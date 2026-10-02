"""
vlns.py — Very Large-Scale Neighborhood Search pour le Railroad Blocking Problem.

Algorithme
----------
La VLNS (Ahuja, Jha & Liu, 2007) est une métaheuristique basée sur des mouvements
de large voisinage qui permettent de remettre en question simultanément un grand
nombre de décisions de la solution courante.

Pour le RBP, trois types de mouvements sont implémentés :

1. **Drop move** : fermer un bloc existant et re-router ses commodités via des blocs
   alternatifs. Si toutes les commodités trouvent un chemin alternatif de coût moindre
   que l'économie de coût fixe, le mouvement est accepté.

2. **Add move** : ouvrir un nouveau bloc et re-router toutes les commodités. Certaines
   commodités peuvent maintenant emprunter le nouveau bloc en tant que hub. Si le gain
   de transport/manutention dépasse le coût fixe supplémentaire, le mouvement est accepté.

3. **Swap move** (composé) : fermer un bloc ET ouvrir un autre simultanément. Ce mouvement
   de plus grand voisinage explore des solutions inaccessibles aux seuls Drop/Add.

Stratégie de recherche
----------------------
- **Descente par meilleure amélioration** (best-improving steepest descent) :
  à chaque itération, évaluer TOUS les mouvements de chaque type et appliquer le meilleur.
- Si aucun mouvement n'est améliorant → arrêt (optimalité locale).
- En pratique, 5–20 itérations suffisent pour l'instance jouet.

Deux phases :
1. Drop phase : supprimer les blocs redondants (gains fixes importants)
2. Add/Swap phase : explorer les consolidations restantes

Sous-problème de routage
------------------------
Étant donné un ensemble de blocs ouverts B, chaque commodité k est routée
indépendamment par le **plus court chemin** (Dijkstra) sur le graphe de service :
    - Nœuds : yards
    - Arcs : blocs ouverts (i,j) ∈ B
    - Coût de l'arc (i,j) pour la commodité k :
        c(k,i,j) = τ × d(i,j) + h_j × 1[j ≠ dest_k]
        où τ = transport_cost_coeff, d(i,j) = SP distance yards, h_j = handling_cost[j]
    (Multiplier par vol_k pour le coût total, mais invariant pour le choix de chemin)

Références
----------
Ahuja, R.K., Jha, K.C. & Liu, J. (2007).
    "Solving real-life railroad blocking problems." Interfaces, 37(5), 404–419.
Crainic, T.G. (1988). Service network design in freight transportation. EJOR.
Magnanti, T.L. & Wong, R.T. (1984). Network design and transportation planning.
    Transportation Science, 18(1), 1–55.

# LIMITE: cette implémentation utilise la descente par meilleure amélioration, qui
#   s'arrête au premier minimum local. Pour les grandes instances, envisager :
#   (a) Recherche tabou (Tabu Search) avec liste tabou sur les blocs récemment modifiés
#   (b) Perturbation + redémarrage (Iterated Local Search)
#   (c) Path Relinking (Ahuja et al. mentionnent cette extension)
# TODO (Phase 4.2): ajouter perturbation aléatoire pour diversification.
# TODO (Phase 4.3): basculer le graphe de service vers igraph pour >500 commodités
#   (NetworkX Dijkstra ~×10 plus lent qu'igraph sur grands graphes).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import networkx as nx

from src.data_loader import (
    RailNetwork,
    get_link_id,
    get_sp_distance,
    get_sp_path,
    min_block_volume,
)
from src.io_json import BlockDesign, BlockingSequence, BlockRoute


# ---------------------------------------------------------------------------
# Résultat de la VLNS
# ---------------------------------------------------------------------------

@dataclass
class VLNSSolution:
    """
    Solution produite par le solver VLNS.

    Attributs
    ---------
    blocks       : liste des blocs ouverts (BlockDesign)
    sequences    : séquences de blocs par commodité (BlockingSequence)
    routes       : routes physiques des blocs (BlockRoute)
    unrouted     : commodity_ids non routés (vide si is_feasible)
    is_feasible  : True si solution faisable pour C1-C7
    obj_value    : coût total de la meilleure solution trouvée
    solve_time   : temps CPU (secondes)
    n_iterations : nombre d'itérations VLNS exécutées
    improvements : liste des améliorations successives [(itération, delta_cost), ...]
    """
    blocks: List[BlockDesign] = field(default_factory=list)
    sequences: List[BlockingSequence] = field(default_factory=list)
    routes: List[BlockRoute] = field(default_factory=list)
    unrouted: List[int] = field(default_factory=list)
    is_feasible: bool = False
    obj_value: float = float("inf")
    solve_time: float = 0.0
    n_iterations: int = 0
    improvements: List[Tuple[int, float]] = field(default_factory=list)

    def to_solution_dict(self, net: RailNetwork) -> Dict[str, Any]:
        """Convertit en format solution_result.json compatible avec io_json."""
        from src.io_json import build_solution_json
        return build_solution_json(net, self.blocks, self.sequences, self.routes)

    def __str__(self) -> str:
        impr_str = (
            f"{len(self.improvements)} améliorations"
            if self.improvements
            else "aucune amélioration"
        )
        return (
            f"VLNSSolution(blocs={len(self.blocks)}, obj={self.obj_value:,.0f}, "
            f"t={self.solve_time:.1f}s, iter={self.n_iterations}, {impr_str})"
        )


# ---------------------------------------------------------------------------
# Solver principal
# ---------------------------------------------------------------------------

def solve_vlns(
    net: RailNetwork,
    initial_solution: Optional[Any] = None,
    max_iterations: int = 100,
    time_limit: float = 300.0,
    verbose: bool = False,
) -> VLNSSolution:
    """
    Résout le RBP par Very Large-Scale Neighborhood Search (VLNS).

    Pourquoi la VLNS sur la VLNS d'Ahuja et al. (2007) :
        La VLNS explore des voisinages de taille polynomiale (|B|² pour Swap) mais
        chaque évaluation de voisin se fait en O(|K| × |B| log|Y|) grâce à Dijkstra,
        ce qui la rend tractable là où un MIP exact serait trop lent (|Y| > 100).

    Paramètres
    ----------
    net              : RailNetwork chargé via load_rail_network()
    initial_solution : GreedySolution ou MIPSolution (None = démarrer du greedy)
    max_iterations   : nombre maximal d'itérations de la boucle principale
    time_limit       : limite CPU en secondes
    verbose          : afficher les logs de chaque itération

    Retourne
    --------
    VLNSSolution avec les trois outputs du problème (blocks, sequences, routes)
    """
    t_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Préparer les structures de données
    # ------------------------------------------------------------------
    settings = net.settings
    fixed_cost   = settings["block_fixed_cost"]
    transp_coeff = settings["transport_cost_coefficient"]

    yards = sorted(net.yard_ids)
    demands_df = net.demands_df

    K  = list(demands_df["commodity_id"].astype(int))
    ok = {int(r.commodity_id): int(r.origin_yard_id) for _, r in demands_df.iterrows()}
    dk = {int(r.commodity_id): int(r.dest_yard_id)   for _, r in demands_df.iterrows()}
    vk = {int(r.commodity_id): float(r.volume)        for _, r in demands_df.iterrows()}

    num_tracks = {int(r.node_id): float(r.num_tracks)        for _, r in net.yards_df.iterrows()}
    handling_cost = {int(r.node_id): float(r.handling_cost)  for _, r in net.yards_df.iterrows()}

    # Tous les blocs candidats (paires de yards avec SP valide)
    all_blocks: List[Tuple[int, int]] = []
    block_sp_dist: Dict[Tuple[int, int], float] = {}
    block_sp_path: Dict[Tuple[int, int], List[int]] = {}
    block_min_vol: Dict[Tuple[int, int], float] = {}
    block_links: Dict[Tuple[int, int], List[int]] = {}

    for i in yards:
        for j in yards:
            if i == j:
                continue
            dist = get_sp_distance(net, i, j)
            if dist is None or dist == float("inf"):
                continue
            path = get_sp_path(net, i, j)
            links = []
            for a, b in zip(path[:-1], path[1:]):
                lid = get_link_id(net.graph, a, b)
                if lid is not None:
                    links.append(lid)
            all_blocks.append((i, j))
            block_sp_dist[(i, j)] = dist
            block_sp_path[(i, j)] = path
            block_min_vol[(i, j)] = min_block_volume(settings, dist)
            block_links[(i, j)] = links

    all_blocks_set = set(all_blocks)

    # ------------------------------------------------------------------
    # 2. Initialiser depuis la solution fournie ou le greedy
    # ------------------------------------------------------------------
    if initial_solution is None:
        from src.solvers.greedy import solve_greedy
        initial_solution = solve_greedy(net)
        if verbose:
            print(f"VLNS: départ greedy (obj={_extract_cost(initial_solution):,.0f})")

    open_blocks, routes_k = _extract_state(initial_solution, K, ok, dk)

    # Vérifier la cohérence de l'état initial
    if not open_blocks or routes_k is None:
        # Rerouter depuis scratch sur les blocs ouverts
        routes_k = _route_all_commodities(
            open_blocks, K, ok, dk, transp_coeff, block_sp_dist, handling_cost
        )
        if routes_k is None:
            raise ValueError("VLNS: l'état initial est infaisable (routage impossible).")

    current_cost, used_blocks = _compute_cost(
        routes_k, K, dk, vk, fixed_cost, transp_coeff, block_sp_dist, handling_cost
    )
    open_blocks = frozenset(used_blocks)  # Ne garder que les blocs effectivement utilisés

    if verbose:
        print(f"VLNS: coût initial = ${current_cost:,.0f}, blocs ouverts = {len(open_blocks)}")

    best_cost = current_cost
    best_open = open_blocks
    best_routes = routes_k
    improvements = []

    # ------------------------------------------------------------------
    # 3. Boucle principale VLNS
    # ------------------------------------------------------------------
    for iteration in range(1, max_iterations + 1):
        if time.perf_counter() - t_start > time_limit:
            if verbose:
                print(f"VLNS: limite de temps atteinte ({time_limit}s)")
            break

        improved = False

        # ---- Phase A : Drop moves ----
        # Essayer de fermer chaque bloc ouvert
        best_drop = _best_drop_move(
            open_blocks, routes_k, K, ok, dk, vk,
            fixed_cost, transp_coeff, block_sp_dist, handling_cost,
            block_min_vol, num_tracks, current_cost,
        )
        if best_drop is not None:
            new_cost, new_open, new_routes = best_drop
            delta = current_cost - new_cost
            if verbose:
                print(f"  iter {iteration}: DROP Δ=${delta:,.0f} → {len(new_open)} blocs (${new_cost:,.0f})")
            current_cost, open_blocks, routes_k = new_cost, new_open, new_routes
            improvements.append((iteration, delta))
            improved = True

        # ---- Phase B : Add moves ----
        # Essayer d'ouvrir chaque bloc candidat non encore ouvert
        closed_blocks = [b for b in all_blocks if b not in open_blocks]
        best_add = _best_add_move(
            open_blocks, closed_blocks, routes_k, K, ok, dk, vk,
            fixed_cost, transp_coeff, block_sp_dist, handling_cost,
            block_min_vol, num_tracks, current_cost,
        )
        if best_add is not None:
            new_cost, new_open, new_routes = best_add
            delta = current_cost - new_cost
            if verbose:
                print(f"  iter {iteration}: ADD  Δ=${delta:,.0f} → {len(new_open)} blocs (${new_cost:,.0f})")
            current_cost, open_blocks, routes_k = new_cost, new_open, new_routes
            improvements.append((iteration, delta))
            improved = True

        # ---- Phase C : Swap moves (composé Drop + Add) ----
        # Essayer de substituer un bloc ouvert par un bloc fermé
        if not improved:
            closed_blocks = [b for b in all_blocks if b not in open_blocks]
            best_swap = _best_swap_move(
                open_blocks, closed_blocks, routes_k, K, ok, dk, vk,
                fixed_cost, transp_coeff, block_sp_dist, handling_cost,
                block_min_vol, num_tracks, current_cost,
            )
            if best_swap is not None:
                new_cost, new_open, new_routes = best_swap
                delta = current_cost - new_cost
                if verbose:
                    print(f"  iter {iteration}: SWAP Δ=${delta:,.0f} → {len(new_open)} blocs (${new_cost:,.0f})")
                current_cost, open_blocks, routes_k = new_cost, new_open, new_routes
                improvements.append((iteration, delta))
                improved = True

        if not improved:
            if verbose:
                print(f"  iter {iteration}: aucune amélioration — optimum local atteint")
            break

        # Mettre à jour le meilleur global
        if current_cost < best_cost:
            best_cost = current_cost
            best_open = open_blocks
            best_routes = routes_k

    t_elapsed = time.perf_counter() - t_start

    # ------------------------------------------------------------------
    # 4. Construire la solution finale
    # ------------------------------------------------------------------
    sol = _build_vlns_solution(
        net, best_open, best_routes, K, ok, dk, vk,
        block_sp_path, block_links, best_cost, demands_df,
        t_elapsed, iteration, improvements,
    )
    return sol


# ---------------------------------------------------------------------------
# Fonctions de mouvement
# ---------------------------------------------------------------------------

def _best_drop_move(
    open_blocks: FrozenSet[Tuple[int, int]],
    routes_k: Dict[int, List[Tuple[int, int]]],
    K, ok, dk, vk,
    fixed_cost, transp_coeff, block_sp_dist, handling_cost,
    block_min_vol, num_tracks, current_cost,
) -> Optional[Tuple[float, FrozenSet, Dict]]:
    """
    Évalue tous les DROP moves et retourne le meilleur (ou None si aucun n'améliore).

    Un DROP move ferme un bloc et re-route toutes les commodités sur les blocs restants.
    Accepté si : (a) toutes les commodités peuvent être re-routées, (b) C2 et C4a
    respectées, (c) le coût total diminue.
    """
    best_improvement = 0.0
    best_result = None

    for block_to_drop in open_blocks:
        candidate_open = open_blocks - {block_to_drop}

        # Re-router toutes les commodités sur les blocs restants
        new_routes = _route_all_commodities(
            candidate_open, K, ok, dk, transp_coeff, block_sp_dist, handling_cost
        )
        if new_routes is None:
            continue  # Certaines commodités ne peuvent pas être re-routées → infaisable

        new_cost, used = _compute_cost(
            new_routes, K, dk, vk, fixed_cost, transp_coeff, block_sp_dist, handling_cost
        )

        # Vérifier C4a (volume minimum par bloc)
        if not _check_c4a(used, new_routes, vk, block_min_vol):
            continue

        # Vérifier C2 (tracks limit par yard)
        if not _check_c2(used, num_tracks):
            continue

        improvement = current_cost - new_cost
        if improvement > best_improvement + 1e-6:
            best_improvement = improvement
            best_result = (new_cost, frozenset(used), new_routes)

    return best_result


def _best_add_move(
    open_blocks: FrozenSet[Tuple[int, int]],
    closed_blocks: List[Tuple[int, int]],
    routes_k: Dict[int, List[Tuple[int, int]]],
    K, ok, dk, vk,
    fixed_cost, transp_coeff, block_sp_dist, handling_cost,
    block_min_vol, num_tracks, current_cost,
) -> Optional[Tuple[float, FrozenSet, Dict]]:
    """
    Évalue tous les ADD moves et retourne le meilleur (ou None si aucun n'améliore).

    Un ADD move ouvre un nouveau bloc et re-route toutes les commodités. Le nouveau
    bloc peut servir de hub alternatif moins coûteux pour certaines commodités.
    Note : si le nouveau bloc n'est pas utilisé par le routage, son coût fixe n'est pas comptabilisé.
    """
    best_improvement = 0.0
    best_result = None

    for block_to_add in closed_blocks:
        candidate_open = open_blocks | {block_to_add}

        new_routes = _route_all_commodities(
            candidate_open, K, ok, dk, transp_coeff, block_sp_dist, handling_cost
        )
        if new_routes is None:
            continue

        new_cost, used = _compute_cost(
            new_routes, K, dk, vk, fixed_cost, transp_coeff, block_sp_dist, handling_cost
        )

        if not _check_c4a(used, new_routes, vk, block_min_vol):
            continue
        if not _check_c2(used, num_tracks):
            continue

        improvement = current_cost - new_cost
        if improvement > best_improvement + 1e-6:
            best_improvement = improvement
            best_result = (new_cost, frozenset(used), new_routes)

    return best_result


def _best_swap_move(
    open_blocks: FrozenSet[Tuple[int, int]],
    closed_blocks: List[Tuple[int, int]],
    routes_k: Dict[int, List[Tuple[int, int]]],
    K, ok, dk, vk,
    fixed_cost, transp_coeff, block_sp_dist, handling_cost,
    block_min_vol, num_tracks, current_cost,
) -> Optional[Tuple[float, FrozenSet, Dict]]:
    """
    Évalue tous les SWAP moves (Drop 1 bloc + Add 1 bloc) et retourne le meilleur.

    Le Swap est le mouvement clé de la VLNS : il remplace un hub existant par un hub
    alternatif, permettant de remodeler la structure de consolidation de la solution.
    Il n'est évalué que lorsqu'aucun Drop ni Add simple n'améliore la solution.

    # PERFORMANCE: O(|open_blocks| × |closed_blocks|) évaluations, chacune O(|K| × |B| log|Y|).
    # Pour |B|=56, |K|=50 → ~3000 évaluations × 50 Dijkstra = ~150,000 Dijkstra.
    # Acceptable sur l'instance jouet (8 yards). Sur le US National Model (>100 yards),
    # utiliser des heuristiques de présélection (promising pairs) comme dans Ahuja et al.
    """
    best_improvement = 0.0
    best_result = None

    for block_to_drop in open_blocks:
        for block_to_add in closed_blocks:
            candidate_open = (open_blocks - {block_to_drop}) | {block_to_add}

            new_routes = _route_all_commodities(
                candidate_open, K, ok, dk, transp_coeff, block_sp_dist, handling_cost
            )
            if new_routes is None:
                continue

            new_cost, used = _compute_cost(
                new_routes, K, dk, vk, fixed_cost, transp_coeff, block_sp_dist, handling_cost
            )

            if not _check_c4a(used, new_routes, vk, block_min_vol):
                continue
            if not _check_c2(used, num_tracks):
                continue

            improvement = current_cost - new_cost
            if improvement > best_improvement + 1e-6:
                best_improvement = improvement
                best_result = (new_cost, frozenset(used), new_routes)

    return best_result


# ---------------------------------------------------------------------------
# Routage (sous-problème de plus court chemin)
# ---------------------------------------------------------------------------

def _route_all_commodities(
    open_blocks: FrozenSet[Tuple[int, int]],
    K: List[int],
    ok: Dict[int, int],
    dk: Dict[int, int],
    transp_coeff: float,
    block_sp_dist: Dict[Tuple[int, int], float],
    handling_cost: Dict[int, float],
) -> Optional[Dict[int, List[Tuple[int, int]]]]:
    """
    Route toutes les commodités sur l'ensemble de blocs donné.

    Pour chaque commodité k, résout un plus court chemin (Dijkstra) de ok[k] à dk[k]
    sur le graphe de service orienté (nœuds = yards, arcs = blocs ouverts).

    Coût de l'arc (i,j) pour la commodité k (par wagon) :
        c(k,i,j) = τ × d(i,j) + h_j × 1[j ≠ dest_k]

    La multiplication par vol_k est inutile pour le choix de chemin (vol_k > 0 constant).

    Retourne None si au moins une commodité ne peut pas être routée.
    """
    # Construire le graphe de service (commun à toutes les commodités)
    G = nx.DiGraph()
    for (i, j) in open_blocks:
        dist = block_sp_dist.get((i, j), 0.0)
        h_j  = handling_cost.get(j, 0.0)
        G.add_edge(i, j, sp_dist=dist, h_j=h_j)

    routes: Dict[int, List[Tuple[int, int]]] = {}
    for k in K:
        origin = ok[k]
        dest   = dk[k]

        # Cas trivial : bloc direct disponible
        if G.has_edge(origin, dest):
            # Vérifier qu'il n'y a pas un chemin encore moins coûteux (possible via hub)
            pass  # Dijkstra s'en charge

        # Dijkstra avec coût dépendant de la destination de k
        for (u, v, data) in G.edges(data=True):
            data["weight"] = (
                transp_coeff * data["sp_dist"]
                + (0.0 if v == dest else data["h_j"])
            )

        try:
            path_nodes = nx.dijkstra_path(G, origin, dest, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None  # Commodité k non routable → mouvement infaisable

        routes[k] = list(zip(path_nodes[:-1], path_nodes[1:]))

    return routes


# ---------------------------------------------------------------------------
# Calcul de coût
# ---------------------------------------------------------------------------

def _compute_cost(
    routes_k: Dict[int, List[Tuple[int, int]]],
    K: List[int],
    dk: Dict[int, int],
    vk: Dict[int, float],
    fixed_cost: float,
    transp_coeff: float,
    block_sp_dist: Dict[Tuple[int, int], float],
    handling_cost: Dict[int, float],
) -> Tuple[float, Set[Tuple[int, int]]]:
    """
    Calcule le coût total d'un routage donné.

    Coût = Σ_{blocs utilisés} fixed_cost
         + Σ_{k, (i,j) ∈ route(k)} τ × d(i,j) × vol_k
         + Σ_{k, (i,j) ∈ route(k), j≠dest_k} h_j × vol_k

    Note : on ne compte le coût fixe que pour les blocs effectivement UTILISÉS
    (au moins une commodité les emprunte), pas pour tous les blocs "ouverts".
    Cela permet d'identifier et de supprimer les blocs redondants.

    Retourne (cost, used_blocks).
    """
    used: Set[Tuple[int, int]] = set()
    for k in K:
        for arc in routes_k[k]:
            used.add(arc)

    cost = len(used) * fixed_cost

    for k in K:
        vol = vk[k]
        for (i, j) in routes_k[k]:
            cost += transp_coeff * block_sp_dist[(i, j)] * vol
            if j != dk[k]:
                cost += handling_cost.get(j, 0.0) * vol

    return cost, used


# ---------------------------------------------------------------------------
# Vérification des contraintes
# ---------------------------------------------------------------------------

def _check_c4a(
    used_blocks: Set[Tuple[int, int]],
    routes_k: Dict[int, List[Tuple[int, int]]],
    vk: Dict[int, float],
    block_min_vol: Dict[Tuple[int, int], float],
) -> bool:
    """
    C4a : volume minimum par bloc ouvert.
    Chaque bloc utilisé doit avoir un volume total ≥ V_min(distance).
    """
    block_volume: Dict[Tuple[int, int], float] = {b: 0.0 for b in used_blocks}
    for k, arcs in routes_k.items():
        for arc in arcs:
            block_volume[arc] = block_volume.get(arc, 0.0) + vk[k]

    for (i, j), vol in block_volume.items():
        if vol < block_min_vol.get((i, j), 0.0) - 1e-6:
            return False
    return True


def _check_c2(
    used_blocks: Set[Tuple[int, int]],
    num_tracks: Dict[int, float],
) -> bool:
    """
    C2 : nombre maximum de blocs sortants par yard ≤ num_tracks[yard].
    """
    outgoing: Dict[int, int] = {}
    for (i, j) in used_blocks:
        outgoing[i] = outgoing.get(i, 0) + 1

    for yard, n_out in outgoing.items():
        if n_out > num_tracks.get(yard, float("inf")):
            return False
    return True


# ---------------------------------------------------------------------------
# Extraction et construction
# ---------------------------------------------------------------------------

def _extract_state(
    sol: Any,
    K: List[int],
    ok: Dict[int, int],
    dk: Dict[int, int],
) -> Tuple[FrozenSet[Tuple[int, int]], Optional[Dict[int, List[Tuple[int, int]]]]]:
    """
    Extrait (open_blocks, routes_k) depuis une GreedySolution ou MIPSolution.
    """
    try:
        open_blocks = frozenset(
            (b["from_yard_id"], b["to_yard_id"]) for b in sol.blocks
        )

        bid_to_pair = {
            b["block_id"]: (b["from_yard_id"], b["to_yard_id"])
            for b in sol.blocks
        }

        routes_k: Dict[int, List[Tuple[int, int]]] = {}
        for seq in sol.sequences:
            kid = seq["commodity_id"]
            block_ids = seq.get("blocking_sequence_ids", [])
            routes_k[kid] = [
                bid_to_pair[bid] for bid in block_ids if bid in bid_to_pair
            ]

        # Compléter les commodités sans séquence (si besoin)
        for k in K:
            if k not in routes_k:
                routes_k[k] = []

        return open_blocks, routes_k

    except (AttributeError, KeyError):
        return frozenset(), None


def _extract_cost(sol: Any) -> float:
    """Extrait le coût de la solution initiale pour affichage."""
    try:
        return sol.obj_value
    except AttributeError:
        return float("inf")


def _build_vlns_solution(
    net: RailNetwork,
    open_blocks: FrozenSet[Tuple[int, int]],
    routes_k: Dict[int, List[Tuple[int, int]]],
    K: List[int],
    ok: Dict[int, int],
    dk: Dict[int, int],
    vk: Dict[int, float],
    block_sp_path: Dict[Tuple[int, int], List[int]],
    block_links: Dict[Tuple[int, int], List[int]],
    obj_value: float,
    demands_df: Any,
    solve_time: float,
    n_iterations: int,
    improvements: List[Tuple[int, float]],
) -> VLNSSolution:
    """
    Construit un VLNSSolution à partir des structures internes de la VLNS.
    """
    sol = VLNSSolution(
        obj_value=obj_value,
        solve_time=solve_time,
        n_iterations=n_iterations,
        improvements=improvements,
    )

    # Calculer les volumes par bloc
    block_volume: Dict[Tuple[int, int], float] = {b: 0.0 for b in open_blocks}
    for k in K:
        for arc in routes_k.get(k, []):
            block_volume[arc] = block_volume.get(arc, 0.0) + vk[k]

    # Types de commodités par bloc
    from collections import Counter
    ck = {int(r.commodity_id): str(r.commodity_type) for _, r in demands_df.iterrows()}
    block_types: Dict[Tuple[int, int], Counter] = {b: Counter() for b in open_blocks}
    for k in K:
        for arc in routes_k.get(k, []):
            block_types[arc][ck.get(k, "Merchandise")] += 1

    # Blocs et routes
    block_id_map: Dict[Tuple[int, int], int] = {}
    for bid, (i, j) in enumerate(sorted(open_blocks), start=1):
        dom_type = block_types[i, j].most_common(1)[0][0] if block_types[i, j] else "Merchandise"
        sol.blocks.append({
            "block_id": bid,
            "from_yard_id": i,
            "to_yard_id": j,
            "commodity_type": dom_type,
            "block_volume": int(round(block_volume.get((i, j), 0.0))),
        })
        block_id_map[(i, j)] = bid

        path  = block_sp_path.get((i, j), [i, j])
        links = block_links.get((i, j), [])
        sol.routes.append({
            "block_id": bid,
            "from_yard_id": i,
            "to_yard_id": j,
            "physical_path_nodes": " -> ".join(map(str, path)),
            "physical_path_links": " -> ".join(map(str, links)),
        })

    # Séquences
    routed_set: set = set()
    for k in K:
        arcs = routes_k.get(k, [])
        if not arcs:
            sol.unrouted.append(k)
            continue

        block_ids_seq = [block_id_map[arc] for arc in arcs if arc in block_id_map]
        row = demands_df[demands_df["commodity_id"] == k].iloc[0]
        sol.sequences.append({
            "commodity_id": k,
            "commodity_type": str(row.commodity_type),
            "origin_yard_id": ok[k],
            "dest_yard_id": dk[k],
            "volume": int(vk[k]),
            "blocking_sequence": " -> ".join(map(str, block_ids_seq)),
            "blocking_sequence_ids": block_ids_seq,
        })
        routed_set.add(k)

    sol.is_feasible = len(sol.unrouted) == 0
    return sol
