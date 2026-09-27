"""Scar consensus — identity first, classification second.

Pure algorithm: no DB, no Flask, no config reads. Same split as
`annotation/signal_consensus.py` and `annotation/label_quality.py`.
`database.compute_encounter_consensus` is untouched and becomes the
`identity: signature` branch.

WHY THIS EXISTS
---------------
The shipped scar algorithm identifies a scar by the tuple
`(SIDE, ZONE, SCAR_TYPE, COLOR)`. Colour and type are *part of the identity*, so
two annotators who saw the same scar and disagreed about its colour do not
produce a disagreement — **they produce two scars**. The signal that consensus
exists to measure is converted into phantom objects that can never disagree with
anything. `signal_consensus.py` already carries this critique in its header; this
module is that critique applied to scars.

Two riders on the same defect, both measured:
  * two same-signature scars in different places on one animal collapse to one
    before voting ever starts;
  * the primary/secondary rule keeps only the top signature per (side, zone) and
    silently drops the rest — and its gate tests `multiple_scars == "YES"`, which
    NO legacy value matches, so on imported data every secondary was dropped
    unconditionally.

THE SCAR PLANE
--------------
Stream F clusters in (time × frequency). The scar analogue already exists in this
repo: `segmentation/pose_zones.project_to_skeleton` returns `t`, the arc-length
fraction along the snout→caudal polyline — pose-invariant, scale-invariant,
frame-invariant. `zone_arc_span` is its inverse.

    u  = anatomical arc fraction ∈ [0, 1]      (snout = 0, caudal = 1)
    v  = signed perpendicular offset ÷ body length
    lane = (side, body-vs-fin)

And the equivalence that makes one matcher work for everything: **`zone` is `u`
quantised.** A scar carrying only a zone is a scar whose `u` is known to an
interval and whose `v` is unknown — which is exactly Stream F's `interval`:
extent on one axis, abstention on the other. Same axis, two precisions. Not an
analogy.

THREE GEOMETRIES, ONE MATCHER
-----------------------------
    body_box    bbox + usable pose on that frame   → u extent × v extent
    pixel_box   bbox, no pose                      → image x,y; comparable ONLY
                                                     with another pixel_box on
                                                     the SAME (video, frame)
    zone_span   zone only (all 8,374 legacy rows)  → u from zone_arc_span,
                                                     v abstains

A `pixel_box` with no same-frame partner **degrades to its own zone_span** rather
than becoming incomparable, so no scar is ever unmatchable and nothing is ever
dropped for want of geometry.

MEASURED ON THE RECOVERED CORPUS (333 multi-rater encounters, 8,374 raw votes)
-----------------------------------------------------------------------------
    signature identity would emit   3,717 scars
    geometric identity emits        2,049 scars
    collapsed                       1,668  (44.9%)

Nearly half the scar corpus was phantom duplicates: the same physical mark,
described slightly differently by two people, counted as two objects that each
looked unanimous. 266 of the surviving clusters are `disputed` -- 188 on
scar_type, 78 on colour -- and **that state did not previously exist**. Every one
of them was two agreement-free scars.

Mean pairwise κ is 0.664 over 299 encounters, and 199 of them fall below the 0.7
bar. That is a real and previously invisible finding about annotator agreement.

1,048 clusters are `single`: one rater marked the scar and the other did not.
That is a DETECTION disagreement, not a naming one, and it is the recall problem
gold items exist to catch -- consensus built from marks cannot see a scar the
whole cohort missed.

THRESHOLDS HAVE NO SHARK EVIDENCE
---------------------------------
`iou_threshold` and `coverage_threshold` are inherited verbatim from
`signal_consensus`, where they were tuned for spectrogram drags. The live scar
corpus is 61 boxes from 2 annotators with **zero encounter overlap**, and **zero
pose coverage on any scar frame**, so the entire `body_box` regime is
structurally unexercised. These ship as parameters, get recorded in `params_json`
on every run, and must be re-tuned the first time two people box the same scar.
Do not quote them as validated.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from .identity import norm_annotator as _norm_annotator
DEFAULT_IOU_THRESHOLD = 0.3
DEFAULT_COVERAGE_THRESHOLD = 0.8
DEFAULT_MIN_CONFIDENCE = 3.0
DEFAULT_ZONE_TOLERANCE = 0
DEFAULT_KAPPA_BAR = 0.7

@dataclass(frozen=True)
class Span:
    """A rectangle in the scar plane. `v_lo is None` means the v axis abstains."""
    u_lo: float
    u_hi: float
    v_lo: Optional[float] = None
    v_hi: Optional[float] = None

    @property
    def abstains_v(self) -> bool:
        ...

def zone_span(zone: str, zone_cuts: Sequence[float]) -> Optional[Span]:
    """Body zone → u interval. Fin zones have no arc position and return None."""
    ...

def geometry_of(scar: Dict[str, Any]) -> str:
    """Which of the three regimes this scar can be compared in."""
    ...

def _lane(scar: Dict[str, Any]) -> Tuple[str, str]:
    """(side, body-or-fin). LEFT never clusters with RIGHT; each fin is its own
    lane. Pairing a fin scar with a body scar manufactures a disagreement out of
    a category error — the same reasoning that keeps Stream F's `interval` and
    `box` apart."""
    ...

def comparable(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Category-error guard, applied before any score is computed."""
    ...

def _iou_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    ...

def _coverage_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    """Overlap as a fraction of the SHORTER interval.

    IoU cannot express "the same claim at different precision" — one rater boxes
    a whole bite cluster, another a single puncture inside it. Coverage is
    scale-invariant like IoU, so it does not make two long flank scrapes sharing
    1% of their length corroborate.
    """
    ...

def _rect_iou(a: Span, b: Span) -> float:
    ...

def _rect_coverage(a: Span, b: Span) -> float:
    ...

def span_of(scar: Dict[str, Any], zone_cuts: Sequence[float]) -> Optional[Span]:
    """The scar's extent in whichever plane it can be compared in.

    A pixel_box is returned in IMAGE coordinates; `match_score` only ever
    compares two pixel_boxes that share a frame, so mixing units cannot happen.
    """
    ...

def _same_frame(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    ...

def _effective_geometry(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    """Which regime this PAIR can actually be compared in.

    Two pixel_boxes on different frames of a swimming shark share no coordinate
    system — the same image rectangle is a different piece of animal. Rather than
    call them incomparable (which would drop them), both degrade to their zone
    spans, which is a real if coarse claim about where the mark is.
    """
    ...

def match_score(a: Dict[str, Any], b: Dict[str, Any], *, zone_cuts: Sequence[float], zone_tolerance: int=DEFAULT_ZONE_TOLERANCE) -> Tuple[float, str]:
    """-> (score in [0,1], regime). 0.0 means "not the same scar"."""
    ...

def matches(a: Dict[str, Any], b: Dict[str, Any], *, zone_cuts: Sequence[float], iou_threshold: float=DEFAULT_IOU_THRESHOLD, coverage_threshold: float=DEFAULT_COVERAGE_THRESHOLD, zone_tolerance: int=DEFAULT_ZONE_TOLERANCE) -> bool:
    ...

def self_merge(scars: Sequence[Dict[str, Any]], *, zone_cuts: Sequence[float], iou_threshold: float=DEFAULT_IOU_THRESHOLD, coverage_threshold: float=DEFAULT_COVERAGE_THRESHOLD, zone_tolerance: int=DEFAULT_ZONE_TOLERANCE) -> List[Dict[str, Any]]:
    """Collapse one annotator's repeated marks of the SAME scar. One vote each.

    This is the INVERSE of Stream F's rule. There, a merge that puts the same
    annotator in a cluster twice is refused outright. Here it is *required*
    first, because one person legitimately re-marks one physical scar on frame
    100, frame 200 and frame 300 — and counting that as three votes is the
    easiest way in the world to manufacture a unanimous consensus of one.

    The hard rule, and the one the old signature dedup got backwards:

        **Two scars on the SAME (video, frame) are NEVER merged.**

    The person drew two boxes on one image; those are two scars by construction,
    whatever they called them. The shipped algorithm merged them whenever the
    four enum values matched, destroying the second before voting began.
    """
    ...

@dataclass
class Cluster:
    weakest_axis: Optional[str] = None
    mean_confidence: Optional[float] = None
    support: Optional[float] = None
    n_eligible: Optional[int] = None
    excluded_from_kappa: bool = False

    @property
    def n_voters(self) -> int:
        ...

    @property
    def annotators(self) -> List[str]:
        ...

def _cluster_group(scars: Sequence[Dict[str, Any]], *, zone_cuts: Sequence[float], iou_threshold: float, coverage_threshold: float, zone_tolerance: int) -> List[List[Dict[str, Any]]]:
    """Complete linkage over one lane.

    COMPLETE, not single. `signal_consensus` documents why single linkage emitted
    3-voter "confirmed" clusters whose first and last members shared zero area.
    Here it is worse: zone spans chain trivially along the body axis, so single
    linkage would walk 1→2→3→…→9 and collapse an entire flank into one "scar".
    """
    ...
from annotation.signal_consensus import cohen_kappa, fleiss_kappa

def _modal(tally: Dict[str, int]) -> str:
    """Most votes, ties broken alphabetically — a rerun must never flip the
    stored answer."""
    ...

def decide_cluster(c: Cluster, *, n_eligible: Optional[int]=None, min_confidence: float=DEFAULT_MIN_CONFIDENCE) -> Cluster:
    """Vote each axis independently; the cluster is as strong as its WEAKEST axis.

    A scar has four classification axes, not one code. Voting them jointly is
    exactly the defect this module exists to remove — it would put colour back
    into the identity. Taking `min` over axes mirrors
    `label_quality.TrackResult.overall_trust`.

    The state that the shipped algorithm structurally cannot produce is
    `disputed`: two people who marked the same scar and named it differently have
    not half-agreed, and a 2-2 split is not "probable" either.
    """
    ...

def eligible_raters(clusters: Sequence[Cluster], reviewed: Dict[str, Dict[str, Any]]) -> Dict[int, set]:
    """Who was actually in a position to see each cluster, by SIDE.

    Absence is only evidence where somebody looked. A rater whose `sides_visible`
    was 'Left' has said nothing whatsoever about a right-flank scar, and counting
    them as "marked nothing here" is how a reliability figure gets inflated by
    people who were never there. That is the failure the old `total_annotators`
    denominator had by construction.

    `reviewed` maps annotator -> {'sides': set of sides they could see}. A rater
    with 'Both' (or nothing recorded) is eligible everywhere.
    """
    ...

@dataclass
class AgreementStats:
    """Every κ is Optional and is None when undefined. Never 0.0, never False.

    Two axes, as in F3. The detection-inclusive figures include an ABSENT
    category and are therefore hostage to the prevalence paradox; `kappa_code` is
    κ over the scars BOTH raters marked — pure classification — and that is what
    the ≥0.7 bar is about. Coverage counts travel with every κ, because a κ over
    six 1-vs-1 zone pairs must not read like a κ over a whole encounter.
    """
    n_raters: int = 0
    n_clusters: int = 0
    raw_agreement: Optional[float] = None
    fleiss_kappa: Optional[float] = None
    mean_pairwise_kappa: Optional[float] = None
    meets_bar: Optional[bool] = None
    n_items_code: int = 0
    n_items_excluded_multi: int = 0

@dataclass
class ConsensusResult:
    n_absent_raters: int = 0
    unanimous_absence: bool = False

    def counts_by_state(self) -> Dict[str, int]:
        ...

def compute_consensus(scars: Sequence[Dict[str, Any]], *, encounter_id: str='', zone_cuts: Sequence[float], reviewed: Optional[Dict[str, Dict[str, Any]]]=None, absent_raters: Sequence[str]=(), iou_threshold: float=DEFAULT_IOU_THRESHOLD, coverage_threshold: float=DEFAULT_COVERAGE_THRESHOLD, zone_tolerance: int=DEFAULT_ZONE_TOLERANCE, min_confidence: float=DEFAULT_MIN_CONFIDENCE, kappa_bar: float=DEFAULT_KAPPA_BAR) -> ConsensusResult:
    """Cluster first, then vote. The whole module in one call.

    `absent_raters` are people who reviewed this encounter and reported NO scars.
    They are an explicit negative vote, not a denominator adjustment — and only
    within the sides they could actually see (see `eligible_raters`).

    NOTHING IS EVER DROPPED. Every scar ends in exactly one cluster; a cluster of
    one is `single`, which is a reportable state, not a deletion. The rule this
    replaces silently deleted every secondary scar in a zone.
    """
    ...

def _agreement(clusters: Sequence[Cluster], n_raters: int, kappa_bar: float) -> AgreementStats:
    ...
