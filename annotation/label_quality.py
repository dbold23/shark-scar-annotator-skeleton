"""Stream B (MLOps) — multi-rater label-quality aggregation.

Pure algorithm layer: NO database, NO config, NO Flask. It takes plain Python
structures (per-annotator track verifications + annotator weights + optional
auto-hints) and returns consensus labels, per-track trust scores, and
per-annotator quality scores for the four categorical track-verification fields
(``scar_type`` / ``human_zone`` / ``human_side`` / ``human_color``).

Why a separate aggregation (and not an edit to ``database.compute_track_consensus``):
the existing path is a weighted-mode vote that writes the single canonical answer
back to ``tracks.human_*``. Stream B's contract is to *read* that and write a NEW
aggregation alongside it (cached in ``track_label_quality`` / ``annotator_quality``
via ``annotation/db_mlops.py``), never to overwrite the canonical column.

Three methods, all selectable so the caller can benchmark them against held-out
gold (research finding: *no consensus algorithm wins universally* — validate):

  * ``majority``      — unweighted plurality (naive baseline).
  * ``weighted_vote`` — weight = experience×proficiency×(confidence/5); mirrors the
                        existing ``compute_track_consensus`` weighting. Pure-Python,
                        always available (this is the default fallback).
  * ``crowdlab``      — cleanlab CROWDLAB. Beats majority/Dawid–Skene/GLAD for
                        multi-rater consensus AND yields calibrated per-example trust
                        + per-annotator quality. CLASSIFICATION-ONLY (these four
                        categorical fields), never detector mAP / pose AP. Optional,
                        heavier dep — lazy-imported; absent ⇒ silent fallback.

CROWDLAB needs model ``pred_probs``. With no trained classifier we bootstrap them
from a Laplace-smoothed global class prior blended with each track's weighted-vote
histogram, and — for zone/side/color — fold the pose auto-hint in as an INDEPENDENT
pseudo-annotator (the one genuinely non-circular signal available pre-model). This
is documented as a bootstrap; when a real classifier exists (Stream A embeddings,
a scar-type head) its out-of-sample probabilities can be passed in unchanged.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Tuple
_CORROBORATION_FULL_AT = 2

@dataclass
class FieldResult:
    field: str
    consensus: Optional[str]
    trust: float
    agreement: float
    n_votes: int
    method: str

@dataclass
class TrackResult:
    track_id: int
    n_voters: int
    fields: Dict[str, FieldResult]
    overall_trust: float
    agreement: float

    def consensus(self, fld: str) -> Optional[str]:
        ...

@dataclass
class AnnotatorResult:
    annotator: str
    overall_quality: Optional[float]
    per_field: Dict[str, float]
    num_examples: int
    agreement_rate: Optional[float]

@dataclass
class LabelQualityResult:
    method: str
    tracks: List[TrackResult]
    annotators: List[AnnotatorResult]
    n_tracks: int
    n_annotators: int
    n_multi_rater: int

def crowdlab_available() -> bool:
    """True if cleanlab (and its numpy/pandas deps) can be imported."""
    ...

def _votes_by_field(verifications: List[Dict], weights: Dict[str, float]) -> Dict[str, Dict[int, List[Dict]]]:
    """Group non-null votes as field → track_id → list of {annotator, label, weight,
    confidence, verified_at}. Weight = annotator weight × confidence/5 (floor on a
    missing confidence = 3/5, mirroring the existing consensus path)."""
    ...

def _track_voter_counts(verifications: List[Dict]) -> Dict[int, int]:
    """Distinct annotators per track (a track's voter count is the max over fields —
    i.e. the number of people who verified it at all)."""
    ...

def _vote_one(field_votes: List[Dict], *, weighted: bool) -> Tuple[Optional[str], float, float]:
    """Resolve one (track, field): returns (consensus, trust, agreement).

    trust = purity (winner mass / total mass) × corroboration discount, where the
    discount linearly penalises < ``_CORROBORATION_FULL_AT`` voters so single-voter
    tracks (the current default) surface for a second opinion. Ties broken by most
    recent ``verified_at`` then label sort (deterministic)."""
    ...

def _vote_consensus(votes: Dict[str, Dict[int, List[Dict]]], voter_counts: Dict[int, int], *, weighted: bool) -> List[TrackResult]:
    ...

def _peer_consensus(field_votes: List[Dict], exclude_annotator: str, *, weighted: bool) -> Optional[str]:
    """LEAVE-ONE-OUT consensus for one (track, field): the answer the OTHER voters
    reach, with ``exclude_annotator``'s vote removed. ``None`` when nobody else
    voted — that (track, field) is then ungradable for this person, because the
    only 'truth' available is their own label."""
    ...

def _vote_annotator_quality(verifications: List[Dict], track_by_id: Dict[int, TrackResult], votes: Optional[Dict[str, Dict[int, List[Dict]]]]=None, *, weighted: bool=True) -> List[AnnotatorResult]:
    """Per-annotator quality = agreement with the consensus of the OTHER annotators.

    Leave-one-out. Grading somebody against a consensus their own vote helped
    decide is not a measurement: on a single-voter track the consensus IS their
    answer, so `label == cons` always held and every sole verifier scored a
    perfect 1.0 — which is the current state of essentially every track. That
    number then feeds users.proficiency_weight through
    db_mlops.feed_proficiency_weight, so the inflation does not stay cosmetic.

    When `votes` is supplied, each vote is scored against `_vote_one` recomputed
    over the same (track, field) with that annotator's vote REMOVED. A vote with
    no remaining voters is skipped entirely rather than counted as a miss —
    scoring it 0.0 would be exactly as wrong as scoring it 1.0, just in the other
    direction. An annotator with nothing left to compare against therefore gets
    `overall_quality=None`, which callers must treat as "not measured" and not as
    zero.

    Without `votes` it keeps the old self-referential behaviour, so existing
    callers that have not been updated do not silently change meaning.
    """
    ...

def _bootstrap_pred_probs(np_mod, track_ids: List[int], classes: List[str], field_votes: Dict[int, List[Dict]], auto_hint_for_track, alpha: float):
    """Per-field pred_probs (N×K): Laplace-smoothed global prior blended with each
    track's weighted-vote histogram, plus the auto-hint as an independent pseudo-
    annotator. Documented bootstrap — replaceable by a real model's pred_probs."""
    ...

def _crowdlab_field(field_votes: Dict[int, List[Dict]], auto_hint_for_track, alpha: float) -> Tuple[Dict[int, FieldResult], Dict[str, float], Dict[str, Optional[float]]]:
    """Run CROWDLAB for ONE field. Returns (track_id→FieldResult,
    annotator→quality, annotator→agreement). Raises on degenerate input so the
    caller can fall back."""
    ...

def compute_label_quality(verifications: List[Dict], weights: Dict[str, float], auto_hints: Optional[Dict[int, Dict[str, Any]]]=None, *, method: str='auto', min_multi_rater: int=5, laplace_alpha: float=1.0, use_auto_hints: bool=True) -> LabelQualityResult:
    """Aggregate ``verifications`` (one dict per track+annotator) into per-track
    consensus+trust and per-annotator quality.

    ``method``: 'auto' uses CROWDLAB when it's importable AND there are
    ≥``min_multi_rater`` tracks with ≥2 voters AND ≥2 annotators; otherwise
    weighted_vote. 'crowdlab' forces CROWDLAB (falls back with a note on any
    failure). 'majority'/'weighted_vote' force those.
    """
    ...

def validate_against_gold(verifications: List[Dict], weights: Dict[str, float], gold_truth: Dict[int, Dict[str, str]], auto_hints: Optional[Dict[int, Dict[str, Any]]]=None, *, methods: Tuple[str, ...]=('majority', 'weighted_vote', 'crowdlab'), min_multi_rater: int=1, laplace_alpha: float=1.0) -> Dict[str, Any]:
    """Compare each method's consensus on gold tracks (tracks with a trusted
    ``gold_truth`` label) field-by-field. Returns per-method accuracy so the caller
    can see which aggregation actually tracks ground truth on THIS dataset (no method
    wins universally — this is the gate's empirical check)."""
    ...
