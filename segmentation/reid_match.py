"""Stream A (re-ID) Phase A2 — embedding matcher math (pure numpy, no DB, no I/O).

Given per-track A1 signatures grouped by individual, this module does the retrieval:
  * build a side-partitioned, model-safe gallery of labeled individuals,
  * rank candidate individuals for a query embedding (cosine, max-over-members → top-k),
  * a leakage-safe eval (recall@k / mAP) using leave-one-ENCOUNTER-out so a query's own encounter
    is never in the gallery it is scored against.

Design follows plans/01-research-models-reid.md §5: per-individual gallery partitioned by `side`
(never compare left vs right), surface Top-k (not Top-1) candidates to a human, and report
Top-1/Top-k/mAP on leakage-safe splits. Propose-only — nothing here writes the DB.
"""
from __future__ import annotations
import json
from typing import Dict, List, Optional, Tuple
import numpy as np

def parse_signature(signature_json: Optional[str]) -> Optional[Tuple[np.ndarray, str]]:
    """Extract the PRIMARY (body/fins) vector + model tag from a self-describing payload.

    Returns (L2-normalized vec, model) or None if unusable. Never raises.
    """
    ...

def side_compatible(a: Optional[str], b: Optional[str]) -> bool:
    """Left and right fins are not matchable; 'both'/'unknown'/None match anything."""
    ...

def rank_individuals(query_vec: np.ndarray, query_side: Optional[str], gallery: List[dict], *, exclude_label=None, exclude_encounter=None, side_partition: bool=True) -> List[Tuple[str, float, int]]:
    """Rank gallery individuals for one query by MAX cosine over their (side-compatible) members.

    gallery items: {label, side, vec, encounter}. Returns [(label, score, n_support)] desc by score.
    """
    ...

def suggest(query_vec: np.ndarray, query_side: Optional[str], gallery: List[dict], *, k: int=5, min_score: float=0.0, side_partition: bool=True, exclude_encounter=None) -> List[Tuple[str, float, int]]:
    """Top-k candidate individuals for a query, filtered by min_score."""
    ...

def evaluate(items: List[dict], k_list=(1, 5, 10), *, side_partition: bool=True) -> dict:
    """Leakage-safe retrieval eval over labeled items.

    items: {track_id, label, encounter, side, vec}. For each query track whose label spans >=2
    distinct encounters, the gallery EXCLUDES the query's own encounter (no same-encounter leakage),
    then we rank individuals and record the rank of the true label. Reports recall@k, mAP, and a
    random-baseline recall@k for context.
    """
    ...
