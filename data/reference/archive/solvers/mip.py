"""
mip.py — Formulation MIP exacte du Railroad Blocking Problem.

Formulation
-----------
Variables :
    y[i,j]   ∈ {0,1}   : bloc ouvert de yard i vers yard j (Block Design)
    z[k,i,j] ∈ {0,1}   : commodité k utilise le bloc (i,j) (Blocking Sequence)

La route physique de chaque bloc = plus court chemin SP(i,j) sur le réseau
physique (satisfait automatiquement C6 : ratio = 1.0 ≤ 1.3).
Pour les instances très chargées où C5 (capacité liens) est saturée, un
modèle étendu avec variables de route serait nécessaire (voir TODO).

Objectif :
    min  Σ_{ij}  f   · y[i,j]                        (coût fixe)
       + Σ_{k,ij} c_ij · vol_k · z[k,i,j]             (coût transport)
       + Σ_{k,(i,j): j≠dest_k} h_j · vol_k · z[k,i,j] (coût manutention)

Contraintes :
    C1  : conservation des flux par commodité et par yard
    C2  : limite de classification tracks par yard (manifest/bulk uniquement)
    C3  : capacité de manutention par yard (inbound classifié)
    C4a : volume minimum par bloc ouvert  (≥ V_min[i,j] · y[i,j])
    C4b : flux lié à l'ouverture du bloc  (z[k,i,j] ≤ y[i,j])
    C5  : capacité des liens physiques    (Σ flux traversant chaque lien ≤ cap)
    C6  : implicite — route = SP (ratio = 1.0)
    C7  : implicite — z binaire + flow conservation = pas de split

Solveur :
    appsi_highs (HiGHS via Pyomo APPSI, open-source, ~×5–10 vs GLPK)
    Fallback : gurobi si disponible (×10–100 vs open-source sur FC-MCND)

Références :
    Magnanti & Wong (1984)  — formulation FC-MCND de base
    Barnhart, Jin & Vance (2000, Oper. Res.) — Branch-and-Price
    Crainic & Hewitt (2021) — revue Network Design avec Benders

# LIMITE: cette formulation ne gère pas la sélection de route alternative
#   quand C5 est saturée (route fixée au SP). Pour les grandes instances,
#   introduire des variables de route y[i,j,p] ∈ {0,1} (chemin p pour bloc ij).
# TODO (Phase 3.2): Branch-and-Price (Barnhart et al.) pour les grandes instances.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from pyomo.environ import (
    Binary,
    ConcreteModel,
    Constraint,
    NonNegativeReals,
    Objective,
    Set as PyoSet,
    SolverFactory,
    Var,
    minimize,
    value,
)

from src.data_loader import (
    RailNetwork,
    get_link_id,
    get_sp_distance,
    get_sp_path,
    min_block_volume,
)
from src.io_json import BlockDesign, BlockingSequence, BlockRoute


# ---------------------------------------------------------------------------
# Résultat du solver MIP
# ---------------------------------------------------------------------------

@dataclass
class MIPSolution:
    """
    Solution produite par le solver MIP.

    Attributs
    ---------
    blocks      : liste des blocs ouverts (BlockDesign)
    sequences   : séquences de blocs par commodité (BlockingSequence)
    routes      : routes physiques des blocs (BlockRoute)
    unrouted    : commodity_ids non routés (doit être vide si is_feasible)
    is_feasible : True si une solution entière faisable a été trouvée
    obj_value   : valeur objective de la meilleure solution entière trouvée
    lower_bound : borne inférieure MIP (LP relaxation bound)
    mip_gap     : gap relatif = (UB - LB) / UB
    solve_time  : temps CPU total (secondes)
    """
    blocks: List[BlockDesign] = field(default_factory=list)
    sequences: List[BlockingSequence] = field(default_factory=list)
    routes: List[BlockRoute] = field(default_factory=list)
    unrouted: List[int] = field(default_factory=list)
    is_feasible: bool = False
    obj_value: float = float("inf")
    lower_bound: float = 0.0
    mip_gap: float = float("inf")
    solve_time: float = 0.0

    def to_solution_dict(self, net: RailNetwork) -> Dict[str, Any]:
        """Convertit en format solution_result.json compatible avec io_json."""
        from src.io_json import build_solution_json
        return build_solution_json(net, self.blocks, self.sequences, self.routes)

    def __str__(self) -> str:
        return (
            f"MIPSolution(blocs={len(self.blocks)}, séquences={len(self.sequences)}, "
            f"obj={self.obj_value:,.0f}, LB={self.lower_bound:,.0f}, "
            f"gap={self.mip_gap*100:.2f}%, t={self.solve_time:.1f}s, "
            f"faisable={self.is_feasible})"
        )


# ---------------------------------------------------------------------------
# Solver principal
# ---------------------------------------------------------------------------

def solve_mip(
    net: RailNetwork,
    time_limit: float = 300.0,
    mip_gap: float = 0.001,
    solver_name: str = "appsi_highs",
    warm_start: Optional["GreedySolution"] = None,  # noqa: F821
    verbose: bool = False,
) -> MIPSolution:
    """
    Résout le Railroad Blocking Problem via formulation MIP Pyomo.

    Pourquoi une formulation arc-nœud compacte :
        Pour l'instance jouet (8 yards, 50 commodités), le modèle a ~2800 variables
        binaires — trivial pour HiGHS. La formulation compacte (z[k,i,j]) est
        préférable à la formulation étendue (Branch-and-Price) sur les petites instances.
        # TODO (Phase 3.2): basculer vers Branch-and-Price pour |Y| > 100.

    Paramètres
    ----------
    net          : RailNetwork chargé via load_rail_network()
    time_limit   : limite CPU en secondes (défaut : 5 min)
    mip_gap      : gap MIP relatif acceptable (défaut : 0.1%)
    solver_name  : "appsi_highs" (défaut) ou "gurobi"
    warm_start   : solution greedy initiale pour accélérer la recherche
    verbose      : afficher les logs du solveur

    Retourne
    --------
    MIPSolution avec les trois outputs du problème (blocks, sequences, routes)
    """
    t_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Préparer les ensembles et paramètres
    # ------------------------------------------------------------------
    settings = net.settings
    fixed_cost   = settings["block_fixed_cost"]
    transp_coeff = settings["transport_cost_coefficient"]

    yards = sorted(net.yard_ids)
    demands_df = net.demands_df

    # Paramètres par yard
    num_tracks     = {int(r.node_id): float(r.num_tracks)
                      for _, r in net.yards_df.iterrows()}
    handling_cap   = {int(r.node_id): float(r.handling_capacity)
                      for _, r in net.yards_df.iterrows()}
    handling_cost  = {int(r.node_id): float(r.handling_cost)
                      for _, r in net.yards_df.iterrows()}
    # Yards soumis à C2 (tracks limit) = manifest/bulk (pas intermodal/auto)
    # HYPOTHÈSE: "hump" et "flat" yards sont tous classifiants sauf les types intermodal.
    # Pour l'instance jouet, tous les yards Merchandise sont soumis à C2.
    tracks_limited = set(yards)  # ajuster si types intermodal/auto présents

    # Paramètres par commodité
    K  = list(demands_df["commodity_id"].astype(int))
    ok = {int(r.commodity_id): int(r.origin_yard_id) for _, r in demands_df.iterrows()}
    dk = {int(r.commodity_id): int(r.dest_yard_id)   for _, r in demands_df.iterrows()}
    vk = {int(r.commodity_id): float(r.volume)        for _, r in demands_df.iterrows()}
    ck = {int(r.commodity_id): str(r.commodity_type)  for _, r in demands_df.iterrows()}

    # Blocs candidats (i, j) : toutes les paires de yards avec chemin physique valide
    # C6 : implicitement satisfait (route = SP → ratio = 1.0)
    BLOCKS: List[Tuple[int, int]] = []
    block_sp_dist: Dict[Tuple[int, int], float] = {}
    block_sp_path: Dict[Tuple[int, int], List[int]] = {}
    block_min_vol: Dict[Tuple[int, int], float] = {}

    for i in yards:
        for j in yards:
            if i == j:
                continue
            try:
                dist = get_sp_distance(net, i, j)
                path = get_sp_path(net, i, j)
                if dist is None or dist == float("inf"):
                    continue
                BLOCKS.append((i, j))
                block_sp_dist[(i, j)]  = dist
                block_sp_path[(i, j)]  = path
                block_min_vol[(i, j)]  = min_block_volume(settings, dist)
            except Exception:
                continue

    # Pré-calcul : quels liens physiques sont traversés par chaque bloc
    # Nécessaire pour C5 (capacité liens)
    block_links: Dict[Tuple[int, int], List[int]] = {}
    for (i, j), path in block_sp_path.items():
        links = []
        for a, b in zip(path[:-1], path[1:]):
            lid = get_link_id(net.graph, a, b)
            if lid is not None:
                links.append(lid)
        block_links[(i, j)] = links

    # Capacité des liens physiques (C5)
    link_cap: Dict[int, float] = {}
    for _, r in net.links_df.iterrows():
        lid = int(r.link_id)
        cap = float(r.capacity)
        link_cap[lid] = cap
        # Bidirectionnel : même capacité dans les deux sens
        # HYPOTHÈSE: la capacité est partagée entre les deux sens (conservateur).

    # Liens traversés par au moins un bloc (pour ne pas créer de contraintes vides)
    active_links = set()
    for links in block_links.values():
        active_links.update(links)

    # Filtrage : pour Intermodal/Auto, seuls les blocs directs O→D sont admissibles
    # (pas de hub intermédiaire). Pour l'instance jouet Merchandise, sans effet.
    # SIMPLIFICATION: on n'implémente pas encore le filtrage par type de commodité
    # dans les blocs candidats. Tous les blocs (i,j) sont admissibles pour toutes
    # les commodités Merchandise.
    admissible: Dict[int, List[Tuple[int, int]]] = {}
    for k in K:
        c_type = ck[k].lower()
        if c_type in ("intermodal", "automobile", "multilevel"):
            # Bloc direct uniquement
            pair = (ok[k], dk[k])
            admissible[k] = [pair] if pair in set(BLOCKS) else []
        else:
            admissible[k] = BLOCKS

    # ------------------------------------------------------------------
    # 2. Construire le modèle Pyomo
    # ------------------------------------------------------------------
    model = ConcreteModel(name="RailroadBlockingProblem")

    # Ensembles Pyomo
    model.BLOCKS = PyoSet(initialize=BLOCKS)
    model.K      = PyoSet(initialize=K)
    model.YARDS  = PyoSet(initialize=yards)

    # 2a. Variables
    # y[i,j] ∈ {0,1} : bloc ouvert
    model.y = Var(model.BLOCKS, within=Binary)

    # z[k,i,j] ∈ {0,1} : commodité k utilise le bloc (i,j)
    # On ne déclare que les paires admissibles (réduit la taille du modèle)
    KxBLOCKS = [(k, i, j) for k in K for (i, j) in admissible[k]]
    model.KxBLOCKS = PyoSet(initialize=KxBLOCKS)
    model.z = Var(model.KxBLOCKS, within=Binary)

    # 2b. Fonction objectif
    def objective_rule(m):
        # Coût fixe des blocs ouverts
        fixed = sum(fixed_cost * m.y[i, j] for (i, j) in BLOCKS)

        # Coût de transport : vol_k * dist(i,j) * transport_coeff * z[k,i,j]
        transport = sum(
            transp_coeff * block_sp_dist[(i, j)] * vk[k] * m.z[k, i, j]
            for (k, i, j) in KxBLOCKS
        )

        # Coût de manutention : h_j * vol_k * z[k,i,j] si j n'est pas la destination de k
        # (classification aux yards intermédiaires seulement)
        handling = sum(
            handling_cost[j] * vk[k] * m.z[k, i, j]
            for (k, i, j) in KxBLOCKS
            if j != dk[k]
        )

        return fixed + transport + handling

    model.obj = Objective(rule=objective_rule, sense=minimize)

    # 2c. Contraintes

    # C1 — Conservation des flux : pour chaque commodité k et chaque yard m
    # Σ_j z[k,m,j] - Σ_i z[k,i,m] = b_km
    # où b_km = +1 si m=origine_k, -1 si m=dest_k, 0 sinon
    def c1_flow_conservation(m, k, yard):
        out_flow = sum(
            m.z[k, yard, j]
            for (kk, i, j) in KxBLOCKS
            if kk == k and i == yard
        )
        in_flow = sum(
            m.z[k, i, yard]
            for (kk, i, j) in KxBLOCKS
            if kk == k and j == yard
        )
        if yard == ok[k]:
            return out_flow - in_flow == 1
        elif yard == dk[k]:
            return out_flow - in_flow == -1
        else:
            return out_flow - in_flow == 0

    model.c1_flow_conservation = Constraint(
        model.K, model.YARDS, rule=c1_flow_conservation
    )

    # C2 — Limite de tracks par yard (manifest/bulk uniquement)
    def c2_track_limit(m, yard):
        if yard not in tracks_limited:
            return Constraint.Skip
        n_out = sum(m.y[i, j] for (i, j) in BLOCKS if i == yard)
        return n_out <= num_tracks[yard]

    model.c2_track_limit = Constraint(model.YARDS, rule=c2_track_limit)

    # C3 — Capacité de manutention par yard
    # Σ_{k,(i,yard): yard≠dest_k} vol_k * z[k,i,yard] ≤ W_yard
    def c3_handling_capacity(m, yard):
        inbound = sum(
            vk[k] * m.z[k, i, yard]
            for (k, i, j) in KxBLOCKS
            if j == yard and yard != dk[k]
        )
        return inbound <= handling_cap[yard]

    model.c3_handling_capacity = Constraint(model.YARDS, rule=c3_handling_capacity)

    # C4a — Volume minimum par bloc ouvert
    # Σ_k vol_k * z[k,i,j] ≥ V_min[i,j] * y[i,j]
    def c4a_min_volume(m, i, j):
        # IMPORTANT: la variable de boucle (k, ii, jj) doit être utilisée dans le corps,
        # pas une variable 'k' de la portée extérieure (bug potentiel si loop var renommée).
        total_flow = sum(
            vk[k] * m.z[k, i, j]
            for (k, ii, jj) in KxBLOCKS
            if ii == i and jj == j
        )
        return total_flow >= block_min_vol[(i, j)] * m.y[i, j]

    model.c4a_min_volume = Constraint(model.BLOCKS, rule=c4a_min_volume)

    # C4b — Lier z à y : commodité ne peut utiliser un bloc que s'il est ouvert
    def c4b_linking(m, k, i, j):
        return m.z[k, i, j] <= m.y[i, j]

    model.c4b_linking = Constraint(model.KxBLOCKS, rule=c4b_linking)

    # C5 — Capacité des liens physiques
    # Pour chaque lien l : Σ_{k,(i,j): l∈route(i,j)} vol_k * z[k,i,j] ≤ cap_l
    def c5_link_capacity(m, link_id):
        total = sum(
            vk[k] * m.z[k, i, j]
            for (k, i, j) in KxBLOCKS
            if link_id in block_links.get((i, j), [])
        )
        return total <= link_cap[link_id]

    model.c5_link_capacity = Constraint(
        list(active_links), rule=c5_link_capacity
    )

    # ------------------------------------------------------------------
    # 3. Warm-start depuis la solution greedy (optionnel)
    # ------------------------------------------------------------------
    if warm_start is not None:
        _apply_warm_start(model, warm_start, BLOCKS, KxBLOCKS, K, ok, dk)

    # ------------------------------------------------------------------
    # 4. Résoudre
    # ------------------------------------------------------------------
    solver = SolverFactory(solver_name)

    # Options HiGHS via APPSI
    if solver_name == "appsi_highs":
        solver.options["time_limit"]     = time_limit
        solver.options["mip_rel_gap"]    = mip_gap
        solver.options["log_to_console"] = verbose
        solver.options["presolve"]       = "on"
        solver.options["parallel"]       = "on"

    elif solver_name == "gurobi":
        solver.options["TimeLimit"] = time_limit
        solver.options["MIPGap"]    = mip_gap
        solver.options["OutputFlag"] = 1 if verbose else 0

    result = solver.solve(model, tee=verbose)

    t_elapsed = time.perf_counter() - t_start

    # ------------------------------------------------------------------
    # 5. Extraire la solution
    # ------------------------------------------------------------------
    sol = MIPSolution(solve_time=t_elapsed)

    # Vérifier si une solution entière a été trouvée
    from pyomo.opt import SolverStatus, TerminationCondition
    is_optimal = result.solver.termination_condition == TerminationCondition.optimal
    is_feasible_mip = result.solver.termination_condition in (
        TerminationCondition.optimal,
        TerminationCondition.maxTimeLimit,
        TerminationCondition.maxIterations,
    )

    # Récupérer les bornes
    try:
        sol.obj_value   = value(model.obj)
        sol.lower_bound = result.problem.lower_bound if hasattr(result.problem, "lower_bound") else 0.0
        if sol.obj_value > 0 and sol.lower_bound > 0:
            sol.mip_gap = (sol.obj_value - sol.lower_bound) / sol.obj_value
    except Exception:
        pass

    # Vérifier si on a une solution entière valide
    try:
        y_vals = {(i, j): round(value(model.y[i, j])) for (i, j) in BLOCKS}
        z_vals = {(k, i, j): round(value(model.z[k, i, j])) for (k, i, j) in KxBLOCKS}
        has_solution = True
    except Exception:
        has_solution = False

    if not has_solution:
        sol.is_feasible = False
        sol.unrouted = K
        return sol

    # Blocs ouverts
    block_id_map: Dict[Tuple[int, int], int] = {}
    block_counter = 1
    opened_blocks = [(i, j) for (i, j) in BLOCKS if y_vals.get((i, j), 0) == 1]

    for (i, j) in opened_blocks:
        # Volume du bloc = Σ_k vol_k * z[k,i,j]
        block_vol = sum(
            vk[k] for k in K
            if z_vals.get((k, i, j), 0) == 1
        )
        # Type dominant dans le bloc
        types_in_block = [ck[k] for k in K if z_vals.get((k, i, j), 0) == 1]
        dom_type = _dominant_type(types_in_block) if types_in_block else "Merchandise"

        sol.blocks.append({
            "block_id": block_counter,
            "from_yard_id": i,
            "to_yard_id": j,
            "commodity_type": dom_type,
            "block_volume": int(block_vol),
        })
        block_id_map[(i, j)] = block_counter
        block_counter += 1

    # Routes physiques
    for b in sol.blocks:
        i, j = b["from_yard_id"], b["to_yard_id"]
        path  = block_sp_path[(i, j)]
        links = block_links[(i, j)]
        sol.routes.append({
            "block_id": b["block_id"],
            "from_yard_id": i,
            "to_yard_id": j,
            "physical_path_nodes": " -> ".join(map(str, path)),
            "physical_path_links": " -> ".join(map(str, links)),
        })

    # Séquences de blocs par commodité
    routed = set()
    for k in K:
        # Reconstruire le chemin de k dans le graphe de service
        k_arcs = [(i, j) for (kk, i, j) in KxBLOCKS if kk == k and z_vals.get((k, i, j), 0) == 1]
        if not k_arcs:
            sol.unrouted.append(k)
            continue

        # Trier les arcs pour reconstituer la séquence O→…→D
        seq = _sort_service_path(k_arcs, ok[k], dk[k])
        block_ids_seq = [str(block_id_map[arc]) for arc in seq if arc in block_id_map]

        # Trouver la ligne demands correspondante
        row = demands_df[demands_df["commodity_id"] == k].iloc[0]
        sol.sequences.append({
            "commodity_id": k,
            "commodity_type": str(row.commodity_type),
            "origin_yard_id": ok[k],
            "dest_yard_id": dk[k],
            "volume": int(vk[k]),
            "blocking_sequence": " -> ".join(block_ids_seq),
            "blocking_sequence_ids": [block_id_map[arc] for arc in seq if arc in block_id_map],
        })
        routed.add(k)

    sol.is_feasible = len(sol.unrouted) == 0
    return sol


# ---------------------------------------------------------------------------
# Fonctions utilitaires internes
# ---------------------------------------------------------------------------

def _dominant_type(types: List[str]) -> str:
    """Retourne le type de commodité dominant dans un bloc (le plus fréquent)."""
    from collections import Counter
    if not types:
        return "Merchandise"
    return Counter(types).most_common(1)[0][0]


def _sort_service_path(
    arcs: List[Tuple[int, int]],
    origin: int,
    dest: int,
) -> List[Tuple[int, int]]:
    """
    Reconstruit la séquence ordonnée d'arcs de service O→…→D
    à partir d'une liste non ordonnée d'arcs.

    Algorithme : parcours BFS depuis l'origine sur les arcs disponibles.
    """
    adj: Dict[int, int] = {i: j for (i, j) in arcs}
    path = []
    node = origin
    visited = set()
    while node != dest and node not in visited:
        visited.add(node)
        nxt = adj.get(node)
        if nxt is None:
            break
        path.append((node, nxt))
        node = nxt
    return path


def _apply_warm_start(
    model: ConcreteModel,
    warm_start: Any,
    BLOCKS: List[Tuple[int, int]],
    KxBLOCKS: List[Tuple[int, int, int]],
    K: List[int],
    ok: Dict[int, int],
    dk: Dict[int, int],
) -> None:
    """
    Initialise les variables du modèle depuis la solution greedy.

    Pourquoi : HiGHS et Gurobi utilisent le warm-start pour amorcer la
    recherche à partir d'une solution entière connue, réduisant souvent le
    temps de résolution de 20–50% sur les instances de taille moyenne.
    # PERFORMANCE: impact maximal pour les instances > 200 commodités.
    """
    # Map (from_yard, to_yard) → bloc ouvert dans le greedy
    open_pairs = {
        (b["from_yard_id"], b["to_yard_id"])
        for b in warm_start.blocks
    }
    # Map commodity_id → liste d'arcs de service
    seq_map: Dict[int, List[Tuple[int, int]]] = {}
    for s in warm_start.sequences:
        kid = s["commodity_id"]
        block_ids = s.get("blocking_sequence_ids", [])
        # Reconstituer les arcs depuis les IDs de blocs
        bid_to_pair = {b["block_id"]: (b["from_yard_id"], b["to_yard_id"]) for b in warm_start.blocks}
        seq_map[kid] = [bid_to_pair[bid] for bid in block_ids if bid in bid_to_pair]

    for (i, j) in BLOCKS:
        model.y[i, j].set_value(1 if (i, j) in open_pairs else 0)

    for (k, i, j) in KxBLOCKS:
        uses = (i, j) in seq_map.get(k, [])
        model.z[k, i, j].set_value(1 if uses else 0)
