"""Gap analysis — what does the corpus still LACK, and which candidate closes it most?

Stream B, plan 10. Pure functions over plain dicts: no DB, no I/O, no third-party
imports, so every rule here is unit-testable in isolation. ``db_datasets.py`` owns
the SQL and calls into this module for the ranking.

The central idea: an annotator's next item is chosen by how much it moves the
declared dataset toward its target, not by what the annotator feels like doing.
Two regimes, because with an empty corpus deficit ranking is meaningless:

  * BOOTSTRAP — corpus below ``bootstrap_n``. Every class has an identical deficit,
    so ranking by deficit is arbitrary. Enforce the visibility gate and maximise
    SPREAD across videos/sites instead, so the first N labels cover the space.
  * DEFICIT — past bootstrap. Rank by what is behind: under-represented keypoints,
    rare scar classes, model uncertainty.

Skipping the bootstrap regime is how a corpus ends up 69 % two classes (see the
pilot numbers in plans/10 §1.2).
"""
from collections import OrderedDict
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple
PLACED_VISIBILITIES = (1, 2)

def select_regime(completed_n: int, bootstrap_n: int) -> str:
    """Which ranking regime applies at this corpus size.

    ``bootstrap_n <= 0`` disables the bootstrap phase entirely (deficit from item one),
    which is the right setting for a spec that extends an already-healthy corpus.
    """
    ...

def normalized_deficit(current: Dict[str, int], target: Dict[str, int]) -> Dict[str, float]:
    """Per-class shortfall in [0, 1]: ``1.0`` = nothing collected yet, ``0.0`` = target met.

    Classes absent from ``current`` count as zero collected — that is the whole point,
    since a class with no examples is the most valuable thing an annotator can add.
    """
    ...

def keypoint_deficit(visible_counts: Dict[str, int], target_per_point: int) -> Dict[str, float]:
    """Shortfall per keypoint, over the full 16-point schema.

    Points missing from ``visible_counts`` are treated as zero, so a keypoint nobody
    has ever placed carries the maximum deficit of 1.0.
    """
    ...

def count_placed_keypoints(keypoints: Iterable[Any]) -> Set[str]:
    """Names of the keypoints actually placed in one annotation (v in {1, 2}).

    Tolerates both ``{"name": ..., "v": ...}`` and ``{"label": ..., "visibility": ...}``
    shapes, and ignores malformed entries rather than raising — annotation blobs are
    written by several generations of the client.
    """
    ...

def whole_animal_gate(predicted_points: Set[str], min_points: int) -> bool:
    """Count-of-predicted-keypoints check. **Diagnostic only — do NOT gate on this.**

    Measured on the v4 pose model (scratchpad/gate_calibration.py, 131 frames), the
    model's per-point detection rate mirrors the training corpus's representation
    almost exactly:

        anal_fin_tip       corpus  2.7 %   model  3.3 %
        caudal_upper_tip   corpus 11.5 %   model  8.8 %
        dorsal_base_front  corpus 63.1 %   model 92.3 %

    The model has learned the corpus's blind spots. Gating on "model sees >= N
    points" therefore selects frames it is ALREADY good at and starves the very
    keypoints we need more of — a self-fulfilling loop that would quietly bake the
    current imbalance into every future model.

    Use ``whole_animal_bbox_gate`` instead: it keys off detection (reliable) rather
    than weak per-point predictions. This function is kept for reporting how much of
    the animal the model *thinks* it sees, which is a useful drift signal.
    """
    ...

def bbox_area_fraction(bbox: Sequence[float], frame_w: int, frame_h: int) -> float:
    """Fraction of the frame covered by ``bbox`` (x, y, w, h), clamped to [0, 1]."""
    ...

def bbox_is_uncropped(bbox: Sequence[float], frame_w: int, frame_h: int, edge_margin_frac: float=0.02) -> bool:
    """Does the detection sit clear of every frame edge?

    A box touching an edge means the animal continues out of shot, so the points
    beyond it are unplaceable — which is precisely how the pilot ended up with
    ``caudal_upper_tip`` marked v=0 (outside frame) in 249 of 295 frames.
    """
    ...

def animal_short_side_px(bbox: Sequence[float]) -> float:
    """Pixels across the animal's narrow axis. The honest measure of placeability.

    Area fraction alone cannot say whether a point is placeable, because it is
    relative to the frame: a shark filling 20% of a 640x360 frame is about 100 px
    tall, and anal_fin_tip on a 100 px animal is a few pixels of gradient. The same
    20% of a 2704x1520 frame is 430 px and perfectly annotatable.

    That distinction matters here specifically: the source clips measured on
    2026-08-16 run 1920x1080 to 3840x2160, but 82 of the 92 historical pose training
    frames are 640x360. Those frames passed an area-fraction gate and still could
    not support the caudal and ventral points, which are exactly the points sitting
    at 2.7% coverage.
    """
    ...

def whole_animal_bbox_gate(bbox: Sequence[float], frame_w: int, frame_h: int, *, min_area_frac: float=0.05, edge_margin_frac: float=0.02, min_short_side_px: float=0.0) -> bool:
    """Is the whole animal in shot, and big enough to annotate precisely?

    The primary pose gate. Uses only the detection box, which the model gets right
    ~92 % of the time, instead of the per-point predictions it gets wrong exactly
    where we need them. A frame passing this gate is valuable *because* the
    annotator can place the caudal and anal points the model cannot see.

    ``min_short_side_px`` adds an ABSOLUTE floor alongside the relative one.
    Defaults to 0 (off) so existing callers are unchanged; the scan supplies the
    configured value.
    """
    ...
ASPECT_BIN_EDGES = (1.8, 2.6, 3.4, 4.4)

def aspect_bin(width: float, height: float) -> int:
    """Coarse viewpoint bucket from the body box's aspect ratio.

    A proxy, not a measurement: it cannot tell left from right, or head-on from
    tail-on. It only has to separate "broadside again" from "something else",
    which is the axis the corpus is actually collapsed along.
    """
    ...

def viewpoint_deficit(counts: Dict[int, int]) -> Dict[int, float]:
    """Per-bin shortfall in [0, 1], where 1.0 means "nothing from this viewpoint yet".

    Normalised against the BUSIEST bin rather than a configured target: there is no
    principled target number of broadside frames, but "you have far fewer of these
    than of those" is exactly the signal worth ranking on.
    """
    ...

def pose_completeness_score(deficit: Dict[str, float], area_frac: float, viewpoint_rarity: float=0.0, *, viewpoint_weight: float=1.0) -> float:
    """Value of a whole-animal frame, scored PER CANDIDATE.

    Deliberately NOT weighted by which points the model predicted — see
    ``whole_animal_gate`` for why trusting those predictions inverts the ranking.

    Two things vary between candidates and both belong here:

    * ``area_frac`` — a larger animal carries more pixels, so points can be placed
      more precisely.
    * ``viewpoint_rarity`` — how under-represented this candidate's viewpoint bin
      is. Without it the ranking collapses: ``sum(deficit.values())`` is computed
      once per generate_work_items call and is therefore IDENTICAL for every
      candidate in the batch, so multiplying by it changes no order at all and the
      queue degenerates to "biggest animal first" globally. That is how a corpus
      ends up with 63.1% coverage on dorsal_base_front and 2.7% on anal_fin_tip:
      the biggest, most obvious broadside frames were always chosen, and they all
      show the same points.

    ``deficit`` is retained as a COMMON factor so the magnitude still falls as the
    corpus fills (a finished spec scores 0). Being common to every candidate in a
    batch, it cannot affect the ordering within one, which is exactly why it could
    never have been the whole score. An EMPTY deficit means "caller supplied no
    deficit information" and is treated as neutral, which is a different thing from
    a deficit that is present and all zeros, meaning "nothing left to collect".
    """
    ...

def pose_frame_score(predicted_points: Set[str], deficit: Dict[str, float]) -> float:
    """How much would labelling this frame close the keypoint gap?

    Sum of the deficits of the points the frame is predicted to contain. A frame
    showing the caudal cluster outscores one showing only the well-covered dorsal
    region, even if the latter has more points overall.
    """
    ...

def scar_candidate_score(predicted_class: Optional[str], deficit: Dict[str, float], uncertainty: float=0.0, *, uncertainty_weight: float=0.3) -> float:
    """Rank a proposed scar by class rarity, nudged by model uncertainty.

    Rarity dominates: a class with no examples must outrank a merely uncertain
    instance of an already-common class. ``uncertainty`` breaks ties within a class.
    An unknown/unpredicted class scores as maximally deficient — we cannot rule out
    that it is the rare one, and finding out is itself informative.
    """
    ...

def round_robin(items: Sequence[Any], key_fn: Callable[[Any], Any]) -> List[Any]:
    """Interleave items across buckets — one per bucket per pass — so the head of the
    queue spreads across categories instead of clustering.

    Bucket order and within-bucket order both follow input order, so the result is
    stable: same input, same queue. Mirrors ``db_mlops._round_robin``, restated here
    to keep this module import-free.
    """
    ...

def bootstrap_spread_key(item: Dict[str, Any]) -> Tuple:
    """Cold-start bucket: one bucket per (site, video).

    Deliberately coarse. Adding a frame bucket here would be actively harmful — it
    splits one video into several buckets, and since ``round_robin`` emits one item
    per bucket per pass, a long video would win *more* slots rather than fewer.
    Intra-video spacing is ``dedup_adjacent``'s job, not this key's.
    """
    ...

def dedup_adjacent(items: Sequence[Dict[str, Any]], window: int) -> List[Dict[str, Any]]:
    """Drop near-duplicate frames: within a video, keep an item only if its frame is
    at least ``window`` frames from one already kept. Order-preserving.

    This is the platform's biggest active-learning redundancy risk — consecutive
    frames are almost the same image, so labelling both costs twice and teaches once.
    """
    ...

def pose_complete_reason(deficit: Dict[str, float], area_frac: float, top_n: int=2) -> str:
    """Why this whole-animal frame — named by the points it makes placeable.

    Reads from the deficit, not from what the model predicted, so it stays honest
    about the weak points even though the model cannot see them.
    """
    ...

def pose_gap_reason(predicted_points: Set[str], deficit: Dict[str, float], top_n: int=2) -> str:
    """One line telling the annotator why this frame — the weakest points it adds.

    A locked queue reads as direction rather than deprivation when the reason is
    visible, so this string is stored per work item, not computed for display only.
    """
    ...

def class_gap_reason(predicted_class: Optional[str], deficit: Dict[str, float]) -> str:
    """One line telling the annotator why this scar candidate."""
    ...

def rank_candidates(candidates: Sequence[Dict[str, Any]], *, regime: str, score_fn: Callable[[Dict[str, Any]], float], reason_fn: Callable[[Dict[str, Any]], str], dedup_window: int=0) -> List[Dict[str, Any]]:
    """Order candidates for dispatch, annotating each with ``priority`` + ``gap_reason``.

    Returns new dicts; the inputs are not mutated. In BOOTSTRAP the score is still
    computed and stored (so the admin can see it) but ordering is by spread, because
    with a near-empty corpus every deficit is ~1.0 and score ordering is noise.
    """
    ...

def assign_split(video_id: Optional[str], split_ratios: Dict[str, float]) -> str:
    """Deterministically bucket a VIDEO into train/val/test.

    Split by video, never by frame. Frames from one video are near-duplicates, so a
    frame-level split puts near-identical images in train and test, silently
    inflating every metric — and it is unrecoverable once models have been trained
    and reported against it.

    Deterministic in ``video_id`` so the same video always lands in the same split,
    across processes and re-runs. No RNG: a reseeded shuffle would silently reshape
    an existing dataset.
    """
    ...
