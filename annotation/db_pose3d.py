"""Stream H (3D lift & volumetrics) — verified silhouettes + measured segments.

Per the integration contract (plans/00-SHARED-CONTEXT.md §3.2) this is a per-stream DB
module: it reuses `get_conn()` from annotation/database.py and NEVER edits the
database.py monolith or the scar consensus algorithm. The tables are created by
scripts/migrate_schema_v70.py; the defensive `init_pose3d_tables()` here mirrors that DDL
so the module also works before the formal migration runs — which is the normal case in
production, where migrations do NOT auto-run (the running app only calls init_*_tables();
the versioned chain runs at Docker build time against a throwaway layer).

This module produces what `marine-cv/shark-pose-3d` consumes to fit its rigged SharkSMPL
template to real footage and read VOLUME off the fitted mesh. Design rationale lives in
plans/14-stream-h-pose3d.md; the three rules that shape the code:

  1. Geometry is stored in IMAGE pixels against a declared image_w x image_h, never in
     display coordinates — zoom and pan differ per annotator and per session.
  2. Scale is DERIVED from stored endpoints, never stored as a scalar. A stored px_per_m
     freezes an assumption (which port? which depth plane?) a later reader cannot audit.
  3. `time_sec` is the canonical temporal anchor. Frame numbers are not: this repo has
     already written a whole track set onto the wrong frame by assuming 30fps against
     59.94fps footage.

The pure geometry helpers (`segment_length_px`, `project_station`, `derive_scale`,
`mask_iou`) take plain values and touch no database, the same split
`signal_consensus.py` uses — so they are testable without a fixture DB.
"""
from __future__ import annotations
import json
import logging
import math
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from annotation.database import get_conn
from .identity import norm_annotator as _norm_annotator
from .signal_consensus import cohen_kappa as _cohen_kappa
from .signal_consensus import _fleiss_with_coverage
_MAX_RETRY = 5

class Pose3DValidationError(ValueError):
    """A mask or segment that must be refused rather than coerced into validity."""

def init_pose3d_tables() -> None:
    """Idempotently ensure the Stream H tables exist (mirrors v70)."""
    ...

def _retry_write(fn):
    """Run a write closure, retrying on 'database is locked' (mirrors core CRUD)."""
    ...

def _now() -> str:
    """Timezone-aware UTC timestamp (same rationale as db_signals._now)."""
    ...

def _row(r: Optional[sqlite3.Row]) -> Optional[dict]:
    ...

def _rows(rs: Iterable[sqlite3.Row]) -> List[dict]:
    ...

def segment_length_px(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean length of a segment in image pixels."""
    ...

def project_station(px: float, py: float, ax1: float, ay1: float, ax2: float, ay2: float) -> float:
    """Fraction along the body axis (0 = snout end, 1 = tail end) of a point.

    Chord stations are the scalar that says WHERE along the animal a width was measured,
    so they must be expressed against the axis actually drawn on that frame rather than
    against raw pixel coordinates — the same frame at a different zoom, or a shark
    swimming the other way, would otherwise produce incomparable numbers.

    The projection is clamped to [0, 1]: a chord marginally past the snout tip is a
    click-precision artifact, not a measurement outside the animal.
    """
    ...

def derive_scale(segments: Sequence[dict]) -> Optional[dict]:
    """Derive pixels-per-metre for one frame from its scale-reference segments.

    Returns None when the frame carries no usable referent — which is the honest answer,
    and lets a consumer tell "not scaled" from "scaled to 1.0". Never guesses.

    **On-animal referents win over in-scene ones**, always, even when an in-scene referent
    is longer and would look more precise. A referent only scales its own depth plane, and
    under a flat port the magnification is depth-dependent; a diver behind the shark
    measures the diver's plane. Averaging the two would produce a number that is wrong in
    a way no downstream check can detect.
    """
    ...

def mask_iou(rle_a: Optional[str], rle_b: Optional[str]) -> Optional[float]:
    """IoU between two COCO-RLE masks, or None when it cannot be computed.

    Computed SERVER-SIDE, never accepted from the client — a client-supplied agreement
    score is a self-graded exam. Returns None rather than 0.0 when pycocotools is absent
    or a mask is missing: 0.0 would read as "the human and the model disagreed
    completely", which is a claim this function did not verify.
    """
    ...

def mask_rle_from_png_b64(png_b64: str, image_w: int, image_h: int) -> str:
    """Encode a client-painted PNG mask into canonical COCO RLE, server-side.

    The browser paints on a canvas and ships a PNG; the RLE is minted here. Two reasons
    it is not the client's job: COCO's compressed `counts` is a byte-level encoding that
    a hand-rolled JS implementation would get subtly wrong (and a subtly wrong mask still
    decodes), and `iou_vs_source` is only meaningful if both masks came through the same
    encoder. Same principle as never accepting a client-supplied agreement score.

    Any non-zero pixel is foreground — the brush paints opaque white, and antialiased
    edges must resolve one way rather than to a threshold nobody recorded.
    """
    ...

def mask_area_px(rle: Optional[str]) -> Optional[int]:
    """Foreground pixel count of a COCO-RLE mask, or None if uncomputable."""
    ...

def validate_mask(*, view_class: str, verdict: str, part: str='whole', image_w: int, image_h: int, time_sec: float, mask_rle: Optional[str], reject_reason: Optional[str]=None) -> None:
    """Check one silhouette. Raises Pose3DValidationError; never coerces."""
    ...

def validate_segment(*, kind: str, label: str, x1: float, y1: float, x2: float, y2: float, image_w: int, image_h: int, real_length_m: Optional[float]=None, referent_plane: Optional[str]=None, length_measure: Optional[str]=None, station: Optional[float]=None) -> dict:
    """Check one measured segment and return its normalised field values.

    Pure — the cross-row checks that need the frame's view class and its axis live in
    `create_segment`, the same split `signal_consensus` uses against `db_signals`.
    """
    ...

def upsert_mask(*, video_id: str, frame_number: int, time_sec: float, image_w: int, image_h: int, view_class: str, verdict: str, annotator: str, part: str='whole', mask_rle: Optional[str]=None, source_mask_rle: Optional[str]=None, encounter_code: Optional[str]=None, view_confidence: Optional[int]=None, reject_reason: Optional[str]=None, fins_included: bool=False, occlusion: Optional[Sequence[str]]=None) -> dict:
    """Create or replace this annotator's silhouette for one frame.

    One human, one mask per frame (the UNIQUE constraint) — re-submitting is an edit, not
    a second opinion. Multi-rater fusion (STAPLE / soft-label averaging) is a later phase
    and stays possible precisely because rows are per-annotator rather than merged now.
    """
    ...

def get_mask(mask_id: int) -> Optional[dict]:
    ...

def list_masks(*, video_id: Optional[str]=None, encounter_code: Optional[str]=None, annotator: Optional[str]=None, view_class: Optional[str]=None, verdict: Optional[str]=None, part: Optional[str]=None, include_rejected: bool=True, limit: int=2000) -> List[dict]:
    ...

def delete_mask(mask_id: int, *, annotator: str, is_admin: bool=False) -> bool:
    """Soft-delete a silhouette AND every chord measured against it.

    The chords have to go with it. A chord is a claim about a cross-section of THIS
    outline; once the outline is retracted the number has no referent. Worse, leaving them
    live is a way around the guard in `upsert_mask`: retract the mask, re-create it with a
    different view class (the guard only sees live masks, so it does not fire), and the
    surviving chord is now measured on an axis that view cannot show — the exact
    undetectable error `_VIEW_CHORDS` exists to refuse.

    The hard-delete path is already covered by the FK CASCADE, which became real when
    foreign keys were enforced. This is the soft path, which the CASCADE cannot see.
    """
    ...

def create_segment(*, video_id: str, frame_number: int, time_sec: float, kind: str, label: str, x1: float, y1: float, x2: float, y2: float, image_w: int, image_h: int, annotator: str, mask_id: Optional[int]=None, real_length_m: Optional[float]=None, real_length_source: Optional[str]=None, referent_plane: Optional[str]=None, length_measure: Optional[str]=None, station: Optional[float]=None, confidence: Optional[int]=None, notes: str='') -> dict:
    """Insert one measured segment, enforcing the cross-row rules.

    Beyond `validate_segment`'s shape checks, a chord must be physically meaningful on the
    view it was drawn on:

      * a `width` is only readable from a dorsal/ventral (or head-on) frame, a `height`
        only from a lateral (or head-on) one, and neither from an oblique frame;
      * on the views where the body axis lies in-plane, the chord's station is PROJECTED
        onto the axis actually drawn on that frame rather than trusted from the client.

    Both refusals exist because a mislabelled chord is undetectable downstream: it is a
    number of the right magnitude on the wrong axis, and it enters the volume integral
    looking exactly like a real measurement.
    """
    ...

def _frame_masks(video_id: str, frame_number: int, annotator: str) -> List[dict]:
    """Every part this annotator has outlined on one frame."""
    ...

def _frame_mask(video_id: str, frame_number: int, annotator: str, part: Optional[str]=None) -> Optional[dict]:
    """One part's mask. With `part` unset, prefer `body` over `whole`.

    That preference is deliberate and only affects the chord path: a chord wants the
    outline of the ANIMAL, and where a labeler has bothered to trace `body` separately it
    is because a fin was in the way.
    """
    ...

def _frame_axis(video_id: str, frame_number: int, annotator: str) -> Optional[dict]:
    ...

def list_segments(*, video_id: Optional[str]=None, frame_number: Optional[int]=None, annotator: Optional[str]=None, kind: Optional[str]=None, mask_id: Optional[int]=None, limit: int=5000) -> List[dict]:
    ...

def delete_segment(segment_id: int, *, annotator: str, is_admin: bool=False) -> bool:
    ...

def frame_bundle(video_id: str, frame_number: int, annotator: str) -> dict:
    """Everything this annotator has recorded on one frame, plus the derived scale."""
    ...
FEET_TO_METERS = 0.3048

def recorded_length_m(encounter_code: Optional[str]) -> Optional[dict]:
    """The field-recorded body length for an encounter, in metres, or None.

    Reads `reid_sightings.size_ft` (Stream A's import of the encounter metadata CSVs,
    whose `size` column is keyed by PhotoID == the encounter code). Returns None rather
    than guessing when the table is absent, the encounter is unknown, or no size was
    recorded — an invented length would scale every measurement on the frame.

    `measure` is reported as `total_length` because that is what the field column means;
    the caller must NOT pair it with a snout-to-caudal-notch span, which is fork length.
    """
    ...

def coverage_stats() -> dict:
    """Corpus-level coverage, in the terms that decide whether volume is reachable.

    `views` matters more than the totals: without dorsal/ventral (or head-on) frames there
    is no width axis, and volume stays governed by the template's girth prior no matter how
    many lateral silhouettes are banked.
    """
    ...
CONFIDENT_MIN = 4
STATION_TOL = 0.05

def _mean(vals: Sequence[Optional[float]]) -> Optional[float]:
    """Mean of the values that exist. None (not 0.0) when nothing is comparable."""
    ...

def _unordered_pairs(items: Sequence[Any]) -> List[Tuple[Any, Any]]:
    ...

def match_chords(a_chords: Sequence[dict], b_chords: Sequence[dict], *, station_tol: float=STATION_TOL) -> dict:
    """Greedily pair two annotators' chords on one frame. Pure — no DB.

    A chord is "the animal is this wide/tall HERE", so two chords are the same
    measurement only when they carry the same label and sit at nearly the same station.
    Matching is one-to-one and greedy on |Δstation| so it is deterministic and so one
    person's five chords cannot all pair against another's single one.

    Lengths are compared in PIXELS and only between chords drawn at the same declared
    resolution. Two annotators working from different renditions of a frame produce px
    numbers that are not on the same ruler, and a ratio between them is a plausible-
    looking artifact — the same failure `mask_iou`'s size check refuses.

    Callers must pass chords from two DIFFERENT annotators. One person's two adjacent
    chords pairing with each other would read as two people agreeing, which is the
    easiest way there is to inflate a reliability figure (Stream F refuses the same
    merge in its clusterer).
    """
    ...

def frame_agreement(video_id: str, frame_number: int, *, part: str='whole') -> dict:
    """Inter-annotator agreement for one (video, frame, part) group.

    Returns a group with a single annotator too — `n_pairs = 0` and every agreement
    figure None. "Nobody has given a second opinion yet" is an answer; an error or an
    invented 1.0 is not.

    The result carries NO geometry: no RLE, no endpoints, no coordinates. That is
    structural, not incidental. A labeler must not be able to learn where a peer put
    their line, and the safest way to guarantee it is for the derived scalars to be the
    only thing this function can return. `redact_agreement_for` then only has to remove
    identities.
    """
    ...

def multi_rater_groups(*, video_id: Optional[str]=None, encounter_code: Optional[str]=None, part: Optional[str]=None, participant: Optional[str]=None, min_annotators: int=2, limit: int=500) -> List[Tuple[str, int, str]]:
    """(video_id, frame_number, part) keys that ≥ `min_annotators` people have outlined.

    `participant` restricts to groups that annotator is IN. That is the default read
    scope for a labeler and it is doing real work, not tidiness: a group they have not
    joined would tell them a peer's view judgement on a frame they have not drawn yet,
    which is the anchoring this whole design exists to measure rather than induce.
    """
    ...

def agreement_summary(*, video_id: Optional[str]=None, encounter_code: Optional[str]=None, part: Optional[str]=None, participant: Optional[str]=None, limit: int=500) -> dict:
    """Roll-up over every multi-rater group in scope, plus per-annotator scorecards.

    Two agreement figures on view class, and the split is load-bearing — it is the same
    lesson Stream F measured on the real RELAY capture, where two raters agreeing on 80%
    of a single-code task scored κ = 0.0:

      * `view_raw_agreement` is the fraction of rater PAIRS that picked the same view.
        Readable, and inflated by prevalence — a catalog that is 90% lateral_left scores
        high for agreeing about the easy case.
      * `view_kappa` (Fleiss) corrects for that, and is None or near-zero exactly when
        the corpus has almost no view diversity. Reported with `n_items_kappa` beside
        `n_items`, because Fleiss needs a constant rater count and silently drops the
        rest — a κ over a third of the corpus otherwise looks like a κ over all of it.

    Neither is reported alone, and there is no pass/fail verdict: see the module comment
    on why this layer emits no `meets_bar`.
    """
    ...

def _score_annotators(groups: Sequence[dict]) -> List[dict]:
    """One row per annotator: how they agree with everyone else, and how sure they were.

    `mean_confidence_when_view_agreed` vs `..._disagreed` is the calibration column, and
    it is the reason the confidence fields are read at all. A labeler who reports 5 just
    as often when the group disagreed with them is not giving the pipeline usable
    information — which is exactly what folding confidence in as a WEIGHT would hide.
    """
    ...

def _redact_group(g: dict, me: str) -> dict:
    """Strip peer identities from one group, keeping every count and aggregate."""
    ...

def redact_agreement_for(result: dict, me: str) -> dict:
    """Remove peer identities from an agreement result for a non-admin reader.

    The geometry problem is already handled upstream — `frame_agreement` returns no
    coordinates at all — so this only has to deal with names. What goes: the annotator
    list, the per-annotator view/verdict map, the named pair table, and every peer
    scorecard row.

    Naming peers turns a reliability panel into a social ranking: labelers start matching
    the person they rate highest instead of what they see, which is the anchoring the
    multi-rater design exists to measure rather than induce. It also publishes a live
    per-person quality league table to the cohort, which nobody agreed to.

    Aggregates survive untouched — κ, raw agreement, mean IoU, every count — so the panel
    stays fully informative, plus `my_*` fields about the reader's own work.
    """
    ...
