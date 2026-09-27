"""Stream F — multi-annotator consensus over signal labels.

Pure algorithm layer: NO database, NO config, NO Flask. It takes plain dicts (the rows
``db_signals.list_labels`` returns) and gives back clusters, per-cluster consensus,
chance-corrected agreement, per-annotator scorecards, and gold checks.

Why a separate module rather than an edit to the existing consensus code
───────────────────────────────────────────────────────────────────────
``database.compute_encounter_consensus`` votes on a *categorical signature* — an
annotator either reported a (side, zone, type, colour) scar or did not. There is no
geometry: two annotators agree because they picked the same four enum values, and it
does not matter where on the animal they clicked.

A signal label is the opposite. Two annotators looking at the same whistle will never
produce identical numbers; they produce two rectangles that overlap. The *first*
question is "are these two marks the same event?" and only then "did you call it the
same thing?". That detection-then-classification split has no counterpart in the scar
algorithm, so there is nothing to reuse there and the existing function is left alone —
as `plans/12-stream-f-signals.md` requires.

One algorithm, three geometries
───────────────────────────────
``db_signals.validate_geometry`` guarantees exactly three shapes:

    box       t1 > t0, f1 > f0            a rectangle
    interval  t1 > t0, f is NULL          full-band: the whole spectrum, a span of time
    point     t1 == t0, f is NULL or f1==f0   an instant, optionally at one frequency

All three are rectangles in a (time × frequency) plane — two of them degenerate. So one
matcher handles all three, provided degeneracy is handled honestly rather than by
letting a 0/0 IoU fall out as 0.0. Where an extent exists we use IoU; where it has
collapsed to a point we use a distance tolerance. Mixing the two is not a fudge: an IoU
between two zero-width marks is *undefined*, and answering an undefined question with
"no overlap" would silently reject every RF pulse pair in the corpus.

Which geometries may be compared
────────────────────────────────
box↔box, point↔point and point↔box are all real comparisons of the same claim at
different precisions. **interval↔box and interval↔point are not.** An interval says "in
this stretch of time the animal was cruising"; a box says "at this time and *this
frequency* there was a whistle". They live in different lanes of the UI and are
different assertions, so they are never clustered together — a category error would show
up as a spurious disagreement and drag the reliability number down for no reason.

Chance correction
─────────────────
Raw agreement is not a reliability statistic: two annotators who both label almost
everything "cw_tone" agree ~95% of the time by accident. This module is the first place
in the repo to compute a chance-corrected figure (a repo-wide grep for kappa / Fleiss /
Krippendorff previously returned nothing) because it has an external bar to clear —
anchor's `docs/paper_outline.md` §4.4 sets **Cohen's κ ≥ 0.7**.

κ is reported on **two axes**, because it answers only one of them well. The
detection-inclusive figures (`fleiss_kappa`, `mean_pairwise_kappa`) fold "nobody marked
this" in as a category and are therefore hostage to the κ prevalence paradox: on a
single-code task, two raters agreeing on 80% of the real 70-pulse RELAY capture score
**κ = 0.0**. `kappa_code` — κ over the events *both* raters marked — is the
classification agreement the ≥0.7 bar is actually about, and is what `meets_bar` judges.
See :class:`AgreementStats`. Raw agreement is reported beside all of them, never instead.

What this layer structurally cannot see
───────────────────────────────────────
Clusters are built *from labels*, so an event the whole cohort missed produces no
cluster and contributes to nothing — not κ, not raw agreement, and not
``detection_recall``, whose denominator is "events other people marked". A cohort that
unanimously overlooks half a file scores perfectly.

So ``meets_bar`` means **"the people who marked things agreed"**, never "we found
everything", and UI copy must not let it read as the latter. Gold items are the only
instrument here that can catch a shared miss, because a gold item asserts an event
independently of whether anybody found it — which is precisely why gold exists alongside
consensus rather than as a nicety on top of it.

Tolerance defaults
──────────────────
``DEFAULT_T_TOL_S`` and ``DEFAULT_F_TOL_HZ`` are RELAY's own scorer tolerances
(`metrics/detection.py`: ±0.200 s, ±3000 Hz). That is deliberate: a gold check passed
here means the same thing it would mean in RELAY's benchmark, rather than merely
something similar.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from .identity import norm_annotator as _norm_annotator
DEFAULT_IOU_THRESHOLD = 0.3
DEFAULT_T_TOL_S = 0.2
DEFAULT_F_TOL_HZ = 3000.0
DEFAULT_MATCH_THRESHOLD = 0.3
DEFAULT_COVERAGE_THRESHOLD = 0.8
DEFAULT_MAX_SIZE_RATIO = 100.0

@dataclass(frozen=True)
class Rect:
    """One label as a rectangle in the (time × frequency) plane.

    ``f0``/``f1`` are None for a full-band label. A point is ``t0 == t1``; a point that
    carries a frequency has ``f0 == f1``.
    """
    t0: float
    t1: float
    f0: Optional[float] = None
    f1: Optional[float] = None

    @property
    def t_degenerate(self) -> bool:
        ...

    @property
    def f_full_band(self) -> bool:
        ...

    @property
    def f_degenerate(self) -> bool:
        ...

@dataclass
class Cluster:
    """A set of labels judged to describe one event, at most one per annotator."""
    key: str
    source_id: Optional[int]
    kind: str
    channel: Optional[str]
    t_start_s: float = 0.0
    t_end_s: float = 0.0
    f_lo_hz: Optional[float] = None
    f_hi_hz: Optional[float] = None
    code: Optional[str] = None
    code_agreement: float = 0.0
    mean_confidence: Optional[float] = None
    n_voters: int = 0
    support: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        ...

@dataclass
class AgreementStats:
    """Chance-corrected agreement for one deployment (or one source within it).

    Detection and classification are reported **separately**, because κ answers only one
    of them well.

    ``fleiss_kappa`` / ``mean_pairwise_kappa`` fold "nobody marked this" in as a category,
    so they cover detection and naming together. That makes them vulnerable to the κ
    prevalence paradox: on a single-code task (every RF pulse is ``tag_pulse``) two raters
    who agree on 80% of a 70-pulse train score **κ = 0.0**, because with one category the
    expected-by-chance agreement is ~1. Measured on the real RELAY corpus, not
    hypothesised.

    ``kappa_code`` is κ over the events **both** raters marked — pure classification, no
    absent category. That is the statistic anchor's ``docs/paper_outline.md`` §4.4 bar is
    about (agreement on a behaviour class), so ``meets_bar`` is judged on it. Where there
    is only one code in play it is undefined rather than misleadingly perfect, and
    detection quality lives in the per-annotator recall figures instead.
    """
    n_items: int = 0
    n_raters: int = 0
    raw_agreement: Optional[float] = None
    fleiss_kappa: Optional[float] = None
    mean_pairwise_kappa: Optional[float] = None
    kappa_code: Optional[float] = None
    code_agreement: Optional[float] = None
    n_items_code: int = 0
    n_items_fleiss: int = 0
    n_items_fleiss_total: int = 0
    meets_bar: Optional[bool] = None
    bar: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        ...

@dataclass
class AnnotatorScore:
    """How one annotator's labels sit against the consensus of everyone else."""
    annotator: str
    n_labels: int = 0
    n_clusters: int = 0
    n_corroborated: int = 0
    n_solo: int = 0
    n_code_hits: int = 0
    n_code_checked: int = 0
    code_agreement: Optional[float] = None
    detection_recall: Optional[float] = None
    n_recall_events: int = 0
    kappa: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        ...

@dataclass
class GoldScore:
    """One annotator checked against blind gold items."""
    annotator: str
    n_gold: int = 0
    n_hit: int = 0
    n_missed: int = 0
    n_false_positive: int = 0
    n_code_hits: int = 0
    n_df_pairs: int = 0
    recall: Optional[float] = None
    precision: Optional[float] = None
    code_accuracy: Optional[float] = None
    mean_abs_dt_s: Optional[float] = None
    mean_abs_df_hz: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        ...

@dataclass
class ConsensusResult:
    deployment_id: int
    n_labels: int = 0
    n_machine: int = 0

    def counts_by_state(self) -> Dict[str, int]:
        ...

    def to_dict(self) -> Dict[str, Any]:
        ...

def rect_of(label: Dict[str, Any]) -> Rect:
    """Read one label row as a rectangle."""
    ...

def _iou_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    """IoU of two closed intervals with positive length."""
    ...

def _point_gap(p: float, lo: float, hi: float) -> float:
    """Distance from a point to a closed interval (0 when inside)."""
    ...

def _axis_score(a0: float, a1: float, b0: float, b1: float, *, tol: float) -> float:
    """Overlap on one axis, in [0, 1], for any mix of extended and degenerate extents.

    Extended vs extended → IoU. Anything degenerate → a linear tolerance kernel, because
    IoU between two zero-width marks is undefined and answering it with 0.0 would reject
    every RF pulse pair in the corpus.
    """
    ...

def _overlap_or_touch(a0: float, a1: float, b0: float, b1: float) -> bool:
    ...

def comparable(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Whether two labels make the same *kind* of claim, so overlap is meaningful.

    An interval ("the animal was cruising during this stretch") and a box ("there was a
    whistle at this time and this frequency") are different assertions on different
    lanes. Clustering them would manufacture a disagreement out of a category error.
    """
    ...

def _coverage_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    """Overlap as a fraction of the SHORTER extent."""
    ...

def _rect_coverage(ra: Rect, rb: Rect) -> float:
    """Intersection area over the SMALLER rectangle's area; 1.0 when one contains the other."""
    ...

def _extended_scores(ra: Rect, rb: Rect) -> Tuple[float, float]:
    """(IoU, coverage) for a pair that both have real extent."""
    ...

def _extended_size_ratio(ra: Rect, rb: Rect) -> float:
    """Larger extent over smaller, on whatever quantity coverage divided by.

    Branches exactly as :func:`_extended_scores` does — duration for two full-band
    intervals, area otherwise — so the ratio always denominates the same thing as the
    coverage it is bounding. Deriving it separately is how the two would drift apart and
    the bound would quietly start policing a quantity nobody computed.

    ``inf`` when the smaller side has collapsed, which cannot corroborate anything by
    containment: a zero-extent partner is the degenerate regime's business, not this one.
    """
    ...

def _rect_iou(ra: Rect, rb: Rect) -> float:
    """True rectangle IoU — intersection area over union area."""
    ...

def is_degenerate_pair(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Whether this pair must be judged by tolerance rather than by overlap.

    True as soon as either label has collapsed on either axis — a point has no duration,
    and a point-on-a-waterfall has no bandwidth. An IoU there is 0/0.
    """
    ...

def match_score(a: Dict[str, Any], b: Dict[str, Any], *, t_tol_s: float=DEFAULT_T_TOL_S, f_tol_hz: float=DEFAULT_F_TOL_HZ) -> float:
    """How strongly two labels assert the same event, in [0, 1].

    Two regimes, because the geometries genuinely differ and forcing one formula on both
    gets one of them wrong:

    * **Both labels have real extent** → true rectangle IoU (or, for two full-band
      intervals, the 1-D IoU in time). This is scale-invariant: multiplying an axis by a
      constant scales intersection and union alike, so the same threshold works for a
      2 MHz RF capture with 20 ms pulses and a 24 kHz HydroMoth file with multi-second
      calls. No normalisation constant to get wrong.

    * **Anything degenerate** → the *worst* axis, each measured against its tolerance.
      ``min``, not a product: RELAY's criterion is "within ±0.200 s **and** ±3000 Hz",
      a conjunction. Multiplying two tolerance kernels would fail a mark that sits
      comfortably inside both (0.5 × 0.5 = 0.25), quietly shrinking the effective
      tolerance to a fraction of the configured one — measured at ~0.7× on the real
      RELAY pulse train before this was split out.

    The returned value is graded so candidate pairs can be ranked. Whether a pair is a
    *match* is :func:`matches`, which applies the right test for its regime.
    """
    ...

def matches(a: Dict[str, Any], b: Dict[str, Any], *, iou_threshold: float=DEFAULT_IOU_THRESHOLD, coverage_threshold: float=DEFAULT_COVERAGE_THRESHOLD, max_size_ratio: float=DEFAULT_MAX_SIZE_RATIO, t_tol_s: float=DEFAULT_T_TOL_S, f_tol_hz: float=DEFAULT_F_TOL_HZ) -> bool:
    """Whether two labels describe the same event.

    The two knobs govern disjoint regimes and never interact: ``iou_threshold`` decides
    how much two drawn rectangles must overlap, while ``t_tol_s``/``f_tol_hz`` decide how
    close two clicks must be. Applying the IoU threshold to a tolerance score as well
    would make the real tolerance some opaque product of the two — so "within tolerance"
    here means exactly what it means in RELAY's scorer, and nothing else.

    ``coverage_threshold`` is the third, narrower door: containment, for "the same claim
    at different precision". ``max_size_ratio`` is what keeps it a door rather than a
    hole — see :data:`DEFAULT_MAX_SIZE_RATIO`. It bounds only this door; the IoU test
    above needs no such guard, because IoU already collapses for mismatched extents.
    """
    ...

def _group_key(label: Dict[str, Any]) -> Tuple:
    """Labels only ever cluster within one source, and one channel of it."""
    ...

def _is_machine(label: Dict[str, Any]) -> bool:
    ...

def cluster_labels(labels: Sequence[Dict[str, Any]], *, iou_threshold: float=DEFAULT_IOU_THRESHOLD, coverage_threshold: float=DEFAULT_COVERAGE_THRESHOLD, max_size_ratio: float=DEFAULT_MAX_SIZE_RATIO, t_tol_s: float=DEFAULT_T_TOL_S, f_tol_hz: float=DEFAULT_F_TOL_HZ) -> List[Cluster]:
    """Group labels that describe the same event, at most one per annotator.

    Constrained single-linkage: candidate pairs are merged strongest-first, and a merge
    is refused when it would put the same annotator in a cluster twice. Without that
    constraint one person drawing two adjacent boxes would read as two people agreeing —
    the single most dangerous way to inflate a consensus number.

    Machine labels are clustered *after* the humans and never bridge two human clusters:
    a detector's proposal linking two separate human marks into one event would let the
    model quietly rewrite the ground truth it is supposed to be measured against.
    """
    ...

def _by_group(labels: Iterable[Dict[str, Any]]) -> Dict[Tuple, List[Dict[str, Any]]]:
    ...

def _candidate_pairs(items: List[Dict[str, Any]], *, t_tol_s: float) -> Iterable[Tuple[int, int]]:
    """Index pairs close enough in time to possibly match.

    A sweep, not an all-pairs scan: a full RF deployment is tens of thousands of pulses
    and O(n²) there is minutes of CPU inside a request.
    """
    ...

def _cluster_one_group(gkey: Tuple, items: List[Dict[str, Any]], *, iou_threshold: float, coverage_threshold: float, max_size_ratio: float, t_tol_s: float, f_tol_hz: float) -> List[Cluster]:
    ...

def _lid(label: Dict[str, Any]) -> int:
    ...

def _build_cluster(rows: List[Dict[str, Any]], source_id: Optional[int], family: str, channel: Optional[str]) -> Cluster:
    ...

def _attach_machine_proposals(clusters: List[Cluster], machines: List[Dict[str, Any]], *, iou_threshold: float, coverage_threshold: float, max_size_ratio: float, t_tol_s: float, f_tol_hz: float) -> None:
    """Record which machine labels back each human cluster, without letting them vote.

    Matched against the cluster's **real member labels**, not against a synthetic
    rectangle spanning them. A hull is not a label: two frequency-less points 50 ms apart
    hull into something with a duration and no band, which classifies as an *interval* —
    so a detector's proposal attached while one human had marked the event and silently
    detached the moment a second human corroborated it. The hull also flipped a pair out
    of the tolerance regime into the IoU regime for the same reason. Comparing like with
    like removes both.
    """
    ...

def _modal(tally: Dict[str, int]) -> str:
    """Most-voted code, ties broken alphabetically so a rerun is byte-identical."""
    ...

def decide_cluster(c: Cluster, *, pool_size: int, min_confidence: float=3.0) -> Cluster:
    """Fill in modal code, agreement, and consensus_state for one cluster.

    Thresholds mirror the house scar algorithm (3+ voters at mean confidence ≥ 3 →
    confirmed, 2+ → probable) so the two systems read the same way, with one addition:
    ``disputed``. Two people marking the same event and *naming it differently* is a
    vocabulary problem, not a detection problem, and collapsing it into "unconfirmed"
    would hide the one signal that says the ethogram needs work.
    """
    ...

def cohen_kappa(pairs: Sequence[Tuple[str, str]]) -> Optional[float]:
    """Cohen's κ over paired categorical judgements.

    Returns None when undefined (no items). When the raters agree on everything *and*
    used a single category, chance agreement is 1.0 and κ is 0/0 — that is reported as
    1.0, the conventional reading: perfect agreement, no information about chance.
    """
    ...

def fleiss_kappa(rows: Sequence[Dict[str, int]]) -> Optional[float]:
    """Fleiss' κ over items rated by a fixed number of raters.

    ``rows`` is one dict per item mapping category → count. Items whose rater count
    differs from the modal count are dropped: Fleiss is only defined for a constant
    number of raters per item, and quietly rescaling would fabricate a statistic.
    """
    ...

def eligible_raters(clusters: Sequence[Cluster], voter_pool: Sequence[str], *, reviewed: Optional[Dict[str, Any]]=None) -> Dict[str, set]:
    """Which raters were actually looking at each cluster's source.

    Absence is only evidence when somebody was there to see it. An annotator assigned
    three files who labeled one of them has said nothing at all about the other two, and
    counting them as "marked nothing here" would make every event in those files look
    unanimously agreed with a rater who never opened them — inflating agreement on the
    exact figure the ≥0.7 bar is checked against.

    ``reviewed`` maps annotator → the set of source_ids they reviewed (``None`` inside
    that set means the whole deployment, which is what a completed assignment implies).
    Without it, review is inferred from where each annotator actually wrote a label —
    weaker, but never claims coverage nobody demonstrated.
    """
    ...

def _weighted_mean(pairs: Sequence[Tuple[float, int]]) -> Optional[float]:
    """Mean of (value, weight) pairs; None when there is nothing to average."""
    ...

def _fleiss_with_coverage(rows: Sequence[Dict[str, int]]) -> Tuple[Optional[float], int, int]:
    """Fleiss' κ plus how much of the data it was actually computed over.

    Fleiss needs a constant rater count, so items rated by a different number of people
    are dropped. With per-source eligibility that group can be a minority of the events —
    and the bare number gave no hint, so a κ computed over a third of a deployment looked
    exactly like one computed over all of it. The counts are returned so the caller can
    say which.
    """
    ...

def compute_agreement(clusters: Sequence[Cluster], voter_pool: Sequence[str], *, bar: float=0.7, reviewed: Optional[Dict[str, Any]]=None) -> AgreementStats:
    """Chance-corrected agreement across the voter pool.

    The unit of analysis is a **cluster**: one event that at least one person marked.
    Each rater's response is the code they gave it, or ABSENT if they reviewed that
    source and marked nothing there. Including ABSENT is what makes this measure
    detection *and* classification together — the two failure modes a labeling team
    actually has. Raters who never reviewed the source contribute nothing to that
    cluster rather than a free "absent".
    """
    ...

def score_annotators(clusters: Sequence[Cluster], voter_pool: Sequence[str], *, reviewed: Optional[Dict[str, Any]]=None) -> List[AnnotatorScore]:
    """Score each annotator against the consensus of *everyone else*.

    Leave-one-out throughout: an annotator is never part of the answer they are graded
    against. Scoring against a modal code they helped set would reward whoever labels
    most, which is the opposite of what a quality score is for.
    """
    ...

def score_against_gold(gold: Sequence[Dict[str, Any]], mine: Sequence[Dict[str, Any]], annotator: str, *, iou_threshold: float=DEFAULT_MATCH_THRESHOLD, coverage_threshold: float=DEFAULT_COVERAGE_THRESHOLD, max_size_ratio: float=DEFAULT_MAX_SIZE_RATIO, t_tol_s: float=DEFAULT_T_TOL_S, f_tol_hz: float=DEFAULT_F_TOL_HZ) -> GoldScore:
    """Check one annotator's labels against blind gold items.

    Greedy best-first one-to-one matching, so a single sloppy box cannot cover three
    gold items and score as three hits.

    A false positive is only counted **inside the time span the gold covers**. Gold
    items are sampled spans, not an exhaustive transcript of the file; counting marks
    outside them as errors would punish an annotator for labeling parts nobody vetted.
    """
    ...

def _extent_gap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Separation between two extents on one axis; 0 when they touch or overlap.

    This is the quantity the matcher judges a degenerate pair on, so localisation error
    reported from it agrees with the decision that produced the match.
    """
    ...

def _centre(a: Optional[float], b: Optional[float]) -> float:
    ...

def compute_consensus(deployment_id: int, labels: Sequence[Dict[str, Any]], *, voter_pool: Optional[Sequence[str]]=None, reviewed: Optional[Dict[str, Any]]=None, iou_threshold: float=DEFAULT_IOU_THRESHOLD, coverage_threshold: float=DEFAULT_COVERAGE_THRESHOLD, max_size_ratio: float=DEFAULT_MAX_SIZE_RATIO, t_tol_s: float=DEFAULT_T_TOL_S, f_tol_hz: float=DEFAULT_F_TOL_HZ, min_confidence: float=3.0, kappa_bar: float=0.7) -> ConsensusResult:
    """Cluster, decide, and score one deployment's labels.

    ``voter_pool`` is who *could* have marked each event — normally the annotators with a
    completed assignment on the deployment. It is the denominator for support and the
    rater set for κ, and it matters: an annotator who reviewed a source and drew nothing
    is casting a real "nothing here" vote, and dropping them would make every event look
    unanimously agreed. When not supplied it falls back to whoever actually wrote a
    label, which is the weaker but still honest reading.
    """
    ...

def redact_for(result: Dict[str, Any], me: str) -> Dict[str, Any]:
    """Strip peer identities from a consensus result for a non-admin reader.

    A labeler needs to know *how many* people marked an event and whether the group
    agreed. They must not learn *who*. Naming peers turns the review panel into a social
    signal: you stop labeling what you see and start labeling what the person you rate
    highly saw, which is precisely the anchoring the whole multi-rater design exists to
    measure rather than induce. It also publishes a live per-person quality ranking to
    the cohort, which nobody consented to.

    Counts survive, names do not — ``n_voters``, ``n_raters`` and every aggregate κ are
    untouched, so the panel stays fully informative. What goes: cluster membership,
    per-person votes, the voter pool, peer scorecards, and the named pairwise κ table.

    ``/scorecard`` already filters its own ``annotators`` list; this exists because the
    same identities leak through four other fields, including ``agreement.pairwise``
    sitting directly beside that filter.

    A withheld collection is returned as ``None``, never as a shorter list. That rule is
    the whole point, and it is the repo's existing one: Darwin Core's
    ``publish_coordinates: false`` withholds coordinates *and* states
    ``informationWithheld``, so a consumer can tell suppression from absence. A truncated
    list breaks that — it is a valid-looking value, so ``len(voter_pool)`` silently means
    "everyone" for an admin and "just you" for a labeler. That exact composition rendered
    a unanimous 3-of-3 event as "3/1", and it was invisible to admins, who are never
    redacted and so never saw it.

    Counts and aggregates are the supported way to ask "how many": ``n_voters`` per
    cluster and ``agreement.n_raters`` for the pool. ``mine`` answers "did I mark this"
    without being shaped like a count.
    """
    ...
