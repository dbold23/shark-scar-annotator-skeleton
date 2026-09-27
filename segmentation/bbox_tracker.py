"""
Bbox-only propagator — tracks a bounding box across frames using template matching
+ optical flow, WITHOUT asking SAM2 to segment a "scar object."

Why this exists: SAM2's video predictor was trained to follow objects with clear
boundaries. Shark scars are low-contrast skin patches that blend into the body;
SAM2 routinely escapes the bbox and latches onto higher-contrast distractors
(bubbles, fish, shark edges). Scars are better treated as image PATCHES tracked
by appearance, not objects tracked by mask.

Public API mirrors `Sam2VideoPropagator.propagate()` exactly so the downstream
pipeline (scoring, preview cache, DB schema, verify flow) doesn't change:

    propagate(video_path, seed_frame_idx, seed_bbox, seed_point=None)
        -> {'detections': [...], 'fps': f, 'orig_size': (w,h), 'scaled_size': (w,h)}

Each detection is a dict with:
    frame_number: int (ORIGINAL video frame index)
    bbox:         dict {x, y, width, height} in ORIGINAL resolution
    mask_rle:     COCO RLE of a rectangle mask covering the bbox
    sam2_score:   float — tracker's match confidence (NCC, 0..1)
    plus the transient scoring context from `track_scoring.make_scoring_context`:
    a PADDED CROP around the bbox (frame_crop / mask_crop / crop_origin) and the
    scalars measured off the full-frame mask (frame_shape, mask_pixels,
    edge_penalty, center_prior, sharpness_raw). NOT the frame — see
    `_make_detection`. On an outsized seed box even the crop is dropped
    (crop_omitted) and rebuilt later for the best frame alone.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

class _LazyFrameWindow:
    """Dict-like view over [start, end) that decodes frames on demand.

    The tracker used to read the entire ±frame_window span into a dict before
    tracking. It never needed to: `_track_direction` touches exactly
    `frames[seed_fn]` and a strictly sequential `frames.get(fn)`, so at most two
    frames are live at once. Buffering cost 121 uncompressed 1080p BGR frames
    ≈ 750 MB-1.2 GB resident *per propagation*, and
    `tracks.max_concurrent_propagations` is enforced per-user — so a 20-student
    cohort propagating together could ask for ~24 GB and OOM the box.

    The seed frame is pinned because both the forward and backward passes read
    it, and re-decoding it must not depend on seek accuracy. Everything else is
    decoded as asked for: the forward pass costs nothing extra (the capture
    cursor is already there), while the backward pass seeks per frame, which is
    slower but keeps memory flat. That trade is deliberate — propagation is a
    background job, and wall-clock is far cheaper than an OOM that takes down
    every other annotator on the box.

    Interface is intentionally the subset the tracker uses: __contains__,
    __getitem__, get, __len__.
    """

    def __init__(self, cap, start: int, end: int, seed_fn: int):
        ...

    def _read_at(self, fn: int) -> Optional[np.ndarray]:
        ...

    def get(self, fn: int, default=None):
        ...

    def __getitem__(self, fn: int) -> np.ndarray:
        ...

    def __contains__(self, fn: int) -> bool:
        ...

    def __len__(self) -> int:
        """Frames actually decoded so far.

        Previously this was the whole pre-read window. Nothing consumes it (it
        surfaces as the informational `window_frames` in the result), so the
        honest streaming answer is the count we really decoded.
        """
        ...

@dataclass
class BboxTrackerConfig:
    """Config specific to the bbox (non-SAM2) tracker.

    All values loadable from config.yaml [tracks] section.
    """
    frame_window: int = 60
    search_radius: int = 25
    min_score: float = 0.3
    flow_margin: int = 60
    flow_max_features: int = 60
    flow_min_features: int = 5
    flow_lk_win: int = 21
    flow_lk_pyramid: int = 3
    template_refresh_every: int = 0
    template_refresh_score: float = 0.92
    max_consecutive_misses: int = 4

def is_available(_cfg=None) -> Tuple[bool, str]:
    """The bbox tracker uses only base opencv-python, always available."""
    ...

class BboxPropagator:
    """Drop-in replacement for Sam2VideoPropagator that tracks bboxes, not masks."""

    def __init__(self, cfg: BboxTrackerConfig):
        ...

    def propagate(self, video_path: str, seed_frame_idx: int, seed_bbox: Dict, seed_point: Optional[Tuple[int, int]]=None, min_mask_pixels: int=20, frame_hook=None, sharpness_min_pixels: Optional[int]=None, max_crop_bytes: Optional[int]=None) -> Dict:
        """Template-matching tracker with multi-scale search + template refresh.

        seed_point is IGNORED — bbox trackers don't use point prompts. We accept
        the arg so the call site stays the same as SAM2.

        frame_hook, if given, is called as hook(detection, frame_bgr, mask) the
        moment a detection is built, while its full frame and full-frame mask are
        still in hand. It is the only way to see those pixels — nothing keeps them
        afterwards. See `propagate_and_score`, which uses it to render previews.

        sharpness_min_pixels / max_crop_bytes come from the caller's
        ScoringConfig — sharpness is measured here, at production time, and the
        retained crop is capped here, because this is the only place that has the
        frame. Both resolve to the ScoringConfig defaults when unset, so a caller
        that knows nothing about them still gets a BOUNDED detection rather than
        an unbounded one (production runs without a `tracks:` config section).
        """
        ...

    def _track_direction(self, frames, detections: List[Dict], seed_fn: int, stop_fn: int, step: int, initial_template: np.ndarray, initial_bbox: Tuple[int, int, int, int], min_mask_pixels: int, frame_hook=None, sharpness_min_pixels: Optional[int]=None, max_crop_bytes: Optional[int]=None):
        """Track forward (step=1) or backward (step=-1) from the seed frame.

        Algorithm: **everything anchored to the seed**. Nothing accumulates
        frame-to-frame bbox-wise — each frame recomputes from the seed:

            center_this_frame = seed_center + cumulative_flow_from_seed
            size_this_frame   = seed_size * best_scale
                                (scales always relative to seed, never previous)

        The only state that carries forward is the LK flow's `cum_dx, cum_dy`
        — the sum of per-frame motion since the seed. Position and size of the
        bbox are both always derived fresh from the seed, so there's no pathway
        for position drift or size drift to compound across frames.
        """
        ...

    @staticmethod
    def _ncc_at(frame: np.ndarray, template: np.ndarray, x: int, y: int, w: int, h: int) -> float:
        """NCC between `template` and the frame region at (x, y, w, h).
        Score only — no search. Returns 0 if the region is off-frame.
        """
        ...

    def _make_detection(self, frame_bgr: np.ndarray, fn: int, bbox: Dict, score: float, min_mask_pixels: int, frame_hook=None, sharpness_min_pixels: Optional[int]=None, max_crop_bytes: Optional[int]=None) -> Dict:
        """Build a detection dict matching the SAM2 output format.

        The "mask" is a filled rectangle covering the bbox — enough for scoring
        (Laplacian sharpness, area score, center prior all work on rectangles)
        and for the preview renderer.

        The full frame and the full-frame mask exist only for the length of this
        call: `frame_hook` gets its one look at them (that is where preview JPEGs
        are rendered, since a preview needs pixels the detection will not keep),
        `make_scoring_context` distils what scoring needs, and then both are
        dropped. Returning them, as this used to, multiplied 8.29 MB by the
        detection count for as long as the propagation ran.

        When even the distilled crop is over `max_crop_bytes` it is not kept
        either, and this path is the easy one to rebuild: the mask IS the bbox,
        a filled rectangle, so re-deriving it later is exact rather than
        approximate. `mask_rle` is written regardless, so the rebuild uses the
        same route for both propagators.
        """
        ...
