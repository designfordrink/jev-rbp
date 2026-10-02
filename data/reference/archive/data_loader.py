"""
data_loader.py — Chargement des données GMNS et construction du graphe physique.

Pourquoi ce module :
    Centraliser le parsing des CSV (nodes, links, demands, settings) en un seul endroit
    réutilisable par tous les solvers. Chaque module dépendant reçoit un objet RailNetwork
    plutôt que de lire les fichiers lui-même, ce qui garantit la cohérence des données.

Référence format : GMNS (General Modeling Network Specification)
    https://github.com/zephyr-data-specs/GMNS

Alternatives considérées et écartées :
    - SQLite : overkill pour 13 nœuds / 50 commodités, inutile sur l'instance jouet
    - ORTools GraphWrapper : couplage fort avec un solveur spécifique, à éviter
    - igraph : plus rapide en boucle interne, mais NetworkX.from_networkx() est compatible
      PyTorch Geometric. On utilisera igraph uniquement en Phase 4 (VLNS) via conversion.
      # PERFORMANCE: basculer vers igraph si >1000 yards en Phase 6 (US National Model)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import pandas as pd


# ---------------------------------------------------------------------------
# Constantes par défaut (écrasées par setting.csv si présentes)
# ---------------------------------------------------------------------------

# HYPOTHÈSE: valeurs issues de l'instance jouet ; les grandes instances peuvent différer.
DEFAULT_SETTINGS = {
    "min_block_vol_short(<100mi)": 5.0,   # C4 : wagons minimum, bloc < 100 miles
    "min_block_vol_med(100-500mi)": 10.0, # C4 : wagons minimum, bloc 100-500 miles
    "min_block_vol_long(>500mi)": 15.0,   # C4 : wagons minimum, bloc > 500 miles
    "max_circuitous_ratio": 1.3,          # C6 : ratio détour max vs plus court chemin
    "operating_cycle": 70.0,              # jours (période d'évaluation)
    "block_fixed_cost": 2500.0,           # $/bloc ouvert
    "transport_cost_coefficient": 1.0,    # $/car-mile
    "interchange_cost": 1.0,              # $/voiture en interchange (multi-RR)
}


# ---------------------------------------------------------------------------
# Dataclass principale
# ---------------------------------------------------------------------------

@dataclass
class RailNetwork:
    """
    Conteneur principal pour toutes les données du problème.

    Tous les modules (validator, evaluator, solvers) reçoivent cette structure
    au lieu de lire les CSV directement, garantissant une source de vérité unique.

    Attributs
    ---------
    settings : dict
        Paramètres globaux (coûts, ratios, volumes min, cycle).
    nodes_df : DataFrame
        Tous les nœuds (yards + stations), colonnes GMNS.
    yards_df : DataFrame
        Sous-ensemble des nœuds de type "yard" uniquement.
    links_df : DataFrame
        Arcs physiques du réseau, colonnes GMNS.
    demands_df : DataFrame
        50 commodités (id, origin, dest, volume, type).
    graph : nx.Graph
        Graphe physique NON-ORIENTÉ (les arcs sont bidirectionnels dans l'instance jouet).
        Poids 'length' en miles. Attributs de nœuds issus de nodes_df.
        # HYPOTHÈSE: bidirectionnel car la solution exemple traverse des arcs en sens inverse.
        # TODO: vérifier avec de grandes instances si le réseau physique peut être dirigé.
    shortest_paths : dict
        {(from_yard_id, to_yard_id): {"distance": float, "path": [node_id, ...]}}
        Pré-calculé pour toutes les paires de yards via Dijkstra (poids 'length').
        Sert à valider C6 (ratio de détour) et à construire les routes physiques.
    yard_ids : set[int]
        Ensemble des node_id de type "yard".
    station_ids : set[int]
        Ensemble des node_id de type "station".
    flat_yard_ids : set[int]
        Yards de type "flat" — seul type autorisé pour Intermodal et Automobile (C7).
    hump_yard_ids : set[int]
        Yards de type "hump" — autorisés pour Merchandise.
    """

    settings: Dict[str, float]
    nodes_df: pd.DataFrame
    yards_df: pd.DataFrame
    links_df: pd.DataFrame
    demands_df: pd.DataFrame
    graph: nx.Graph
    shortest_paths: Dict[Tuple[int, int], Dict] = field(default_factory=dict)
    yard_ids: Set[int] = field(default_factory=set)
    station_ids: Set[int] = field(default_factory=set)
    flat_yard_ids: Set[int] = field(default_factory=set)
    hump_yard_ids: Set[int] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Fonctions de chargement
# ---------------------------------------------------------------------------

def load_settings(path: Path) -> Dict[str, float]:
    """
    Lit setting.csv et retourne un dict {paramètre: valeur}.

    Les paramètres manquants sont complétés par DEFAULT_SETTINGS pour garantir
    que le code reste fonctionnel si le fichier est incomplet.

    Pourquoi pd.read_csv et non configparser : le format GMNS utilise CSV, et
    on veut rester cohérent avec le format des autres fichiers du dataset.
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    settings = dict(DEFAULT_SETTINGS)
    for _, row in df.iterrows():
        key = str(row["Parameter"]).strip()
        try:
            settings[key] = float(row["Value"])
        except (ValueError, TypeError):
            pass  # conserver la valeur par défaut si la cellule est vide/invalide

    return settings


def load_nodes(path: Path) -> pd.DataFrame:
    """
    Lit nodes.csv.

    Nettoyage :
    - Les stations ont yard_type, yard_level = NaN (not applicable dans GMNS).
    - is_interchange : convertie en bool Python (la valeur est "TRUE"/"FALSE" en CSV).
    - handling_cost : 0 pour les stations (elles n'ont pas de triage).
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    # Normaliser is_interchange en bool
    df["is_interchange"] = df["is_interchange"].map(
        lambda v: str(v).strip().upper() == "TRUE" if pd.notna(v) else False
    )

    # node_id doit être int pour cohérence avec la solution JSON
    df["node_id"] = df["node_id"].astype(int)

    return df


def load_links(path: Path) -> pd.DataFrame:
    """
    Lit links.csv.

    HYPOTHÈSE: les liens physiques sont bidirectionnels (la solution exemple
    traverse des arcs en sens inverse de leur définition CSV, ex. bloc 25 utilise
    link 5 de 11018→10002 alors que link 5 est défini de 10002→11018).
    On stocke quand même la direction CSV pour référence, mais le graphe est Graph().
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df["from_node_id"] = df["from_node_id"].astype(int)
    df["to_node_id"] = df["to_node_id"].astype(int)
    df["link_id"] = df["link_id"].astype(int)
    return df


def load_demands(path: Path) -> pd.DataFrame:
    """
    Lit demands.csv.

    commodity_type est une chaîne : "Merchandise", "Intermodal", "Automobile",
    "Coal", "Grain". Toutes les commodités de l'instance jouet sont Merchandise.
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df["commodity_id"] = df["commodity_id"].astype(int)
    df["origin_yard_id"] = df["origin_yard_id"].astype(int)
    df["dest_yard_id"] = df["dest_yard_id"].astype(int)
    df["volume"] = df["volume"].astype(float)
    return df


def _build_graph(nodes_df: pd.DataFrame, links_df: pd.DataFrame) -> nx.Graph:
    """
    Construit le graphe physique NON-ORIENTÉ depuis nodes_df et links_df.

    Pourquoi non-orienté :
        L'instance exemple montre des blocs circulant dans les deux sens sur les
        mêmes liens physiques. Le GMNS ne précise pas d'interdiction de sens,
        et la solution de référence confirme la bidirectionnalité.

    Attributs de nœuds ajoutés : tous les champs de nodes_df.
    Attributs d'arêtes ajoutés : link_id, length, capacity, railroad_id, free_speed.

    # LIMITE: si de futures instances ont des liens unidirectionnels, il faudra
    # basculer sur nx.DiGraph et adapter le calcul de plus court chemin.
    """
    G = nx.Graph()

    # Ajouter les nœuds avec tous leurs attributs
    for _, row in nodes_df.iterrows():
        G.add_node(int(row["node_id"]), **row.to_dict())

    # Ajouter les arêtes (bidirectionnelles)
    for _, row in links_df.iterrows():
        G.add_edge(
            int(row["from_node_id"]),
            int(row["to_node_id"]),
            link_id=int(row["link_id"]),
            length=float(row["length"]),
            capacity=float(row["capacity"]),
            railroad_id=str(row["railroad_id"]),
            free_speed=float(row["free_speed"]),
        )

    return G


def _precompute_shortest_paths(
    graph: nx.Graph,
    yard_ids: Set[int],
) -> Dict[Tuple[int, int], Dict]:
    """
    Pré-calcule les plus courts chemins (en miles) entre toutes les paires de yards.

    Algorithme : Dijkstra avec weight='length'.
    Pourquoi Dijkstra et non Bellman-Ford : toutes les distances sont positives
    (miles), donc Dijkstra est optimal en O((V+E) log V).

    Retourne un dict :
        {(from_yard_id, to_yard_id): {"distance": float, "path": [node_id, ...]}}

    Note : les chemins incluent tous les nœuds intermédiaires (stations incluses),
    pas uniquement les yards.

    # PERFORMANCE: sur le US National Model (>1000 yards), pré-calculer seulement
    # les paires réellement utilisées par les commodités ou utiliser all_pairs_dijkstra
    # en parallèle. Sur l'instance jouet (8 yards), le coût est négligeable.
    """
    sp: Dict[Tuple[int, int], Dict] = {}
    yard_list = list(yard_ids)

    for src in yard_list:
        if src not in graph:
            continue
        # Dijkstra depuis src vers tous les nœuds atteignables
        lengths, paths = nx.single_source_dijkstra(
            graph, src, weight="length"
        )
        for dst in yard_list:
            if dst == src:
                continue
            if dst in lengths:
                sp[(src, dst)] = {
                    "distance": lengths[dst],
                    "path": paths[dst],
                }
            else:
                # LIMITE: yard non atteignable depuis src (réseau déconnecté)
                sp[(src, dst)] = {"distance": math.inf, "path": []}

    return sp


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def load_rail_network(data_dir: str | Path) -> RailNetwork:
    """
    Point d'entrée unique : charge tous les fichiers CSV d'un répertoire de données
    et retourne un objet RailNetwork prêt à l'emploi.

    Paramètres
    ----------
    data_dir : str ou Path
        Répertoire contenant nodes.csv, links.csv, demands.csv, setting.csv.

    Retourne
    --------
    RailNetwork
        Objet complet avec graphe et plus courts chemins pré-calculés.

    Exemple
    -------
    >>> net = load_rail_network("data/")
    >>> len(net.yards_df)
    8
    >>> net.settings["block_fixed_cost"]
    2500.0
    """
    data_dir = Path(data_dir)

    settings = load_settings(data_dir / "setting.csv")
    nodes_df = load_nodes(data_dir / "nodes.csv")
    links_df = load_links(data_dir / "links.csv")
    demands_df = load_demands(data_dir / "demands.csv")

    # Segmentation yards / stations
    yards_df = nodes_df[nodes_df["node_type"] == "yard"].copy()
    yard_ids = set(yards_df["node_id"].tolist())
    station_ids = set(
        nodes_df[nodes_df["node_type"] == "station"]["node_id"].tolist()
    )

    # Sous-ensembles par type de yard
    flat_yard_ids = set(
        yards_df[yards_df["yard_type"] == "flat"]["node_id"].tolist()
    )
    hump_yard_ids = set(
        yards_df[yards_df["yard_type"] == "hump"]["node_id"].tolist()
    )

    # Construction du graphe physique
    graph = _build_graph(nodes_df, links_df)

    # Pré-calcul des plus courts chemins inter-yards
    shortest_paths = _precompute_shortest_paths(graph, yard_ids)

    return RailNetwork(
        settings=settings,
        nodes_df=nodes_df,
        yards_df=yards_df,
        links_df=links_df,
        demands_df=demands_df,
        graph=graph,
        shortest_paths=shortest_paths,
        yard_ids=yard_ids,
        station_ids=station_ids,
        flat_yard_ids=flat_yard_ids,
        hump_yard_ids=hump_yard_ids,
    )


# ---------------------------------------------------------------------------
# Helpers pratiques (utilisés par validator et evaluator)
# ---------------------------------------------------------------------------

def get_link_id(
    graph: nx.Graph,
    from_node: int,
    to_node: int,
) -> Optional[int]:
    """
    Retourne le link_id de l'arête (from_node, to_node), ou None si inexistante.
    Fonctionne dans les deux sens (graphe non-orienté).
    """
    if graph.has_edge(from_node, to_node):
        return graph[from_node][to_node]["link_id"]
    return None


def get_sp_distance(
    net: RailNetwork,
    from_yard: int,
    to_yard: int,
) -> float:
    """
    Retourne la distance (miles) du plus court chemin entre deux yards.
    Retourne math.inf si les yards ne sont pas connectés.
    """
    entry = net.shortest_paths.get((from_yard, to_yard))
    return entry["distance"] if entry else math.inf


def get_sp_path(
    net: RailNetwork,
    from_yard: int,
    to_yard: int,
) -> List[int]:
    """
    Retourne la liste ordonnée de node_ids du plus court chemin entre deux yards.
    Retourne [] si les yards ne sont pas connectés.
    """
    entry = net.shortest_paths.get((from_yard, to_yard))
    return entry["path"] if entry else []


def min_block_volume(settings: Dict[str, float], distance_miles: float) -> float:
    """
    Retourne le volume minimum requis pour ouvrir un bloc, selon la distance (C4).

    Seuils (instance jouet, confirmés par setting.csv) :
        < 100 mi  → 5 wagons
        100-500 mi → 10 wagons
        > 500 mi  → 15 wagons
    """
    if distance_miles < 100.0:
        return settings["min_block_vol_short(<100mi)"]
    elif distance_miles <= 500.0:
        return settings["min_block_vol_med(100-500mi)"]
    else:
        return settings["min_block_vol_long(>500mi)"]
