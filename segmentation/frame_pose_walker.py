"""Walk a clip (or a single image) and derive the per-frame flank, once, up front.

Pure computation: opens media, runs the pose model, returns per-frame results. No
database, no Flask — the same split `detector_inference.walk_video` uses, so this is
testable without a catalog and reusable from a CLI backfill.

WHAT THIS PRODUCES, AND WHY IT IS A FRAME-LEVEL FACT
-----------------------------------------------------
`determine_side` returns the sign of the horizontal component of snout->tail. The
scar coordinate it takes enters only through the head-on test's reference scale — the
flank itself is a property of the ANIMAL IN THE FRAME, not of any box drawn on it.
That is why this can run before an annotator has drawn anything, and why the answer
is still the answer once they do.

Measured end to end on the 200 human-labelled lateral frames: this path scores
**105/108 = 97.2%**, abstaining on 46% of them, at ~86 ms/frame on CPU. All three
errors are on Left frames (Left recall 95.4%, Right 100%).

THE REFERENCE POINT IS THE ANIMAL'S OWN CENTROID
-------------------------------------------------
With no scar to anchor to, the head-on test needs some reference scale. This uses the
centre of the detected shark box rather than the centre of the frame, because the
test is asking whether the animal is foreshortened, and the animal's own extent is
the only scale that means anything for that. A frame-centre reference makes the same
frame read differently depending on where in the image the shark happens to swim.

`min_kpt_conf` is read from the caller's ZoneConfig — never re-derived here — for the
same reason Stream F freezes its spectrogram lattice at ingest: a threshold that
drifts between the precompute and the read makes stored values disagree with freshly
computed ones while both look correct.

ABSTENTION IS A RESULT
-----------------------
Every failure mode returns a row with a `pose_status` and no side, rather than
returning nothing. A frame with no cached row is "not yet walked"; a frame with a
row and `pose_status='insufficient_anchors'` is "walked, and the model declined".
Collapsing those two makes coverage unmeasurable.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

@dataclass
class FrameHint:
    """One sampled frame's answer. Mirrors a `frame_hints` row before storage."""
    frame_number: int
    time_sec: float
    auto_side: Optional[str] = None
    auto_side_confidence: float = 0.0
    kpts: Optional[Dict[str, Any]] = None

    @property
    def usable(self) -> bool:
        ...

@dataclass
class WalkResult:
    frames_sampled: int = 0
    error: Optional[str] = None

    @property
    def n_usable(self) -> int:
        ...

def is_image(path: str) -> bool:
    ...

def _kpts_payload(res, kpts_xy, kpts_conf) -> Dict[str, Any]:
    """The skeleton blob stored on the row.

    Stored in the model's NATIVE 16-point order, exactly as `PoseFrameResult` hands
    it over — NOT remapped. `remap_from_detector` is applied on read instead, so a
    correction to that mapping fixes every cached row at once rather than requiring a
    full re-walk of the corpus. The mapping has already been wrong once (it was
    index-identity against a differently-ordered detector), which is precisely why
    the raw form is the one worth keeping.

    Note the deliberate asymmetry with `auto_side`, which IS frozen at walk time:
    the raw skeleton is evidence and stays re-derivable, while the stored side is a
    derived answer that a re-walk supersedes. Keeping both is what lets a mapping fix
    correct zone hints immediately while leaving the flank figures that were measured
    against specific weights untouched until they are deliberately recomputed.
    """
    ...

def hint_for_frame(frame_bgr, *, inferencer, zone_cfg, frame_number: int, time_sec: float) -> FrameHint:
    """Run the model on one decoded BGR frame. NEVER raises."""
    ...

def walk_media(path: str, *, inferencer, zone_cfg, interval_sec: float=2.0, max_frames: Optional[int]=None, progress: Optional[Callable[[float, int, int], None]]=None, should_stop: Optional[Callable[[], bool]]=None) -> WalkResult:
    """Sample `path` and return one FrameHint per sample.

    A single image is one sample at frame 0, time 0.0 — matching how image assets
    are already stored (all 302 of them carry `frame_number = 0`).

    A video is sampled every `interval_sec`, and the frame numbers are read from the
    decoder, never computed from an assumed fps. That assumption is the
    30-vs-59.94 bug (`645ffca`) whose stored frame numbers needed a corpus-wide
    backfill; a cache keyed on a guessed index would reintroduce it in a place where
    nothing would notice.
    """
    ...

def _model_version(inferencer) -> str:
    ...

def summarise(result: WalkResult) -> Dict[str, Any]:
    """Counts for a log line or a job's detail blob."""
    ...
