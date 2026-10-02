"""
validator.py — Vérification de toutes les contraintes C1–C7 d'une solution.

Pourquoi ce module :
    Un validateur indépendant est essentiel pour trois raisons :
    1. Vérifier que la solution de référence est bien faisable (test de fumée).
    2. Détecter les violations dans les solutions produites par nos solvers.
    3. Guider les heuristiques de réparation (Phase 2) en localisant précisément
       les contraintes violées.

Référence contraintes : cahier des charges INFORMS RAS 2026, reformulé en C1-C7.

Structure de retour :
    ValidationResult contient un champ `violations` (liste de messages) et un
    booléen `is_feasible`. On retourne toutes les violations (et non pas stop
    à la première) pour permettre un debugging complet.

Alternatives considérées :
    - Vérification inline dans chaque solver : risque de duplication et d'oubli.
    - OR-Tools/Pyomo pour contraintes : overkill pour une simple vérification,
      trop couplé à un solveur.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.data_loader import (
    RailNetwork,
    get_link_id,
    get_sp_distance,
    min_block_volume,
)
from src.io_json import BlockDesign, BlockingSequence, BlockRoute, parse_outputs


# ---------------------------------------------------------------------------
# Résultat de validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """
    Résultat de la validation d'une solution.

    Attributs
    ---------
    is_feasible : bool
        True si aucune violation détectée.
    violations  : List[str]
        Messages descriptifs de chaque violation, avec identifiant de contrainte.
    warnings    : List[str]
        Situations inhabituelles non bloquantes (ex: bloc avec volume = min exactement).
    """
    is_feasible: bool = True
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_violation(self, msg: str) -> None:
        self.is_feasible = False
        self.violations.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def __str__(self) -> str:
        status = "FAISABLE ✓" if self.is_feasible else f"INFAISABLE ✗ ({len(self.violations)} violation(s))"
        lines = [f"=== Validation : {status} ==="]
        for v in self.violations:
            lines.append(f"  [VIOLATION] {v}")
        for w in self.warnings:
            lines.append(f"  [WARNING]   {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def validate(
    net: RailNetwork,
    solution: dict,
) -> ValidationResult:
    """
    Vérifie toutes les contraintes C1–C7 d'une solution.

    Paramètres
    ----------
    net      : RailNetwork chargé par data_loader.load_rail_network()
    solution : dict chargé par io_json.load_solution()

    Retourne
    --------
    ValidationResult avec toutes les violations détectées.

    Exemple
    -------
    >>> from src.data_loader import load_rail_network
    >>> from src.io_json import load_solution
    >>> net = load_rail_network("data/")
    >>> sol = load_solution("data/solution_result.json")
    >>> result = validate(net, sol)
    >>> print(result)
    """
    parsed = parse_outputs(solution)
    blocks: List[BlockDesign] = parsed["blocks"]
    sequences: List[BlockingSequence] = parsed["sequences"]
    routes: List[BlockRoute] = parsed["routes"]

    result = ValidationResult()

    # Index des blocs et routes par block_id
    block_by_id: Dict[int, BlockDesign] = {b["block_id"]: b for b in blocks}
    route_by_block: Dict[int, BlockRoute] = {r["block_id"]: r for r in routes}
    block_ids_set: Set[int] = set(block_by_id.keys())

    # Pré-calculer la distance physique de chaque bloc (nécessaire pour C4 et C6)
    link_length: Dict[int, float] = {
        int(row["link_id"]): float(row["length"])
        for _, row in net.links_df.iterrows()
    }
    block_route_distance: Dict[int, float] = _compute_block_distances(
        blocks, route_by_block, link_length, net
    )

    # ------------------------------------------------------------------
    # C7 : Unicité du chemin par commodité (pas de splitting)
    # ------------------------------------------------------------------
    _check_c7_no_split(sequences, net.demands_df, result)

    # ------------------------------------------------------------------
    # C1a : Chaque commodité a au moins un bloc dans sa séquence
    # C1b : La séquence connecte bien l'origine à la destination
    # C1c : Les blocs de la séquence sont chaînés (to_yard[B_i] == from_yard[B_{i+1}])
    # C1d : Tous les block_id référencés dans les séquences existent dans Block Design
    # ------------------------------------------------------------------
    _check_c1_flow_and_connectivity(sequences, block_by_id, result)

    # ------------------------------------------------------------------
    # C1 (routes physiques) : chaque bloc a une route physique valide
    # - Les arcs existent dans le graphe physique
    # - La route va de from_yard à to_yard du bloc
    # - Pas de cycle (subtour)
    # ------------------------------------------------------------------
    _check_c1_physical_routes(blocks, route_by_block, net, result)

    # ------------------------------------------------------------------
    # C2 : num_tracks par yard (blocs sortants manifest/bulk ≤ num_tracks)
    # HYPOTHÈSE: tous les blocs de l'instance jouet sont Merchandise → contrainte active.
    # Intermodal et Automobile sont exempts de la contrainte num_tracks.
    # ------------------------------------------------------------------
    _check_c2_track_limit(blocks, net, result)

    # ------------------------------------------------------------------
    # C3 : handling_capacity par yard
    # Volume classifié à chaque yard ≤ handling_capacity[yard]
    # ------------------------------------------------------------------
    _check_c3_handling_capacity(sequences, block_by_id, net, result)

    # ------------------------------------------------------------------
    # C4 : Volume minimum par bloc selon la distance
    # ------------------------------------------------------------------
    _check_c4_min_volume(blocks, block_route_distance, net, result)

    # ------------------------------------------------------------------
    # C5 : Capacité des liens physiques
    # Volume total circulant sur chaque lien ≤ capacity[lien]
    # ------------------------------------------------------------------
    _check_c5_link_capacity(blocks, route_by_block, net, result)

    # ------------------------------------------------------------------
    # C6 : Ratio de détour max = MAX_CIRCUITOUS_RATIO × shortest_path
    # ------------------------------------------------------------------
    _check_c6_circuitous_ratio(blocks, block_route_distance, net, result)

    return result


# ---------------------------------------------------------------------------
# Vérifications individuelles
# ---------------------------------------------------------------------------

def _check_c7_no_split(
    sequences: List[BlockingSequence],
    demands_df,
    result: ValidationResult,
) -> None:
    """
    C7 : Chaque commodité doit apparaître exactement une fois dans les séquences.
    """
    seen: Dict[int, int] = defaultdict(int)
    for seq in sequences:
        seen[seq["commodity_id"]] += 1

    all_commodity_ids = set(demands_df["commodity_id"].tolist())

    for cid, count in seen.items():
        if count > 1:
            result.add_violation(
                f"C7: Commodité {cid} apparaît {count} fois dans les séquences "
                "(splitting interdit)"
            )

    missing = all_commodity_ids - set(seen.keys())
    for cid in sorted(missing):
        result.add_violation(
            f"C7: Commodité {cid} n'a pas de séquence de blocking assignée"
        )


def _check_c1_flow_and_connectivity(
    sequences: List[BlockingSequence],
    block_by_id: Dict[int, BlockDesign],
    result: ValidationResult,
) -> None:
    """
    C1 : Conservation des flux et connectivité logique des séquences.

    Vérifie :
    - Tous les block_ids référencés existent dans le Block Design
    - La séquence démarre au yard origine de la commodité
    - La séquence termine au yard destination de la commodité
    - Les blocs sont chaînés : to_yard(B_i) == from_yard(B_{i+1})
    """
    for seq in sequences:
        cid = seq["commodity_id"]
        origin = seq["origin_yard_id"]
        dest = seq["dest_yard_id"]
        block_ids = seq["blocking_sequence_ids"]

        if not block_ids:
            result.add_violation(
                f"C1: Commodité {cid} a une séquence vide (aucun bloc)"
            )
            continue

        # Vérifier l'existence des blocs
        missing_blocks = [bid for bid in block_ids if bid not in block_by_id]
        if missing_blocks:
            result.add_violation(
                f"C1: Commodité {cid} : blocs {missing_blocks} référencés mais "
                "absents du Block Design"
            )
            continue  # impossible de vérifier la connectivité sans les blocs

        # Vérifier que la séquence commence à l'origine
        first_block = block_by_id[block_ids[0]]
        if first_block["from_yard_id"] != origin:
            result.add_violation(
                f"C1: Commodité {cid} : le premier bloc (id={block_ids[0]}) "
                f"part de {first_block['from_yard_id']} mais l'origine est {origin}"
            )

        # Vérifier que la séquence se termine à la destination
        last_block = block_by_id[block_ids[-1]]
        if last_block["to_yard_id"] != dest:
            result.add_violation(
                f"C1: Commodité {cid} : le dernier bloc (id={block_ids[-1]}) "
                f"arrive à {last_block['to_yard_id']} mais la destination est {dest}"
            )

        # Vérifier le chaînage : to_yard(B_i) == from_yard(B_{i+1})
        for i in range(len(block_ids) - 1):
            b_curr = block_by_id[block_ids[i]]
            b_next = block_by_id[block_ids[i + 1]]
            if b_curr["to_yard_id"] != b_next["from_yard_id"]:
                result.add_violation(
                    f"C1: Commodité {cid} : bloc {block_ids[i]} arrive à "
                    f"{b_curr['to_yard_id']} mais bloc {block_ids[i+1]} part de "
                    f"{b_next['from_yard_id']} (chaînage rompu)"
                )


def _check_c1_physical_routes(
    blocks: List[BlockDesign],
    route_by_block: Dict[int, BlockRoute],
    net: RailNetwork,
    result: ValidationResult,
) -> None:
    """
    C1 (routes physiques) : chaque route physique de bloc est valide.

    Vérifie :
    - La route existe dans route_by_block pour chaque bloc
    - Le premier nœud = from_yard du bloc
    - Le dernier nœud = to_yard du bloc
    - Chaque arc consécutif (node_i, node_{i+1}) existe dans le graphe physique
    - La liste des link_ids correspond aux arcs parcourus
    - Pas de nœud répété (subtour)
    """
    graph = net.graph

    for block in blocks:
        bid = block["block_id"]
        from_y = block["from_yard_id"]
        to_y = block["to_yard_id"]

        route = route_by_block.get(bid)
        if route is None:
            result.add_violation(
                f"C1: Bloc {bid} ({from_y}→{to_y}) n'a pas de route physique déclarée"
            )
            continue

        node_ids = route.get("path_node_ids", [])
        link_ids = route.get("path_link_ids", [])

        if not node_ids:
            result.add_violation(
                f"C1: Bloc {bid} a une route physique vide (aucun nœud)"
            )
            continue

        # Premier et dernier nœuds
        if node_ids[0] != from_y:
            result.add_violation(
                f"C1: Bloc {bid} : la route physique commence à {node_ids[0]} "
                f"mais le bloc part de {from_y}"
            )
        if node_ids[-1] != to_y:
            result.add_violation(
                f"C1: Bloc {bid} : la route physique se termine à {node_ids[-1]} "
                f"mais le bloc arrive à {to_y}"
            )

        # Chaque arc existe dans le graphe
        for i in range(len(node_ids) - 1):
            u, v = node_ids[i], node_ids[i + 1]
            if not graph.has_edge(u, v):
                result.add_violation(
                    f"C1: Bloc {bid} : arc ({u}, {v}) inexistant dans le réseau physique"
                )

        # Cohérence nœuds / liens : len(links) == len(nodes) - 1
        if link_ids and len(link_ids) != len(node_ids) - 1:
            result.add_violation(
                f"C1: Bloc {bid} : {len(node_ids)} nœuds mais {len(link_ids)} liens "
                "(doit être len(nœuds) - 1)"
            )

        # Vérifier que chaque link_id correspond bien à l'arc nœuds[i]→nœuds[i+1]
        for i, lid in enumerate(link_ids):
            u, v = node_ids[i], node_ids[i + 1]
            if graph.has_edge(u, v):
                actual_lid = graph[u][v]["link_id"]
                if actual_lid != lid:
                    result.add_violation(
                        f"C1: Bloc {bid} : lien déclaré {lid} pour arc ({u},{v}) "
                        f"mais le lien réel est {actual_lid}"
                    )

        # Pas de subtour : tous les nœuds distincts
        if len(node_ids) != len(set(node_ids)):
            result.add_violation(
                f"C1: Bloc {bid} : route physique contient un cycle/subtour "
                f"(nœuds répétés dans {node_ids})"
            )


def _check_c2_track_limit(
    blocks: List[BlockDesign],
    net: RailNetwork,
    result: ValidationResult,
) -> None:
    """
    C2 : Le nombre de blocs SORTANTS de chaque yard ≤ num_tracks[yard].

    Périmètre : Merchandise et Coal/Grain (bulk) uniquement.
    Intermodal et Automobile sont exempts (ils utilisent des voies dédiées).
    # HYPOTHÈSE: dans l'instance jouet, tous les blocs sont Merchandise → contrainte
    # active pour tous les blocs.
    """
    # Compter les blocs sortants par yard et par type de commodité
    outgoing: Dict[int, int] = defaultdict(int)

    TRACK_LIMITED_TYPES = {"Merchandise", "Coal", "Grain"}

    for block in blocks:
        if block["commodity_type"] in TRACK_LIMITED_TYPES:
            outgoing[block["from_yard_id"]] += 1

    num_tracks: Dict[int, int] = {
        int(row["node_id"]): int(row["num_tracks"])
        for _, row in net.yards_df.iterrows()
    }

    for yard_id, count in outgoing.items():
        limit = num_tracks.get(yard_id, 0)
        if count > limit:
            result.add_violation(
                f"C2: Yard {yard_id} : {count} blocs sortants > num_tracks={limit}"
            )


def _check_c3_handling_capacity(
    sequences: List[BlockingSequence],
    block_by_id: Dict[int, BlockDesign],
    net: RailNetwork,
    result: ValidationResult,
) -> None:
    """
    C3 : Volume classifié à chaque yard ≤ handling_capacity[yard].

    Le volume classifié à un yard = somme des wagons qui y font une correspondance
    (tous les yards intermédiaires de toutes les séquences).
    """
    classified: Dict[int, float] = defaultdict(float)

    for seq in sequences:
        block_ids = seq["blocking_sequence_ids"]
        volume = float(seq["volume"])

        for i in range(len(block_ids) - 1):
            bid = block_ids[i]
            block = block_by_id.get(bid)
            if block:
                classified[block["to_yard_id"]] += volume

    handling_capacity: Dict[int, float] = {
        int(row["node_id"]): float(row["handling_capacity"])
        for _, row in net.yards_df.iterrows()
    }

    for yard_id, volume in classified.items():
        capacity = handling_capacity.get(yard_id, 0.0)
        if volume > capacity:
            result.add_violation(
                f"C3: Yard {yard_id} : {volume:.0f} wagons classifiés > "
                f"handling_capacity={capacity:.0f}"
            )


def _check_c4_min_volume(
    blocks: List[BlockDesign],
    block_route_distance: Dict[int, float],
    net: RailNetwork,
    result: ValidationResult,
) -> None:
    """
    C4 : Volume minimum par bloc selon la distance.

    Seuils :
        < 100 mi  → 5 wagons
        100-500 mi → 10 wagons
        > 500 mi  → 15 wagons

    C'est l'une des contraintes les plus souvent oubliées dans les implémentations
    naïves (Van Dyke & Meketon, 2015).
    """
    for block in blocks:
        bid = block["block_id"]
        distance = block_route_distance.get(bid, 0.0)
        vol_min = min_block_volume(net.settings, distance)
        vol = block["block_volume"]
        if vol < vol_min:
            result.add_violation(
                f"C4: Bloc {bid} ({block['from_yard_id']}→{block['to_yard_id']}) : "
                f"volume={vol} < minimum requis={vol_min} pour distance={distance:.1f} mi"
            )


def _check_c5_link_capacity(
    blocks: List[BlockDesign],
    route_by_block: Dict[int, BlockRoute],
    net: RailNetwork,
    result: ValidationResult,
) -> None:
    """
    C5 : La capacité de chaque lien physique n'est pas dépassée.

    Volume sur un lien = somme des block_volume de tous les blocs dont la route
    physique traverse ce lien (dans n'importe quel sens, le réseau étant bidirectionnel).
    """
    volume_on_link: Dict[int, float] = defaultdict(float)

    for block in blocks:
        bid = block["block_id"]
        route = route_by_block.get(bid)
        if route is None:
            continue
        link_ids = route.get("path_link_ids", [])
        for lid in link_ids:
            volume_on_link[lid] += float(block["block_volume"])

    link_capacity: Dict[int, float] = {
        int(row["link_id"]): float(row["capacity"])
        for _, row in net.links_df.iterrows()
    }

    for lid, volume in volume_on_link.items():
        capacity = link_capacity.get(lid, math.inf)
        if volume > capacity:
            result.add_violation(
                f"C5: Lien {lid} : volume={volume:.0f} > capacity={capacity:.0f}"
            )


def _check_c6_circuitous_ratio(
    blocks: List[BlockDesign],
    block_route_distance: Dict[int, float],
    net: RailNetwork,
    result: ValidationResult,
) -> None:
    """
    C6 : La route physique d'un bloc ne peut pas dépasser 1.3 × plus court chemin
    entre les yards origine et destination du bloc.

    C'est l'autre contrainte fréquemment oubliée (C4 et C6 sont les plus critiques
    selon Van Dyke & Meketon, 2015).
    """
    ratio_max = net.settings["max_circuitous_ratio"]

    for block in blocks:
        bid = block["block_id"]
        from_y = block["from_yard_id"]
        to_y = block["to_yard_id"]

        sp_dist = get_sp_distance(net, from_y, to_y)
        if math.isinf(sp_dist):
            result.add_warning(
                f"C6: Bloc {bid} : impossible de calculer le plus court chemin "
                f"{from_y}→{to_y} (yards non connectés ?)"
            )
            continue

        actual_dist = block_route_distance.get(bid, sp_dist)
        max_allowed = ratio_max * sp_dist

        if actual_dist > max_allowed + 1e-6:  # tolérance numérique
            result.add_violation(
                f"C6: Bloc {bid} ({from_y}→{to_y}) : distance réelle={actual_dist:.1f} mi "
                f"> {ratio_max} × shortest_path={sp_dist:.1f} mi = {max_allowed:.1f} mi"
            )


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _compute_block_distances(
    blocks: List[BlockDesign],
    route_by_block: Dict[int, BlockRoute],
    link_length: Dict[int, float],
    net: RailNetwork,
) -> Dict[int, float]:
    """
    Calcule la distance physique (miles) de chaque bloc depuis sa route déclarée.
    Si la route est absente, utilise le plus court chemin comme approximation.
    """
    distances: Dict[int, float] = {}
    for block in blocks:
        bid = block["block_id"]
        route = route_by_block.get(bid)
        if route and route.get("path_link_ids"):
            dist = sum(link_length.get(lid, 0.0) for lid in route["path_link_ids"])
        else:
            dist = get_sp_distance(net, block["from_yard_id"], block["to_yard_id"])
        distances[bid] = dist
    return distances
