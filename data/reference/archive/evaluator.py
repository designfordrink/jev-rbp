"""
evaluator.py — Calcul du coût total d'une solution de blocking.

Pourquoi ce module :
    L'évaluateur est la fonction objectif du problème d'optimisation. Il doit
    être rapide, précis et décomposé par composante pour permettre le debugging
    et la comparaison entre solutions.

Formulation du coût (Magnanti & Wong, 1984 ; adapté RBP) :
    Coût total = Coût fixe + Coût transport + Coût manutention + Coût interchange

    Coût fixe         = Σ_{blocs ouverts} BLOCK_FIXED_COST
    Coût transport    = Σ_{blocs} block_volume × route_distance × TRANSPORT_COST_COEFF
    Coût manutention  = Σ_{yards intermédiaires} cars_classified × handling_cost[yard]
    Coût interchange  = Σ_{wagons en interchange} INTERCHANGE_COST
                        (toujours 0 sur l'instance jouet mono-railroad)

Définition de "yard intermédiaire" (classification) :
    Pour une commodité suivant la séquence de blocs B1 → B2 → B3 :
    - Les wagons sont classifiés à to_yard(B1) = from_yard(B2) (hub intermédiaire 1)
    - Puis à to_yard(B2) = from_yard(B3) (hub intermédiaire 2)
    - Pas de classification au yard origine ni au yard destination finale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from src.data_loader import RailNetwork, get_sp_distance, min_block_volume
from src.io_json import BlockDesign, BlockingSequence, BlockRoute, parse_outputs


# ---------------------------------------------------------------------------
# Résultat détaillé de l'évaluation
# ---------------------------------------------------------------------------

@dataclass
class CostBreakdown:
    """
    Décomposition complète du coût d'une solution.

    Attributs
    ---------
    fixed_cost      : coût fixe total (nb_blocs × BLOCK_FIXED_COST)
    transport_cost  : coût de transport (Σ volume × miles × coeff)
    handling_cost   : coût de manutention aux yards intermédiaires
    interchange_cost: coût d'interchange inter-railroads (0 sur instance jouet)
    total_cost      : somme des 4 composantes
    num_blocks      : nombre de blocs ouverts
    total_car_miles : Σ volume × route_distance (indicateur physique)
    classified_by_yard : {yard_id: nb_wagons_classifiés} (pour debug C3)
    """
    fixed_cost: float = 0.0
    transport_cost: float = 0.0
    handling_cost: float = 0.0
    interchange_cost: float = 0.0
    total_cost: float = 0.0
    num_blocks: int = 0
    total_car_miles: float = 0.0
    classified_by_yard: Dict[int, float] = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [
            "=== Décomposition du coût ===",
            f"  Blocs ouverts       : {self.num_blocks}",
            f"  Coût fixe           : ${self.fixed_cost:,.0f}",
            f"  Coût transport      : ${self.transport_cost:,.0f}",
            f"  Coût manutention    : ${self.handling_cost:,.0f}",
            f"  Coût interchange    : ${self.interchange_cost:,.0f}",
            f"  ──────────────────────────────",
            f"  TOTAL               : ${self.total_cost:,.0f}",
            f"  Car-miles totaux    : {self.total_car_miles:,.0f}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def evaluate(
    net: RailNetwork,
    solution: dict,
) -> CostBreakdown:
    """
    Calcule le coût total détaillé d'une solution.

    Paramètres
    ----------
    net      : RailNetwork chargé par data_loader.load_rail_network()
    solution : dict chargé par io_json.load_solution()

    Retourne
    --------
    CostBreakdown avec toutes les composantes de coût.

    Exemple
    -------
    >>> from src.data_loader import load_rail_network
    >>> from src.io_json import load_solution
    >>> net = load_rail_network("data/")
    >>> sol = load_solution("data/solution_result.json")
    >>> cost = evaluate(net, sol)
    >>> print(cost)
    """
    parsed = parse_outputs(solution)
    blocks: List[BlockDesign] = parsed["blocks"]
    sequences: List[BlockingSequence] = parsed["sequences"]
    routes: List[BlockRoute] = parsed["routes"]

    # Index des routes par block_id pour accès O(1)
    route_by_block: Dict[int, BlockRoute] = {r["block_id"]: r for r in routes}

    # Index des blocs par block_id pour accès O(1)
    block_by_id: Dict[int, BlockDesign] = {b["block_id"]: b for b in blocks}

    result = CostBreakdown()
    result.num_blocks = len(blocks)

    # ------------------------------------------------------------------
    # 1. Coût fixe
    # ------------------------------------------------------------------
    result.fixed_cost = result.num_blocks * net.settings["block_fixed_cost"]

    # ------------------------------------------------------------------
    # 2. Coût de transport : Σ_blocs block_volume × route_distance × coeff
    # ------------------------------------------------------------------
    # Calcul de la distance de chaque route physique (somme des longueurs de liens).
    # On utilise la route physique réelle (pas le plus court chemin) pour être fidèle
    # à la solution : les wagons parcourent réellement cette distance.
    link_length: Dict[int, float] = {
        int(row["link_id"]): float(row["length"])
        for _, row in net.links_df.iterrows()
    }

    block_route_distance: Dict[int, float] = {}
    for block in blocks:
        bid = block["block_id"]
        route = route_by_block.get(bid)
        if route is None:
            # LIMITE: bloc sans route déclarée → distance = plus court chemin (approx)
            dist = get_sp_distance(net, block["from_yard_id"], block["to_yard_id"])
        else:
            link_ids = route.get("path_link_ids", [])
            dist = sum(link_length.get(lid, 0.0) for lid in link_ids)
        block_route_distance[bid] = dist

        car_miles = block["block_volume"] * dist
        result.transport_cost += car_miles * net.settings["transport_cost_coefficient"]
        result.total_car_miles += car_miles

    # ------------------------------------------------------------------
    # 3. Coût de manutention aux yards intermédiaires
    # ------------------------------------------------------------------
    # Pour chaque commodité, les wagons sont classifiés à chaque yard intermédiaire
    # de sa séquence de blocs (tous les yards sauf le yard origine de la commodité).
    #
    # Exemple : séquence "10 -> 28" pour commodité 11012 → 10002
    #   Bloc 10 : 11012 → 11018, Bloc 28 : 11018 → 10002
    #   Classification à 11018 (yard intermédiaire = to_yard(B10) = from_yard(B28))
    #
    # Données de coût de manutention : handling_cost[yard_id] en $/wagon.
    handling_cost_by_yard: Dict[int, float] = {
        int(row["node_id"]): float(row["handling_cost"])
        for _, row in net.yards_df.iterrows()
    }

    for seq in sequences:
        block_ids = seq["blocking_sequence_ids"]
        volume = float(seq["volume"])

        if len(block_ids) <= 1:
            # Bloc direct : aucune classification intermédiaire
            continue

        # Les yards intermédiaires sont to_yard(B_i) pour i = 0..n-2
        # (équivalent à from_yard(B_{i+1}))
        for i in range(len(block_ids) - 1):
            bid = block_ids[i]
            block = block_by_id.get(bid)
            if block is None:
                continue
            intermediate_yard = block["to_yard_id"]

            # Accumuler pour C3 (capacité de manutention)
            result.classified_by_yard[intermediate_yard] = (
                result.classified_by_yard.get(intermediate_yard, 0.0) + volume
            )

            # Coût de manutention
            h_cost = handling_cost_by_yard.get(intermediate_yard, 0.0)
            result.handling_cost += volume * h_cost

    # ------------------------------------------------------------------
    # 4. Coût d'interchange
    # ------------------------------------------------------------------
    # SIMPLIFICATION: toujours 0 sur l'instance jouet (mono-railroad BNSF).
    # Sur le US National Model, un wagon en interchange = wagon transféré d'un
    # railroad à un autre → coût INTERCHANGE_COST par voiture.
    # TODO: implémenter quand les grandes instances multi-railroads seront publiées.
    result.interchange_cost = 0.0

    # ------------------------------------------------------------------
    # Total
    # ------------------------------------------------------------------
    result.total_cost = (
        result.fixed_cost
        + result.transport_cost
        + result.handling_cost
        + result.interchange_cost
    )

    return result
