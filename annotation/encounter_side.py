"""Encounter-level Left / Right / Both from per-frame landmark detections.

PURE ALGORITHM. Stdlib only: no Flask, no sqlite3, no file IO, no numpy, no
torch, no config reads. Same split as `annotation/scar_consensus.py` and
`annotation/signal_consensus.py`, so it runs in the ML-free test suite and can
be reasoned about without a model on disk.

WHAT THIS REPLACES
------------------
The annotator's encounter form asks a human "which sides of the animal were
visible: Left, Right, or Both". This module is the machine half of that answer.
The chain is: detect the shark -> detect anatomical landmarks as INDEPENDENT
detection classes -> per-frame flank from an anterior->posterior vector
(`frame_flank`) -> aggregate frames into the encounter answer (`encounter_side`).

Landmarks arrive as independent detections rather than as a joint pose because
coverage is the bottleneck, not accuracy: the pose-based flank estimator
declines on roughly 46% of frames because it needs a whole skeleton, whereas
this needs only TWO landmarks that are far enough apart along the animal.

THE SIGN CONVENTION - THE WORST AVAILABLE BUG
---------------------------------------------
A flipped sign inverts every answer in the system while still producing a
plausible-looking distribution, so it is written out here in full and pinned by
a test against `segmentation/pose_zones.determine_side`, which is the shipped
definition.

    dx = posterior.cx - anterior.cx   # horizontal component, head -> tail

    dx > 0  ->  "Left"
    dx < 0  ->  "Right"

Worked example, image coordinates, x increasing to the right:

    Shark FACING IMAGE-LEFT.  head at x=100, tail at x=500.
      head->tail points image-RIGHT, dx = +400  ->  LEFT flank visible.

    Shark FACING IMAGE-RIGHT. head at x=500, tail at x=100.
      head->tail points image-LEFT, dx = -400   ->  RIGHT flank visible.

Derivation (from the `determine_side` docstring, which says DO NOT FLIP THIS):
with left = dorsal x anterior in a right-handed image frame (screen-right = +X,
screen-up = +Y, toward-viewer = +Z), a shark facing image-left has anterior
a = -X and dorsal d = +Y, so left = d x a = Y x (-X) = +Z, pointing at the
camera. The LEFT flank is the one you can see. `pose_zones` computes exactly
this as `cross_z = body_vec[0] = caudal.x - snout.x`, then `"Left" if cross_z >
0 else "Right"` - the same comparison on the same quantity.

WHY THE CONVENTION IS RESTATED HERE RATHER THAN IMPORTED
--------------------------------------------------------
`pose_zones.determine_side` is not a sign function: it is a 16-slot numpy
skeleton API that also does head-on detection, dorsal-up fallback and
confidence capping, and importing it would drag numpy into a module whose whole
point is that it takes plain values. The convention is one comparison, not an
algorithm. So it is duplicated deliberately and the DUPLICATION IS PINNED:
`tests/test_encounter_side.py` builds synthetic left-facing and right-facing
skeletons and asserts both functions return the same string. That is the same
pattern `tests/test_pose3d_agreement.py` uses to keep a borrowed definition from
drifting on this side.

ANCHOR SELECTION IS A RANKING, NOT TWO LISTS - AND HERE IS THE MEASUREMENT
--------------------------------------------------------------------------
There is no "head anchor" set and no "tail anchor" set. Every landmark carries
an ANTERIOR->POSTERIOR RANK (`LANDMARK_RANK`), and a frame's axis is the
available pair with the LARGEST rank separation. Two hardcoded lists were tried
first and were measurably worse, for a structural reason: they had to name
landmarks in advance, and the two most-placed landmarks in this corpus
(`dorsal_base_front`, 184/240; `dorsal_fin_tip`, 133/240) were in NEITHER list,
so a frame carrying both of them and nothing else produced no axis at all.

Measured over the 240 annotation rows carrying >=1 placed keypoint (v>0), with
`scripts/export_yolo_pose.RENAME` applied so legacy names resolve. 228 of those
240 (95.0%) carry >=2 DISTINCT landmarks, which is the ceiling for ANY
two-anchor method:

    selector                                     frames with a usable pair
    rank-based, min_rank_separation=3 (shipped)  189/240 = 78.8%
    the two hardcoded lists it replaces          103/240 = 42.9%
    the anchor set pose_zones.determine_side uses 118/240 = 49.2%

Of the 189, 188 also cleared the head-on gate, so 188/240 = 78.3% of these
frames get an actual flank. Sensitivity of the pair count to the separation
floor, same 240 frames: 1 -> 227 (94.6%), 2 -> 198 (82.5%), 3 -> 189 (78.8%),
4 -> 174 (72.5%). Exactly ONE of the 240 has two or more distinct landmarks but
no rank-separated pair at all, i.e. every landmark on it sits at the same rank.

The extra coverage costs no disagreement. On every frame where a narrower
selector also decided, the rank selector returned the SAME flank: 118/118
against the pose_zones set, 103/103 against the old lists.

CAVEATS THAT MUST TRAVEL WITH THOSE NUMBERS
  * They are HUMAN keypoint placements, not detector outputs. They say what
    share of frames a person put two ranked landmarks on. A trained detector
    will find a different, probably smaller, set, so treat 78.8% as an upper
    bound on what a model inherits, not as a model result.
  * 242 of 248 trainable labels come from ONE annotator, so the placement
    pattern the coverage is measured on is one person's habits.
  * NOTHING HERE MEASURES ACCURACY. There is still no per-frame flank ground
    truth in this checkout (`frame_hints` is empty,
    `exports/view_class_labels.jsonl` is absent), so what share of those 188
    decisions is CORRECT is unmeasured. Coverage is not correctness.

WHY min_rank_separation EXISTS
------------------------------
Two adjacent landmarks define a short, noisy axis whose horizontal sign is one
detection jitter from flipping, so a pair must span at least
`min_rank_separation` ranks (default 3). Equal-rank pairs are the extreme case
and are worth naming: `dorsal_fin_tip` vs `dorsal_base_front`, or
`caudal_upper_tip` vs `caudal_lower_tip`, are separated ACROSS the animal rather
than along it, so their axis is near-VERTICAL. At the default they cannot be
chosen at all; if a caller lowers `min_rank_separation` to 0 they become
selectable and the `min_dx_frac` head-on gate is what still rejects them. That
gate is not optional and both tests pin it.

WHAT A SINGLE FRAME CANNOT SAY
------------------------------
`frame_flank` never returns "Both". One frame shows one flank; "Both" is a
statement about an encounter's COVERAGE across frames, and manufacturing it
per-frame is how `sides_visible` came to be misread as a per-frame fact (it
agrees with the true per-frame flank 58.2% of the time against a 54.5%
always-Left baseline). A frame that cannot be decided returns side=None with a
reason, never a guess and never "Both".

WHY "BOTH" NEEDS TWO FLOORS
---------------------------
"Both" asserts coverage the encounter may not have, and a downstream reader
cannot tell an asserted "Both" from an observed one. One mislabelled frame in a
200-frame clip must therefore not be able to produce it. A flank counts as
present only if it clears an absolute floor (`min_frames_per_side`, default 3)
AND a share floor (`min_share_per_side`, default 0.15) of the DECIDED frames.
The floors are on COUNTS, not on the confidence-weighted votes: weights are
whatever the detector says, and a model that is confidently wrong on one frame
would otherwise buy a side outright. Weights are used for `margin` only.

A COROLLARY WORTH STATING: a unit of fewer than `min_frames_per_side` frames
can NEVER produce an answer. A single still is not a small encounter, it is an
unanswerable one, and the caller should say so rather than paying for inference
and printing `below_floors`.

A THIRD FLOOR, AND IT IS ON TIME: THE ONE-FRAME FLIP
----------------------------------------------------
A share floor is a GLOBAL test and a flip is a LOCAL event, so the share floor
protects a short clip by accident and stops protecting a long one. Measured on
this corpus's real detector output - 20 clips walked at detector conf 0.15,
stride 5, of which 19 produced any decided frame at all:

    AN13120503_11ft_FEMALE_1   7 minority-side (Left) votes against 75 Right,
                               arriving as runs of 1, 1, 2 and 3 against Right
                               runs of 1, 20, 26 and 28. Viewed, the Left votes
                               are mostly the animal swimming near-axially away
                               from the camera. Noise. The 0.15 share floor
                               happened to suppress them (7/82 = 0.085); a
                               longer clip at the same noise RATE would not have
                               been protected at all.
    AN15112302_XX_MALE_03      a GENUINE turn. Left runs of 1, 1, 1, 10 and 50
                               against Right runs of 1, 1, 1, 1, 24 and 67. The
                               human said Both, and Both is the correct answer.

Across all 19 clips that decided anything, the MINORITY side's longest run was
0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 5, 7 - and then 50, which is
that one genuine turn. RUN LENGTH separates a real second flank from detection
noise far better than global share does, so `min_run_frames` (default 3)
discounts any decided frame that sits in a run shorter than it. An animal does
not show you its other flank for one sampled frame and then take it back.

The same split holds at the coarser setting the corpus was first walked at
(conf 0.25, stride 15): minority longest run 0 to 4 on 18 clips, 22 on the turn.

3 is a DESIGN CHOICE - the shortest run that is not one frame plus a neighbour -
not a value fitted to those 19 clips. Nothing here was tuned to them: at the
default the two clips above keep the answers they already had, and what changes
is FEMALE_1's minority vote count, 7 -> 3. `scripts/predict_encounter_side.py`
exposes it as `--min-run-frames` so it can be swept rather than argued about.

The gate is TEMPORAL, so it applies only where there is a time axis: runs are
found within ONE clip (`video_id`), over the DECIDED frames of that clip ordered
by `frame_number`. Undecided frames are GAPS and do NOT break a run - the
detector losing the animal for a second is not the animal turning around. Only
an opposite-side decided frame breaks a run. A still (`is_still`) and a frame
with no `frame_number` have no temporal neighbours at all, so each is its own
stable run of one and the gate cannot touch it.

A discounted frame is REPORTED, NOT DELETED: it stays in `n_decided` and
therefore in `coverage` (the detector really did read a flank off it, and
hiding it would make a noisy clip look like one the model could not see), it is
counted in `n_unstable` and in the `unstable` reason bucket, and it contributes
nothing to `n_left`, `n_right`, the shares, the weights or the presence tests.
`longest_run_left` / `longest_run_right` travel with every result so a reader
can see the evidence the gate acted on.

The honest failure mode of this module is LOW COVERAGE, not a wrong side, so
`coverage` and the per-reason census are reported on every result and should be
quoted with every number that comes out of it.

THRESHOLDS HAVE NO SHARK EVIDENCE YET
-------------------------------------
Every default in `SideConfig` is a starting point, not a measurement. The only
encounter-level ground truth in this checkout is 14 usable rows (19
`media_type='video'` rows carry a `sides_visible` label; 5 of them disagree
across their own rows and are refused). Any score from this module measures
agreement with one person's conventions on a sample of 14. Say so wherever a
number is reported; do not quote these thresholds as validated. `min_run_frames`
is the one knob with any shark observation behind it (the run-length split
above, on 19 clips) and even that is an observation, not a validation.
"""
from __future__ import annotations
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Tuple
_PRECISION = 6

@dataclass(frozen=True)
class SideConfig:
    """Knobs. Every one is a threshold, not a feature gate: there is no "off"."""
    min_score: float = 0.25
    min_axis_px: float = 20.0
    min_dx_frac: float = 0.2
    min_rank_separation: int = 3
    min_frame_confidence: float = 0.0
    min_frames_per_side: int = 3
    min_share_per_side: float = 0.15
    min_run_frames: int = 3

@dataclass(frozen=True)
class FrameFlank:
    """One frame's answer. `side` is 'Left', 'Right' or None. NEVER 'Both'."""
    side: Optional[str] = None
    confidence: float = 0.0
    basis: Optional[str] = None
    dx: float = 0.0
    dy: float = 0.0
    axis_px: float = 0.0
    head_score: float = 0.0
    tail_score: float = 0.0
    rank_separation: int = 0
    frame_number: Optional[int] = None
    video_id: Optional[str] = None
    is_still: bool = False

    def as_dict(self) -> Dict[str, Any]:
        ...

@dataclass(frozen=True)
class EncounterSide:
    """The encounter answer, with the evidence that produced it.

    `coverage` is decided / total frames, where DECIDED includes the frames the
    `min_run_frames` gate discounted (`n_unstable`). Those frames still count as
    read: the detector did put a flank on them, and burying that in the coverage
    denominator would make a clip full of one-frame flips look like a clip the
    model could not see at all. They count as votes nowhere - not in `n_left` or
    `n_right`, not in the shares, not in the weights, not in the presence tests.
    So `n_left + n_right + n_unstable == n_decided`, and the shares are over the
    votes, not over `n_decided`.
    """
    side: Optional[str] = None
    n_left: int = 0
    n_right: int = 0
    n_undecided: int = 0
    coverage: float = 0.0
    margin: float = 0.0
    n_frames: int = 0
    n_decided: int = 0
    weight_left: float = 0.0
    weight_right: float = 0.0
    share_left: float = 0.0
    share_right: float = 0.0
    left_present: bool = False
    right_present: bool = False
    answerable: bool = True
    n_unstable: int = 0
    longest_run_left: int = 0
    longest_run_right: int = 0

    def as_dict(self) -> Dict[str, Any]:
        ...

def flank_for_dx(dx: float) -> Optional[str]:
    """Biological flank from the horizontal component of the head->tail vector.

    dx = posterior.x - anterior.x, in image pixels with x increasing right.

        dx > 0  (head->tail points image-RIGHT; the shark FACES IMAGE-LEFT) -> 'Left'
        dx < 0  (head->tail points image-LEFT; the shark FACES IMAGE-RIGHT) -> 'Right'
        dx == 0 -> None, the animal is vertical in frame and has no flank answer

    Identical comparison to `segmentation/pose_zones.determine_side`, which
    computes `cross_z = caudal.x - snout.x` and returns "Left" if cross_z > 0.
    DO NOT FLIP THIS. See the module docstring for the derivation and for the
    test that pins the two implementations together.
    """
    ...

def _detection_fields(det: Any) -> Optional[Tuple[str, float, float, float]]:
    """(class_name, cx, cy, score) from one detection, or None if unusable.

    Accepts a mapping with `class_name`/`cx`/`cy`/`score`; `name` and
    `confidence` are tolerated as aliases because that is the shape ultralytics
    results are most often reshaped into, and a silently empty anchor list is a
    much worse failure than an alias. Anything malformed is SKIPPED, never
    raised on and never coerced to a plausible coordinate.
    """
    ...

def _best_by_class(detections: Optional[Iterable[Any]], min_score: float) -> Dict[str, Tuple[float, float, float]]:
    """class_name -> (cx, cy, score) for the highest-scoring detection of each class.

    Ties break on the LOWER cx then the LOWER cy, so a frame with two identically
    scored detections of one class gives the same answer on every run.
    """
    ...

def rank_map(cfg: Optional[SideConfig]=None) -> Dict[str, int]:
    """The configured anterior->posterior ranking as a dict. Malformed entries drop."""
    ...

def _pick_anchor_pair(best: Mapping[str, Tuple[float, float, float]], ranks: Mapping[str, int], min_rank_separation: int) -> Optional[Tuple[Tuple[str, float, float, float], Tuple[str, float, float, float], int]]:
    """The available pair spanning the most ANIMAL, as (anterior, posterior, sep).

    Selection order, worst-case O(16^2) on a 16-class detector:
      1. largest rank separation - the axis the two points actually span;
      2. then largest pixel separation - between two pairs that span the same
         anatomy, the longer one has the steadier sign;
      3. then largest summed score - the detector's own preference, last,
         because a confident short axis is still a short axis;
      4. then lexicographic on (anterior, posterior), so the answer is the same
         on every run even when a frame is perfectly symmetric.
    Returns None when no pair clears `min_rank_separation`.
    """
    ...

def frame_flank(detections: Optional[Iterable[Any]], cfg: Optional[SideConfig]=None) -> FrameFlank:
    """One frame of landmark detections -> 'Left', 'Right', or an explained None.

    `detections` is a list of {class_name, cx, cy, score} for ONE frame, in
    IMAGE pixels. Never raises: every failure is a reason string.
    """
    ...

def _opt_frame_number(value: Any) -> Optional[int]:
    """An integer frame index, or None for "this frame has no place in time".

    A frame with no usable index is EXEMPT from the run gate rather than sorted
    to position 0, because coercing an unreadable value to a number would put an
    arbitrary frame at the head of a clip's sequence and change which runs form.
    """
    ...

def _as_flank(item: Any) -> FrameFlank:
    """FrameFlank, or a mapping shaped like one (e.g. reloaded from JSON).

    The three temporal fields are carried through, because they are what the run
    gate reads and a JSON round trip that dropped them would silently disarm the
    gate on exactly the reloaded corpus a sweep is run over. A pre-gate file has
    none of them and degrades to "no temporal position", i.e. every decided frame
    is its own stable run - the old behaviour, which is the right default.
    """
    ...

def _run_stability(voting: List[Tuple[int, FrameFlank]], min_run_frames: int) -> Tuple[FrozenSet[int], int, int, Dict[Tuple[bool, str], Tuple[int, int]]]:
    """Which voting frames sit in a run too short to believe, and how long runs get.

    `voting` is (position, flank) for every frame that WOULD vote, in input
    order. Returns (unstable positions, longest_run_left, longest_run_right,
    longest runs PER CLIP).

    The per-clip runs are returned rather than recomputed by a caller because
    they are the same walk: a second implementation of "how long was the run"
    drifts from this one, and the drift shows up as a stored diagnostic that
    contradicts the gate it is supposed to explain.

    A run is contiguous over the DECIDED frames of ONE clip, ordered by
    `frame_number`. Undecided frames never enter the sequence, so they are gaps
    and do not break a run; only an opposite-side decided frame does. A frame
    that is a still, or that carries no frame number, has no temporal
    neighbours: it counts as its own stable run of one and is never discounted.

    Deterministic by construction: clips are visited in sorted key order and
    each clip's frames are sorted by (frame_number, input position), so nothing
    depends on dict iteration order or on the order the caller happened to
    concatenate its clips in.
    """
    ...

@dataclass(frozen=True)
class _Partition:
    """Everything the answer and the per-clip census both read, computed once.

    It exists so there is exactly ONE implementation of the two vote-removing
    filters (`min_frame_confidence`, then `min_run_frames`). A second copy in a
    caller that only wants per-clip numbers drifts from this one, and the drift
    surfaces as a stored diagnostic that contradicts the gate whose output it is
    meant to explain -- always flattering, because a looser rule finds flicker
    where the gate found a flank.
    """
    flanks: List[FrameFlank]
    voting: List[Tuple[int, FrameFlank]]
    confidences: Dict[int, float]
    reasons: Counter
    unstable: FrozenSet[int]
    longest_left: int
    longest_right: int
    clip_runs: Dict[Tuple[bool, str], Tuple[int, int]]

def _partition(frame_flanks: Optional[Iterable[Any]], cfg: SideConfig) -> _Partition:
    """Coerce the input, drop the votes the two filters drop, and time the runs."""
    ...

def clip_census(frame_flanks: Optional[Iterable[Any]], cfg: Optional[SideConfig]=None) -> List[Dict[str, Any]]:
    """Per-clip counts that RECONCILE with `encounter_side` on the same input.

    One entry per clip, in first-appearance order, carrying the same four
    populations the encounter answer is built from -- `n_left`, `n_right`,
    `n_unstable`, `n_undecided` -- plus that clip's longest same-side runs. Every
    field sums across clips to the matching field of `encounter_side`, so a
    reader can do the arithmetic and have it come out.

    WHY IT LIVES HERE AND NOT IN THE CALLER THAT STORES IT
    ------------------------------------------------------
    An encounter answer of "Both" assembled from one clip that only ever showed
    Left and one that only ever showed Right is a different claim from one clip
    that flipped, and the aggregate columns cannot tell them apart -- which is
    why the breakdown is stored at all. But a breakdown computed by a second,
    independent walk is worse than none: it is read as an explanation of the
    answer while disagreeing with it. In particular an undecided frame is a GAP
    and does not break a run (the detector losing the animal for a second is not
    the animal turning around), and the counts here are POST-gate, so a clip's
    `n_left` is votes cast, never raw detections.
    """
    ...

def encounter_side(frame_flanks: Optional[Iterable[Any]], cfg: Optional[SideConfig]=None) -> EncounterSide:
    """Aggregate per-frame flanks into the encounter's Left / Right / Both / None.

    A flank is PRESENT only if it clears both floors. Both present -> 'Both';
    exactly one -> that one; neither -> None with a reason. Never raises.

    `answerable` is False when there were fewer frames than
    `cfg.min_frames_per_side`, in which case `below_floors` was guaranteed
    before any pixel was read. Reporting that is the difference between "we
    looked and could not tell" and "nobody could have told from this input".

    THREE FILTERS, IN THIS ORDER, AND THE ORDER IS THE DESIGN:
      1. `min_frame_confidence` - a decided frame too weak to vote at all;
      2. `min_run_frames` - a decided frame in a run too short to be a turn,
         within its own clip, over the frames that survived (1);
      3. `min_frames_per_side` and `min_share_per_side` - the presence floors,
         applied to what survived (2), unchanged.
    Steps 1 and 2 remove VOTES; step 3 reads them. Running the floors first
    would let a burst of flicker buy a side before anything had asked whether it
    was a burst.
    """
    ...

@dataclass(frozen=True)
class ClipSide:
    """One clip's Left / Right / Both / None, with the evidence that produced it.

    Same shape and same arithmetic as `EncounterSide`, one grain down, minus the
    fields that only mean something across clips (`weight_*`, `margin`, the frame
    reason census). `reason` is one of `CLIP_REASONS`.
    """
    side: Optional[str] = None
    video_id: Optional[str] = None
    is_still: bool = False
    n_left: int = 0
    n_right: int = 0
    n_unstable: int = 0
    n_undecided: int = 0
    n_frames: int = 0
    coverage: float = 0.0
    share_left: float = 0.0
    share_right: float = 0.0
    longest_run_left: int = 0
    longest_run_right: int = 0
    left_present: bool = False
    right_present: bool = False
    answerable: bool = True

    def as_dict(self) -> Dict[str, Any]:
        ...

def _int(value: Any) -> int:
    """A count out of a stored blob, degrading to 0. Never raises: this runs
    inside a request that must not fail because a legacy row is short a key."""
    ...

def clip_side(clip: Mapping, cfg: Optional[SideConfig]=None) -> ClipSide:
    """The Left / Right / Both / None for ONE clip, from its stored census entry.

    WHY THIS EXISTS AT ALL
    ----------------------
    The annotator has one clip open, and a suggestion about footage they will
    never watch is one they cannot check — pressing Accept on it is a rubber
    stamp, which is exactly the anchoring the click-to-accept design exists to
    avoid. Storage already agreed with that grain before this function did:
    `sides_visible` lives on the per-clip annotation blob, and
    `encounter_pass_clips` exists precisely because sides differ across the clips
    of one encounter (22 of 112 pairs). The encounter-wide answer is the UNION of
    per-clip answers and is additive context, not the claim being made.

    IT APPLIES STEP 3 ONLY, AND THAT IS THE WHOLE POINT
    ----------------------------------------------------
    `encounter_side` runs three filters in order: (1) `min_frame_confidence`,
    (2) the `min_run_frames` flicker gate, (3) the presence floors
    `min_frames_per_side` / `min_share_per_side`. **Steps 1 and 2 already ran**
    when the census entry was written — `clip_census` shares one `_partition`
    with `encounter_side`, so `n_left` / `n_right` here are POST-gate votes and
    the discounted frames are already sitting in `n_unstable`. This function
    re-runs NEITHER. Re-deriving runs from counts is not possible anyway (the
    frame order is gone), and re-applying a confidence floor to numbers that
    already cleared one would silently discount the same frames twice.

    So this takes the votes as given and asks step 3's question of them, with
    `present()` mirroring `encounter_side`'s exactly — which is what makes a
    one-clip encounter and that clip return the same side. There is no second
    definition of "present" in this module and there must not be.

    A STILL IS NOT A SMALL CLIP
    ---------------------------
    One frame can never clear `min_frames_per_side`, so a still is returned as
    `side=None, reason="still"` rather than as a one-frame guess or as the
    `below_floors` it would otherwise be. A weak suggestion is an anchor, not
    help; and the per-frame scar-form hint already covers stills at the grain
    they can actually answer. The rule is unconditional on the configured floor:
    even at `min_frames_per_side=1` a single image is not evidence of coverage.

    Never raises. A missing or malformed key reads as 0, because this runs inside
    a request whose worst acceptable outcome is "no suggestion".
    """
    ...

def config_from_mapping(raw: Any) -> SideConfig:
    """A `SideConfig` from a stored `config` blob, ignoring what it does not own.

    The precompute freezes its whole run configuration into the row — device,
    imgsz, stride, the weights hash — beside the thresholds. Only the thresholds
    are `SideConfig` fields, so anything else is dropped rather than passed on,
    and any value that will not coerce falls back to that field's default. The
    point is that a suggestion is judged against THE FLOORS IT WAS COMPUTED
    UNDER, not against whatever today's defaults happen to be.
    """
    ...
