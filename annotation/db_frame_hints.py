"""Precomputed per-frame pose hints — the cache behind ``POST /api/scars/hint``.

The hint pipeline already existed (`annotation/routes_hints.py`, plan 10 §5): the
annotator draws a box, the client ships the decoded frame, the server runs YOLO-pose
and answers zone / side / colour. What it lacked was *memory*. Every box paid ~90 ms
of inference, and the answer arrived only AFTER the human had drawn — too late to
pre-fill the one field that is a property of the FRAME rather than of the box.

    side is a per-FRAME fact.  zone and on-fin are per-BOX facts.

That split is not a style choice, it is what `determine_side` computes: the sign of
the horizontal component of snout->tail. The scar coordinate enters only through the
head-on test's reference scale. Measured on the 290-frame view-class study, the
shipped path (YOLO -> remap_from_detector -> determine_side) scores **105/108 = 97.2%
against a human `view_class`, on 54% coverage** — while the stored `sides_visible`
label, which the form has been defaulting for years, tracks the true per-frame flank
only 58.2% of the time — barely above the 54.5% an always-"Left" guess scores on the
same frames. The geometry was never the problem; it was being scored against a label
that answers an encounter-level coverage question.

WHAT IS STORED, AND WHY IT IS NOT THE OBVIOUS LIST
--------------------------------------------------
The tempting schema is `(auto_side, auto_zone, auto_on_fin)`. Two of those three
cannot exist at this grain: a zone is "where on the animal is THIS POINT", and a
frame has no canonical point. Storing a frame-level zone would mean inventing a
coordinate — the shark's centroid, say — and every consumer downstream would read a
real-looking zone that answers nothing anybody asked.

So the row stores the **skeleton** (`kpts_json`) instead. From it:

    side        read straight off the row (frame-level, already derived)
    zone        `compute_frame_outcome(scar_xy, kpts, conf, cfg)` — pure numpy,
                microseconds, no model load, for ANY box on that frame
    on_fin      same call

That is strictly more than the three columns could hold, and it costs one JSON blob.

THIS TABLE IS WRITTEN BY THE SERVER-SIDE WALKER ONLY
-----------------------------------------------------
`frame_number` here is the TRUE cv2 index, read from the decoder during the walk —
never a client-supplied one. The read path may look a row up by a client's frame
number, but it must not write one back: a client whose fps is wrong (the pre-`645ffca`
30-vs-59.94 bug, and the reason `frame_number_raw`/`frame_fps` exist at all) would
poison the cache with hints filed under frames that do not contain them. Read wide,
write narrow.

`model_version` is part of the UNIQUE key so re-running a NEW model adds rows beside
the old ones rather than overwriting them. The 97.2% above is a measurement against
specific weights; a cache that silently replaces the values it was measured on
destroys the only record that makes the next model comparable.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from annotation.database import get_conn

def init_frame_hints_table() -> None:
    """Create the table + indices. Idempotent; safe on every app start."""
    ...

def upsert_hint(*, video_id: str, frame_number: int, model_version: str, time_sec: Optional[float]=None, auto_side: Optional[str]=None, auto_side_confidence: float=0.0, pose_status: str='unavailable', kpts: Optional[Dict[str, Any]]=None) -> int:
    """Store one frame's hint. Returns the row id.

    Re-running the SAME model version on the same frame overwrites in place — a
    recompute is a correction, not a second opinion. Running a DIFFERENT version
    inserts a new row, because that comparison is the whole point of keeping the
    version in the key.
    """
    ...

def upsert_many(rows: List[Dict[str, Any]]) -> int:
    """Bulk form of `upsert_hint` in ONE transaction. Returns rows written.

    A per-frame commit on a 5-minute clip is ~150 fsyncs while an annotator is
    waiting on the same WAL.
    """
    ...

def _row_to_dict(row) -> Dict[str, Any]:
    ...

def get_hint(video_id: str, frame_number: int, model_version: Optional[str]=None) -> Optional[Dict[str, Any]]:
    """One frame's hint, or None.

    With no `model_version` the NEWEST row for that frame wins — a fresh model
    should serve the annotator immediately. Pin the version to reproduce a
    measurement; leave it unset to get today's best answer.

    `nearest_hint` is the tolerant lookup for video frames; this one is exact.
    """
    ...

def nearest_hint(video_id: str, frame_number: int, *, max_distance: int=0, model_version: Optional[str]=None) -> Optional[Dict[str, Any]]:
    """The cached hint for this frame, or the closest one within `max_distance`.

    A precompute walk samples every Nth frame, so an exact hit is the exception on
    video. Neighbour reuse is sound for SIDE specifically — the flank cannot change
    without the animal turning, which takes far longer than a sampling interval —
    and is NOT sound for the skeleton, which moves every frame. Callers that reuse
    a neighbour therefore get `stale_by` and must drop `kpts` for geometry.

    `max_distance=0` (the default) makes this an exact lookup, so nothing gets a
    neighbour by accident.
    """
    ...

def list_hints(video_id: str, model_version: Optional[str]=None) -> List[Dict[str, Any]]:
    ...

def has_hints(video_id: str, model_version: Optional[str]=None) -> bool:
    ...

def delete_hints(video_id: str, model_version: Optional[str]=None) -> int:
    ...

def coverage_stats(model_version: Optional[str]=None) -> Dict[str, Any]:
    """Corpus-level honesty check: how much of the catalog actually has a hint.

    `usable` is the number that matters and it is NOT `n_rows`: the detector
    abstains on roughly half of real frames, and a coverage figure that counts
    abstentions as coverage is the same mistake as reading `meets_bar` as "we
    found everything".
    """
    ...
