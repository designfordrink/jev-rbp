"""
io_json.py — Lecture et écriture du format solution_result.json.

Pourquoi ce module :
    Le format de sortie attendu par la compétition a une structure précise
    (inputs + outputs avec 3 sections numérotées). Centraliser la sérialisation
    ici évite de dupliquer la logique de parsing dans chaque solver.

Format de référence : data/solution_result.json fourni par les organisateurs.

Note sur NaN :
    Le fichier de référence contient des `NaN` (valeurs Python/pandas non-standard
    en JSON) pour les champs non applicables des stations (yard_type, yard_level).
    Le module json de Python les accepte en lecture ET les écrit comme `NaN`.
    Ce comportement non-standard est intentionnellement conservé pour rester
    compatible avec le format attendu par les organisateurs.
    # LIMITE: si un parseur JSON strict est utilisé en validation, NaN sera rejeté.
    # TODO: proposer une option allow_nan=False qui substitue null à NaN.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.data_loader import RailNetwork


# ---------------------------------------------------------------------------
# Types de la solution (structure logique)
# ---------------------------------------------------------------------------

# Un bloc ouvert dans le plan de blocking.
#   block_id       : identifiant unique attribué par le solver
#   from_yard_id   : yard d'origine du bloc
#   to_yard_id     : yard de destination du bloc
#   commodity_type : "Merchandise" | "Intermodal" | "Automobile" | "Coal" | "Grain"
#   block_volume   : volume total (wagons) consolidé dans ce bloc
BlockDesign = Dict[str, Any]

# La séquence de blocs empruntée par une commodité.
#   commodity_id      : id de la commodité
#   commodity_type    : type
#   origin_yard_id    : yard origine de la commodité
#   dest_yard_id      : yard destination de la commodité
#   volume            : volume de la commodité (wagons)
#   blocking_sequence : chaîne "block_id1 -> block_id2 -> ..." ou "block_id" si direct
BlockingSequence = Dict[str, Any]

# La route physique (sur le réseau ferroviaire) d'un bloc.
#   block_id             : id du bloc
#   from_yard_id         : yard origine
#   to_yard_id           : yard destination
#   physical_path_nodes  : chaîne "node_id1 -> node_id2 -> ..."
#   physical_path_links  : chaîne "link_id1 -> link_id2 -> ..."
BlockRoute = Dict[str, Any]


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def load_solution(path: str | Path) -> Dict[str, Any]:
    """
    Lit solution_result.json et retourne le dict Python brut.

    Le fichier peut contenir des NaN (non-standard JSON) — Python les accepte.
    Aucune transformation n'est appliquée ici ; utiliser parse_solution() pour
    obtenir les listes typées.

    Paramètres
    ----------
    path : str ou Path
        Chemin vers solution_result.json.

    Retourne
    --------
    dict avec clés "inputs" et "outputs".
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_outputs(solution: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait et normalise la section "outputs" d'une solution chargée.

    Retourne un dict avec :
        "blocks"    : List[BlockDesign]
        "sequences" : List[BlockingSequence]
        "routes"    : List[BlockRoute]

    La clé "blocking_sequence" est normalisée en liste d'entiers pour faciliter
    le traitement algorithmique (le format JSON stocke "10 -> 28" en chaîne).
    """
    outputs = solution.get("outputs", {})

    # --- Bloc Design ---
    blocks: List[BlockDesign] = outputs.get("1 Block Design", [])

    # --- Blocking Sequence : parse "10 -> 28" → [10, 28] ---
    raw_sequences = outputs.get("2 Blocking Sequence", [])
    sequences: List[BlockingSequence] = []
    for seq in raw_sequences:
        entry = dict(seq)
        raw_str = str(seq.get("blocking_sequence", "")).strip()
        entry["blocking_sequence_ids"] = _parse_arrow_list(raw_str, dtype=int)
        sequences.append(entry)

    # --- Block Route : parse nœuds et liens ---
    raw_routes = outputs.get("3 Block Route", [])
    routes: List[BlockRoute] = []
    for route in raw_routes:
        entry = dict(route)
        node_str = str(route.get("physical_path_nodes", "")).strip()
        link_str = str(route.get("physical_path_links", "")).strip()
        entry["path_node_ids"] = _parse_arrow_list(node_str, dtype=int)
        entry["path_link_ids"] = _parse_arrow_list(link_str, dtype=int)
        routes.append(entry)

    return {"blocks": blocks, "sequences": sequences, "routes": routes}


def _parse_arrow_list(s: str, dtype=int) -> List:
    """
    Convertit une chaîne "10 -> 28 -> 7" en [10, 28, 7].
    Retourne [] si la chaîne est vide ou invalide.
    """
    if not s or s in ("nan", "NaN", "None", ""):
        return []
    parts = [p.strip() for p in s.split("->")]
    result = []
    for p in parts:
        try:
            result.append(dtype(p))
        except (ValueError, TypeError):
            pass
    return result


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

def build_solution_json(
    net: RailNetwork,
    blocks: List[BlockDesign],
    sequences: List[BlockingSequence],
    routes: List[BlockRoute],
) -> Dict[str, Any]:
    """
    Construit le dict solution_result.json complet à partir des outputs du solver.

    La section "inputs" est reconstruite depuis l'objet RailNetwork pour
    garantir la cohérence avec les données source.

    Paramètres
    ----------
    net       : RailNetwork chargé par data_loader.load_rail_network()
    blocks    : liste de BlockDesign (sortie du solver)
    sequences : liste de BlockingSequence (sortie du solver)
    routes    : liste de BlockRoute (sortie du solver)

    Retourne
    --------
    dict prêt à être sérialisé en JSON.
    """
    return {
        "inputs": _build_inputs_section(net),
        "outputs": {
            "1 Block Design": blocks,
            "2 Blocking Sequence": [_format_sequence(s) for s in sequences],
            "3 Block Route": [_format_route(r) for r in routes],
        },
    }


def save_solution(solution: Dict[str, Any], path: str | Path) -> None:
    """
    Écrit solution_result.json sur disque.

    Utilise indent=4 pour la lisibilité (conforme au format de référence).
    allow_nan=True pour conserver les NaN des stations.

    Paramètres
    ----------
    solution : dict retourné par build_solution_json()
    path     : chemin de sortie (sera créé / écrasé)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(solution, f, indent=4, allow_nan=True)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _build_inputs_section(net: RailNetwork) -> Dict[str, Any]:
    """
    Reconstruit la section "inputs" du JSON depuis les DataFrames de RailNetwork.
    Les NaN pandas sont conservés tels quels (non convertis en null) pour compatibilité.
    """
    # Settings
    settings_dict = dict(net.settings)

    # Nodes : convertir DataFrame → liste de dicts ; les NaN restent NaN
    nodes_records = net.nodes_df.to_dict(orient="records")
    # Convertir numpy types → Python natifs pour json.dump
    nodes_clean = [_clean_record(r) for r in nodes_records]

    # Demands
    demands_records = net.demands_df.to_dict(orient="records")
    demands_clean = [_clean_record(r) for r in demands_records]

    # Links
    links_records = net.links_df.to_dict(orient="records")
    links_clean = [_clean_record(r) for r in links_records]

    return {
        "settings": settings_dict,
        "nodes": nodes_clean,
        "demands": demands_clean,
        "links": links_clean,
    }


def _clean_record(record: Dict) -> Dict:
    """
    Convertit les types numpy (int64, float64, bool_) en types Python natifs
    pour la sérialisation JSON. Les NaN float restent float('nan').
    """
    clean = {}
    for k, v in record.items():
        if isinstance(v, float) and math.isnan(v):
            clean[k] = float("nan")
        elif hasattr(v, "item"):  # numpy scalar → Python scalaire
            clean[k] = v.item()
        else:
            clean[k] = v
    return clean


def _format_sequence(seq: BlockingSequence) -> Dict[str, Any]:
    """
    Sérialise une BlockingSequence vers le format JSON attendu.
    Convertit [10, 28] → "10 -> 28".
    """
    ids = seq.get("blocking_sequence_ids", [])
    if not ids:
        # Cas où la séquence est déjà en format chaîne (passée directement par un solver)
        raw = seq.get("blocking_sequence", "")
    else:
        raw = " -> ".join(str(i) for i in ids)

    return {
        "commodity_id": seq["commodity_id"],
        "commodity_type": seq["commodity_type"],
        "origin_yard_id": seq["origin_yard_id"],
        "dest_yard_id": seq["dest_yard_id"],
        "volume": seq["volume"],
        "blocking_sequence": raw,
    }


def _format_route(route: BlockRoute) -> Dict[str, Any]:
    """
    Sérialise un BlockRoute vers le format JSON attendu.
    Convertit [10883, 10002] → "10883 -> 10002" pour les nœuds et liens.
    """
    node_ids = route.get("path_node_ids", [])
    link_ids = route.get("path_link_ids", [])

    if node_ids:
        node_str = " -> ".join(str(n) for n in node_ids)
    else:
        node_str = route.get("physical_path_nodes", "")

    if link_ids:
        link_str = " -> ".join(str(l) for l in link_ids)
    else:
        link_str = route.get("physical_path_links", "")

    return {
        "block_id": route["block_id"],
        "from_yard_id": route["from_yard_id"],
        "to_yard_id": route["to_yard_id"],
        "physical_path_nodes": node_str,
        "physical_path_links": link_str,
    }
