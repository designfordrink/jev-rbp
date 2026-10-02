"""
greedy.py — Heuristique de construction greedy pour le Railroad Blocking Problem.

Algorithme : Direct Block First + Consolidation par affinité
--------------------------------------------------------------------------------
Référence : Ahuja, Jha & Liu (2007, Interfaces) — description de la baseline
industrielle CSX avant VLNS. Gap typique : 15-35% vs optimal.

Pourquoi ce solver en premier :
    1. Fournit une solution faisable en < 1 seconde (utile pour déboguer).
    2. Sert de point de départ (warm-start) pour MIP et VLNS.
    3. Pédagogique : les décisions sont traçables et compréhensibles.

Algorithme en 4 étapes :
    1. Agrégation : pour chaque paire de yards (O, D), sommer les volumes.
    2. Blocs directs : ouvrir un bloc O→D si volume ≥ min_block_vol et
       tracks disponibles à O. Trier par volume décroissant (greedy pur).
    3. Routage : construire le graphe de service (yards = nœuds, blocs = arcs),
       puis router chaque commodité sur le chemin le plus court dans ce graphe
       (en termes de nombre de sauts = minimise les reclassifications).
    4. Blocs additionnels : pour les commodités non routées, ouvrir les blocs
       manquants O→hub→D via l'heuristique "Consolidation par Affinité".
       Affinité = volume potentiel partagé sur le segment commun.

Alternatives considérées et écartées :
    - Triage par coût total (car-miles) : plus coûteux en calcul, marginal sur
      les petites instances. À envisager en Phase 4 (VLNS warm-start).
    - Ouverture séquentielle purement goulue des blocs individuels : risque de
      blocage (no-track pour les commodités restantes). Le routage via graphe
      de service est plus robuste.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

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
# Résultat du solver
# ---------------------------------------------------------------------------

@dataclass
class GreedySolution:
    """
    Solution produite par le solver greedy.

    Attributs
    ---------
    blocks    : liste des BlockDesign ouverts
    sequences : liste des BlockingSequence (une par commodité)
    routes    : liste des BlockRoute (une par bloc)
    unrouted  : commodity_ids non routés (solution infaisable si non vide)
    """
    blocks: List[BlockDesign] = field(default_factory=list)
    sequences: List[BlockingSequence] = field(default_factory=list)
    routes: List[BlockRoute] = field(default_factory=list)
    unrouted: List[int] = field(default_factory=list)

    @property
    def is_feasible(self) -> bool:
        return len(self.unrouted) == 0

    def to_solution_dict(self, net: RailNetwork) -> dict:
        """Convertit en format solution_result.json via io_json."""
        from src.io_json import build_solution_json
        return build_solution_json(net, self.blocks, self.sequences, self.routes)


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def solve_greedy(net: RailNetwork) -> GreedySolution:
    """
    Résout le Railroad Blocking Problem avec l'heuristique Direct Block First.

    Paramètres
    ----------
    net : RailNetwork chargé par data_loader.load_rail_network()

    Retourne
    --------
    GreedySolution avec blocks, sequences, routes et unrouted.

    Complexité : O(K × Y²) où K = commodités, Y = yards.
    Sur l'instance jouet (50 × 64) → négligeable.
    # PERFORMANCE: pour >10 000 commodités, filtrer les hubs candidats.
    """
    # --- Étape 1 : Agrégation des volumes par paire de yards ---
    od_volumes: Dict[Tuple[int, int], float] = _aggregate_od_volumes(net)

    # --- Étape 2 : Blocs directs ---
    # outgoing_count : nb de blocs sortants déjà ouverts par yard
    outgoing_count: Dict[int, int] = defaultdict(int)
    blocks: List[BlockDesign] = []
    block_id_counter = [1]  # compteur mutable via liste (évite global)

    block_by_od: Dict[Tuple[int, int], BlockDesign] = {}

    _open_direct_blocks(
        od_volumes, net, blocks, block_by_od, outgoing_count, block_id_counter
    )

    # --- Étape 3 : Construction du graphe de service ---
    # Nœuds = yards, arcs = blocs ouverts (avec poids = distance physique du bloc).
    # On utilise le nombre de sauts comme métrique primaire pour minimiser
    # les reclassifications (chaque saut = coût de manutention supplémentaire).
    service_graph = _build_service_graph(blocks)

    # --- Étape 4 : Routage des commodités ---
    sequences: List[BlockingSequence] = []
    unrouted: List[int] = []

    for _, row in net.demands_df.iterrows():
        cid = int(row["commodity_id"])
        origin = int(row["origin_yard_id"])
        dest = int(row["dest_yard_id"])
        volume = float(row["volume"])
        ctype = str(row["commodity_type"])

        path_blocks = _route_commodity(origin, dest, service_graph, block_by_od)

        if path_blocks is None:
            # Tentative : ouvrir des blocs additionnels via consolidation
            path_blocks = _consolidate_open_blocks(
                cid, origin, dest, volume, ctype,
                od_volumes, net, blocks, block_by_od,
                outgoing_count, block_id_counter, service_graph
            )

        if path_blocks is None:
            unrouted.append(cid)
            continue

        sequences.append({
            "commodity_id": cid,
            "commodity_type": ctype,
            "origin_yard_id": origin,
            "dest_yard_id": dest,
            "volume": volume,
            "blocking_sequence_ids": path_blocks,
            "blocking_sequence": " -> ".join(str(b) for b in path_blocks),
        })

    # --- Étape 5 : Mise à jour des volumes de blocs ---
    # Les volumes de blocs sont la somme des commodités routées via ce bloc.
    _recompute_block_volumes(blocks, sequences)

    # --- Étape 6 : Routes physiques (plus court chemin) ---
    routes = _build_physical_routes(blocks, net)

    return GreedySolution(
        blocks=blocks,
        sequences=sequences,
        routes=routes,
        unrouted=unrouted,
    )


# ---------------------------------------------------------------------------
# Étape 1 : Agrégation
# ---------------------------------------------------------------------------

def _aggregate_od_volumes(net: RailNetwork) -> Dict[Tuple[int, int], float]:
    """
    Somme les volumes de toutes les commodités par paire (origin_yard, dest_yard).
    Retourne un dict {(o, d): volume_total}.
    """
    od_volumes: Dict[Tuple[int, int], float] = defaultdict(float)
    for _, row in net.demands_df.iterrows():
        key = (int(row["origin_yard_id"]), int(row["dest_yard_id"]))
        od_volumes[key] += float(row["volume"])
    return dict(od_volumes)


# ---------------------------------------------------------------------------
# Étape 2 : Blocs directs
# ---------------------------------------------------------------------------

def _open_direct_blocks(
    od_volumes: Dict[Tuple[int, int], float],
    net: RailNetwork,
    blocks: List[BlockDesign],
    block_by_od: Dict[Tuple[int, int], BlockDesign],
    outgoing_count: Dict[int, int],
    block_id_counter: List[int],
) -> None:
    """
    Ouvre un bloc direct O→D pour chaque paire de yards avec volume suffisant
    et tracks disponibles. Trie par volume décroissant (greedy pur).

    Pourquoi volume décroissant :
        Les paires à fort volume ont le plus de chances de satisfaire C4
        et génèrent les plus grandes économies de coût fixe unitaire.

    Contraintes vérifiées ici :
        C2 : outgoing_count[O] < num_tracks[O]
        C4 : volume ≥ min_block_volume(distance)
        Commodity type : intermodal/auto → bloc direct uniquement (déjà satisfait ici)
    """
    num_tracks: Dict[int, int] = {
        int(row["node_id"]): int(row["num_tracks"])
        for _, row in net.yards_df.iterrows()
    }

    # Déterminer le type de commodité dominant par paire OD
    od_type = _dominant_commodity_type(net)

    # Trier par volume décroissant
    sorted_od = sorted(od_volumes.items(), key=lambda x: -x[1])

    for (origin, dest), volume in sorted_od:
        # Vérifier la contrainte de tracks (C2)
        ctype = od_type.get((origin, dest), "Merchandise")

        # HYPOTHÈSE: Intermodal et Automobile sont exempts de num_tracks.
        # Merchandise et Coal/Grain sont soumis à num_tracks.
        tracks_limited = ctype in {"Merchandise", "Coal", "Grain"}
        if tracks_limited:
            max_tracks = num_tracks.get(origin, 0)
            if outgoing_count[origin] >= max_tracks:
                continue  # yard saturé → skip ce bloc direct

        # Vérifier la contrainte de volume minimum (C4)
        sp_dist = get_sp_distance(net, origin, dest)
        if math.isinf(sp_dist):
            continue  # OD non connecté dans le réseau physique

        vol_min = min_block_volume(net.settings, sp_dist)
        if volume < vol_min:
            continue  # volume insuffisant pour un bloc direct

        # Ouvrir le bloc
        bid = block_id_counter[0]
        block_id_counter[0] += 1

        block: BlockDesign = {
            "block_id": bid,
            "from_yard_id": origin,
            "to_yard_id": dest,
            "commodity_type": ctype,
            "block_volume": volume,  # sera recalculé après routage (étape 5)
        }
        blocks.append(block)
        block_by_od[(origin, dest)] = block

        if tracks_limited:
            outgoing_count[origin] += 1


def _dominant_commodity_type(net: RailNetwork) -> Dict[Tuple[int, int], str]:
    """
    Pour chaque paire OD, retourne le type de commodité avec le plus grand volume.
    Utilisé pour affecter le bon type à chaque bloc (important pour C2).

    # SIMPLIFICATION: un bloc ne peut transporter qu'un seul type de commodité.
    # Si plusieurs types coexistent sur une paire OD, on prend le type dominant.
    # TODO: dans les grandes instances, séparer les blocs par type si nécessaire.
    """
    od_type_vol: Dict[Tuple[int, int], Dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for _, row in net.demands_df.iterrows():
        key = (int(row["origin_yard_id"]), int(row["dest_yard_id"]))
        od_type_vol[key][str(row["commodity_type"])] += float(row["volume"])

    return {
        od: max(type_vol, key=type_vol.get)
        for od, type_vol in od_type_vol.items()
    }


# ---------------------------------------------------------------------------
# Étape 3 : Graphe de service
# ---------------------------------------------------------------------------

def _build_service_graph(blocks: List[BlockDesign]) -> nx.DiGraph:
    """
    Construit un graphe de service orienté à partir des blocs ouverts.

    Nœuds : yards (from_yard_id et to_yard_id de chaque bloc)
    Arcs  : (from_yard, to_yard) avec attribut block_id

    Pourquoi DiGraph (orienté) : les blocs ont une direction fixe O→D.
    Un routage sur ce graphe garantit des séquences sans aller-retour.
    """
    G = nx.DiGraph()
    for block in blocks:
        G.add_edge(
            block["from_yard_id"],
            block["to_yard_id"],
            block_id=block["block_id"],
        )
    return G


# ---------------------------------------------------------------------------
# Étape 4a : Routage d'une commodité sur le graphe de service
# ---------------------------------------------------------------------------

def _route_commodity(
    origin: int,
    dest: int,
    service_graph: nx.DiGraph,
    block_by_od: Dict[Tuple[int, int], BlockDesign],
) -> Optional[List[int]]:
    """
    Trouve le chemin de blocs le plus court (en nb de sauts) de origin à dest
    dans le graphe de service.

    Retourne la liste de block_ids dans l'ordre, ou None si aucun chemin.

    Pourquoi nb de sauts comme métrique :
        Chaque saut = une reclassification supplémentaire (coût de manutention).
        Minimiser les sauts minimise approximativement le coût de manutention.
        La minimisation des car-miles est gérée par le choix de la route physique.
    """
    if not service_graph.has_node(origin) or not service_graph.has_node(dest):
        return None

    try:
        node_path = nx.shortest_path(service_graph, origin, dest)
    except nx.NetworkXNoPath:
        return None

    # Convertir le chemin de nœuds en liste de block_ids
    block_ids = []
    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i + 1]
        block = block_by_od.get((u, v))
        if block is None:
            return None  # arc présent dans le graphe mais bloc manquant (incohérence)
        block_ids.append(block["block_id"])

    return block_ids if block_ids else None


# ---------------------------------------------------------------------------
# Étape 4b : Consolidation par affinité (blocs additionnels)
# ---------------------------------------------------------------------------

def _consolidate_open_blocks(
    cid: int,
    origin: int,
    dest: int,
    volume: float,
    ctype: str,
    od_volumes: Dict[Tuple[int, int], float],
    net: RailNetwork,
    blocks: List[BlockDesign],
    block_by_od: Dict[Tuple[int, int], BlockDesign],
    outgoing_count: Dict[int, int],
    block_id_counter: List[int],
    service_graph: nx.DiGraph,
) -> Optional[List[int]]:
    """
    Tente de router une commodité non routée en ouvrant les blocs manquants
    via l'heuristique "Consolidation par Affinité".

    Stratégie (1-hop uniquement) :
        Pour chaque yard hub H ≠ O, D :
            Score_affinité(H) = od_volumes.get((O,H), 0) + od_volumes.get((H,D), 0)
        Tester les hubs par score décroissant. Pour le premier hub H faisable :
            - Ouvrir le bloc O→H si manquant et faisable
            - Ouvrir le bloc H→D si manquant et faisable
            - Router la commodité sur O→H→D

    Pourquoi affinité = somme des volumes :
        Un hub concentrant beaucoup de flux O→H et H→D permet d'amortir les
        coûts fixes sur de nombreuses commodités (principe du hub-and-spoke).
        Ahuja (2007) appelle cela "Consolidation by Geographic Affinity".

    # LIMITE: ne teste que les chemins à 1 hub. Les chemins à 2+ hubs sont
    # rarissimes sur l'instance jouet mais fréquents sur le US National Model.
    # TODO Phase 4 (VLNS): explorer des voisinages à k hubs (k=2,3).
    """
    num_tracks: Dict[int, int] = {
        int(row["node_id"]): int(row["num_tracks"])
        for _, row in net.yards_df.iterrows()
    }

    tracks_limited = ctype in {"Merchandise", "Coal", "Grain"}

    # HYPOTHÈSE: Intermodal/Automobile ne peuvent pas avoir de hub intermédiaire.
    # Ils exigent un bloc direct → si le bloc direct n'a pas été ouvert (volume
    # insuffisant), la commodité reste non routée.
    if ctype in {"Intermodal", "Automobile"}:
        return None

    # Évaluer tous les hubs candidats (yards distincts de O et D)
    hub_scores: List[Tuple[float, int]] = []
    for hub in net.yard_ids:
        if hub in (origin, dest):
            continue
        score = od_volumes.get((origin, hub), 0.0) + od_volumes.get((hub, dest), 0.0)
        hub_scores.append((score, hub))

    hub_scores.sort(reverse=True)  # hubs les plus affins en premier

    for _, hub in hub_scores:
        # Vérifier si le segment O→hub est faisable
        ok_oh = _can_open_block(
            origin, hub, ctype, tracks_limited, num_tracks,
            outgoing_count, net
        )
        # Vérifier si le segment hub→D est faisable (ou déjà ouvert)
        ok_hd = _can_open_block(
            hub, dest, ctype, tracks_limited, num_tracks,
            outgoing_count, net
        )

        if not (ok_oh and ok_hd):
            continue

        # Ouvrir les blocs manquants et mettre à jour le graphe de service
        if (origin, hub) not in block_by_od:
            b = _open_block(
                origin, hub, ctype, od_volumes.get((origin, hub), volume),
                tracks_limited, blocks, block_by_od,
                outgoing_count, block_id_counter
            )
            service_graph.add_edge(origin, hub, block_id=b["block_id"])

        if (hub, dest) not in block_by_od:
            b = _open_block(
                hub, dest, ctype, od_volumes.get((hub, dest), volume),
                tracks_limited, blocks, block_by_od,
                outgoing_count, block_id_counter
            )
            service_graph.add_edge(hub, dest, block_id=b["block_id"])

        # Router la commodité sur ce chemin à 2 blocs
        bid_oh = block_by_od[(origin, hub)]["block_id"]
        bid_hd = block_by_od[(hub, dest)]["block_id"]
        return [bid_oh, bid_hd]

    return None  # aucun hub faisable trouvé


def _can_open_block(
    from_yard: int,
    to_yard: int,
    ctype: str,
    tracks_limited: bool,
    num_tracks: Dict[int, int],
    outgoing_count: Dict[int, int],
    net: RailNetwork,
) -> bool:
    """
    Retourne True si le bloc (from_yard, to_yard) peut être ouvert.
    Vérifie tracks disponibles et connectivité physique.
    Ignore C4 (volume min) car le volume sera reconsolidé après.
    """
    # Bloc déjà ouvert → toujours OK (on ajoute juste du volume)
    from src.io_json import BlockDesign  # import local pour éviter import circulaire
    # (vérifié via block_by_od dans l'appelant)

    # Connectivité physique
    sp = get_sp_distance(net, from_yard, to_yard)
    if math.isinf(sp):
        return False

    # Tracks disponibles
    if tracks_limited:
        limit = num_tracks.get(from_yard, 0)
        if outgoing_count[from_yard] >= limit:
            return False

    return True


def _open_block(
    from_yard: int,
    to_yard: int,
    ctype: str,
    volume: float,
    tracks_limited: bool,
    blocks: List[BlockDesign],
    block_by_od: Dict[Tuple[int, int], BlockDesign],
    outgoing_count: Dict[int, int],
    block_id_counter: List[int],
) -> BlockDesign:
    """
    Ouvre un nouveau bloc et met à jour les structures de suivi.
    Pré-condition : le bloc n'existe pas encore dans block_by_od.
    """
    bid = block_id_counter[0]
    block_id_counter[0] += 1
    block: BlockDesign = {
        "block_id": bid,
        "from_yard_id": from_yard,
        "to_yard_id": to_yard,
        "commodity_type": ctype,
        "block_volume": max(volume, 0.0),
    }
    blocks.append(block)
    block_by_od[(from_yard, to_yard)] = block
    if tracks_limited:
        outgoing_count[from_yard] += 1
    return block


# ---------------------------------------------------------------------------
# Étape 5 : Mise à jour des volumes de blocs
# ---------------------------------------------------------------------------

def _recompute_block_volumes(
    blocks: List[BlockDesign],
    sequences: List[BlockingSequence],
) -> None:
    """
    Recalcule le volume de chaque bloc comme la somme des commodités routées via lui.

    Pourquoi recalculer :
        Les volumes initiaux sont des estimations agrégées (Step 1).
        Après le routage des commodités, certains blocs peuvent recevoir des
        commodités de paires OD différentes (via les hubs). Le volume réel
        = somme des wagons effectivement routés.
    """
    volume_by_bid: Dict[int, float] = defaultdict(float)
    for seq in sequences:
        for bid in seq["blocking_sequence_ids"]:
            volume_by_bid[bid] += seq["volume"]

    for block in blocks:
        block["block_volume"] = volume_by_bid.get(block["block_id"], 0.0)


# ---------------------------------------------------------------------------
# Étape 6 : Routes physiques
# ---------------------------------------------------------------------------

def _build_physical_routes(
    blocks: List[BlockDesign],
    net: RailNetwork,
) -> List[BlockRoute]:
    """
    Attribue à chaque bloc sa route physique = plus court chemin Dijkstra
    entre from_yard et to_yard sur le réseau physique.

    Pourquoi le plus court chemin :
        C'est la route qui minimise les car-miles (composante majeure du coût
        de transport). Elle garantit aussi le respect de C6 (ratio de détour ≤ 1.3
        pour k = 1.0, ce qui est trivial puisque la route EST le plus court chemin).

    Les link_ids sont déduits des arêtes successives dans le graphe physique.
    """
    routes: List[BlockRoute] = []

    for block in blocks:
        from_y = block["from_yard_id"]
        to_y = block["to_yard_id"]

        path_nodes = get_sp_path(net, from_y, to_y)
        if not path_nodes:
            # Fallback : route directe si les yards sont voisins dans le graphe
            if net.graph.has_edge(from_y, to_y):
                path_nodes = [from_y, to_y]
            else:
                path_nodes = [from_y, to_y]  # déclaré mais invalide → sera détecté par validator

        # Reconstituer les link_ids depuis les arêtes successives
        path_links = []
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            lid = get_link_id(net.graph, u, v)
            if lid is not None:
                path_links.append(lid)

        routes.append({
            "block_id": block["block_id"],
            "from_yard_id": from_y,
            "to_yard_id": to_y,
            "path_node_ids": path_nodes,
            "path_link_ids": path_links,
            "physical_path_nodes": " -> ".join(str(n) for n in path_nodes),
            "physical_path_links": " -> ".join(str(l) for l in path_links),
        })

    return routes
