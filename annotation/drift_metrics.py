"""Stream B (MLOps) — pure drift & degradation metrics for Phase B4.

No DB, no model, no numpy/scipy: takes distributions / embedding vectors / scalars
as plain Python and returns reproducible drift scores. Kept dependency-free (same
discipline as ``eval_metrics.py``) so it imports anywhere, the numbers are
byte-stable, and the monitor runs on a CPU box with nothing extra installed.

Three families, matching the research framing (Evidently/DriftLens catch covariate
drift P(X); PSI is the canonical categorical-prior drift metric; the labeled golden
set remains the only real performance gate):

  * label drift     — Population Stability Index over a categorical distribution
                      (verified-track scar_type/zone/side/color) vs a frozen ref.
  * embedding drift — covariate drift P(X): normalized centroid shift between a
                      reference and a current set of same-model embeddings.
  * performance     — degradation of a served metric vs a reference best.

Severity is a simple two-threshold band (none / warn / alarm) so the monitor and
the admin panel read the same labels. Nothing here decides to retrain or deploy —
callers gate that separately.
"""
from __future__ import annotations
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence
PSI_WARN = 0.1
PSI_ALARM = 0.25

def severity(score: Optional[float], warn: float, alarm: float, higher_is_worse: bool=True) -> str:
    """Map a drift score to none|warn|alarm against two thresholds. ``score`` None
    → 'insufficient_data' (the signal couldn't be computed this cycle)."""
    ...

def proportions(values: Sequence[Optional[str]]) -> Dict[str, float]:
    """Normalized categorical distribution. ``None`` is its own bucket so a shift
    toward/away from 'unlabeled' still registers. Empty input → empty dict."""
    ...

def psi(expected: Dict[str, float], actual: Dict[str, float], eps: float=0.0001) -> float:
    """Population Stability Index between two categorical distributions (proportions
    that each sum to ~1). Symmetric in structure; ``expected`` is the frozen
    reference. Categories missing from either side are floored to ``eps`` so a newly
    appearing/vanishing class contributes finite, bounded drift.

        PSI = Σ (a_i − e_i) · ln(a_i / e_i)
    """
    ...

def label_drift(ref_props_by_field: Dict[str, Dict[str, float]], cur_values_by_field: Dict[str, Sequence[Optional[str]]], eps: float=0.0001, aggregate: str='max') -> Dict[str, Any]:
    """PSI per categorical field + an aggregate. ``ref_props_by_field`` is the frozen
    reference (proportions); ``cur_values_by_field`` is the current window's raw
    values. Aggregate 'max' is the headline (worst field drives the alarm); 'mean'
    is also reported. Fields absent from the reference are skipped."""
    ...

def _is_vector(v: Any, dim: Optional[int]) -> bool:
    ...

def centroid(vectors: Sequence[Sequence[float]]) -> List[float]:
    """Mean vector. Assumes equal-length vectors (caller filters)."""
    ...

def _l2(a: Sequence[float], b: Sequence[float]) -> float:
    ...

def mean_radius(vectors: Sequence[Sequence[float]], center: Sequence[float]) -> float:
    """Mean L2 distance of vectors from a center — the reference dispersion used to
    normalize the centroid shift into a scale-free drift score."""
    ...

def embedding_drift(ref_vectors: Sequence[Sequence[float]], cur_vectors: Sequence[Sequence[float]], min_items: int=10) -> Dict[str, Any]:
    """Covariate-drift proxy P(X): distance between the reference and current
    centroids, normalized by the reference dispersion (mean radius). Scale-free, so
    a single warn/alarm threshold works across embedding models.

        score = ||centroid_cur − centroid_ref|| / mean_radius(ref)

    Returns score None (caller → 'insufficient_data') when either side has < min_items
    usable vectors, or when dims mismatch — so this no-ops until Stream A populates
    ``signature_json``."""
    ...

def embedding_reference(vectors: Sequence[Sequence[float]], min_items: int=10) -> Optional[Dict[str, Any]]:
    """Compact, storable reference for embedding drift: centroid + dispersion +
    dim + n. Returns None if fewer than ``min_items`` usable vectors — so a baseline
    is only frozen once enough signatures exist. Stored in the v24 baseline row so
    later cycles never need the raw reference vectors."""
    ...

def embedding_drift_vs_ref(ref: Dict[str, Any], cur_vectors: Sequence[Sequence[float]], min_items: int=10) -> Dict[str, Any]:
    """Embedding drift of a current window against a stored ``embedding_reference``
    summary (centroid + radius). Same normalized-centroid-shift score as
    ``embedding_drift``, but the reference is the frozen baseline, not raw vectors."""
    ...

def performance_degradation(reference: Optional[float], current: Optional[float], higher_is_better: bool=True) -> Dict[str, Any]:
    """How far the served metric has fallen below the reference best (on the SAME
    frozen golden set). Positive ``score`` = degradation; 0 when current ≥ reference.
    ``reference``/``current`` None → score None (not scored this cycle)."""
    ...

def _ln(x: float) -> float:
    ...
