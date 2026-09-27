"""
SAM2 video propagation — Phase 1 of the tracks redesign.

Given a seed bounding box in one frame of a video, propagate the corresponding mask
forward and backward through a bounded frame window using Meta's SAM2 video predictor.

IMPORTANT: This module uses Meta's reference `sam2` package (facebookresearch/sam2),
which is a DIFFERENT implementation than the HuggingFace `transformers.Sam2Model` used
by segmentation/sam2_segmenter.py for image-only prompted segmentation. The HF weights
and the Meta weights are NOT interchangeable — you need the Meta `.pt` checkpoint
together with its Hydra config name (e.g., sam2_hiera_l.yaml).

The `sam2` package must be installed separately:
    pip install git+https://github.com/facebookresearch/sam2.git

If sam2 is not installed, this module will raise `VideoPropagationUnavailable` at the
first call to propagate() — callers should check `is_available()` first to gate the UI.
"""
from __future__ import annotations
import base64
import json
import logging
import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

class VideoPropagationUnavailable(RuntimeError):
    """Raised when Meta's sam2 package isn't installed or weights are missing."""

class VideoPropagationError(RuntimeError):
    """Raised for runtime failures during propagation (corrupt video, mask collapse, etc.)."""

@dataclass
class PropagatorConfig:
    """Propagation-specific config loaded from config.yaml [tracks]."""
    frame_window: int = 60
    downscale_to: int = 720

def is_available(cfg: PropagatorConfig) -> Tuple[bool, str]:
    """Report whether video propagation can be performed.

    Returns (ready, reason). Reason is empty if ready, human-readable if not.
    Does NOT import sam2 (to avoid paying import cost at boot time).
    """
    ...

class Sam2VideoPropagator:
    """Thin wrapper around Meta's sam2 video predictor.

    Intentionally NOT a subclass of SAM2Segmenter — the image-prompted flow in
    segmentation/sam2_segmenter.py stays untouched. This class owns its own
    model instance and its own lock, so live interactive segmentation is not
    starved while a propagation job runs.
    """

    def __init__(self, cfg: PropagatorConfig):
        ...

    def _ensure_loaded(self):
        ...

    def _extract_window_frames(self, video_path: str, seed_frame_idx: int, out_dir: Path) -> Tuple[List[int], float, Tuple[int, int], Tuple[int, int]]:
        """Extract a downscaled frame window to `out_dir` as sequentially-named JPEGs.

        Returns (original_frame_indices, fps, (orig_w, orig_h), (scaled_w, scaled_h)).
        Sequential filenames are 00000.jpg, 00001.jpg, ... (zero-padded, sortable).
        """
        ...

    @staticmethod
    def _mask_to_bbox(mask: np.ndarray) -> Dict[str, int]:
        """Convert a binary mask to {x, y, width, height} in the mask's resolution."""
        ...

    @staticmethod
    def _scale_bbox(bbox: Dict[str, int], scale: float) -> Dict[str, int]:
        ...

    @staticmethod
    def _largest_connected_component(mask: np.ndarray) -> np.ndarray:
        """Keep only the largest connected component in a binary mask.

        SAM2 video propagation can split a mask into multiple components when the
        object partially occludes. The Plan agent flagged this explicitly — keep
        the largest.
        """
        ...

    @staticmethod
    def mask_to_coco_rle(mask: np.ndarray) -> str:
        """Encode a binary mask to base64-encoded COCO RLE JSON string.

        Uses pycocotools for compression (much smaller than raw PNG for sparse masks).
        """
        ...

    @staticmethod
    def coco_rle_to_mask(rle_str: str) -> np.ndarray:
        """Decode a COCO RLE JSON string back to a binary mask (uint8 0/255)."""
        ...

    def propagate(self, video_path: str, seed_frame_idx: int, seed_bbox: Dict, seed_point: Optional[Tuple[int, int]]=None, min_mask_pixels: int=20, frame_hook=None, sharpness_min_pixels: Optional[int]=None, max_crop_bytes: Optional[int]=None) -> Dict:
        """Propagate a mask forward and backward from the seed frame.

        Args:
            video_path: absolute path to mp4/mov on disk (must be in tmp_videos/ cache).
            seed_frame_idx: frame index in the ORIGINAL video coordinate system.
            seed_bbox: {x, y, width, height} in ORIGINAL resolution.
            seed_point: optional (x, y) positive-click inside the scar, in ORIGINAL
                        resolution. Combining bbox + positive point materially helps
                        SAM2 latch onto the intended object rather than a nearby
                        high-contrast distractor.
            min_mask_pixels: masks smaller than this AFTER upscaling are dropped.
            frame_hook: optional hook(detection, frame_bgr, mask), called while a
                        detection's full frame and full-frame mask are still in
                        hand. Nothing keeps them afterwards, so this is the only
                        opportunity to use whole-frame pixels (previews).
            sharpness_min_pixels: ScoringConfig.min_mask_pixels_for_sharpness,
                        threaded in because sharpness is now measured HERE (the
                        only place with the frame) rather than during scoring.
            max_crop_bytes: ceiling on what one detection may retain. Over it the
                        crop is dropped and rebuilt later for the best frame
                        only — see `rebuild_scoring_pixels`. Both default to the
                        ScoringConfig defaults, so an uninformed caller still
                        gets a bounded detection.

        Returns:
            {
              'detections': [ {frame_number, bbox, mask_rle, sam2_score, + the
                              transient scoring context from
                              track_scoring.make_scoring_context}, ... ],
              'fps': float,
              'orig_size': (w, h),
              'scaled_size': (w, h),
            }

            The scoring-context fields are TRANSIENT (a padded crop and a few
            scalars) — the caller should persist only frame_number, bbox,
            mask_rle, sam2_score.
        """
        ...

    def _propagate_locked(self, video_path: str, seed_frame_idx: int, seed_bbox: Dict, seed_point: Optional[Tuple[int, int]], min_mask_pixels: int, frame_hook=None, sharpness_min_pixels: Optional[int]=None, max_crop_bytes: Optional[int]=None) -> Dict:
        ...

    @staticmethod
    def _logits_to_mask_and_score(mask_logits, obj_ids) -> Tuple[Optional[np.ndarray], float]:
        """Convert SAM2 output tensors to a binary mask + scalar confidence.

        mask_logits shape is typically [num_objs, 1, H, W] (PyTorch tensor).
        We seeded exactly one object, so take index 0.
        """
        ...

    @staticmethod
    def _read_frame(video_path: str, frame_idx: int) -> Optional[np.ndarray]:
        """Read a single frame from a video file at a specific index."""
        ...

def rebuild_scoring_pixels(video_path: str, det: Dict) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], str]:
    """Re-derive the (frame_crop, mask_crop) a detection declined to keep.

    Returns (frame_crop, mask_crop, "") on success, or (None, None, reason).

    Only ONE detection per propagation ever needs this — the best frame, so that
    `extract_auto_color` can read it. Everything else scoring wants is a scalar,
    so a crop that is over `tracks.max_detection_crop_bytes` is simply not
    stored and this rebuilds it on demand. That is the whole point: paying one
    seek at the end instead of carrying N crops throughout.

    The frame comes back through `Sam2VideoPropagator._read_frame`, the SAME
    mechanism pose already uses for its top-K re-reads. An independent audit
    measured this against the pixels the propagation was built from: 423 frames
    across 7 real videos, 0 mismatches, covering both the sequentially-decoded
    forward range and the seeked backward range.

    The mask comes back through `mask_rle`, not through the bbox. For the bbox
    tracker the two are the same thing (its mask IS a filled rectangle), but a
    SAM2 mask has shape the bbox cannot express, and reconstructing a rectangle
    there would hand `extract_auto_color` a different object — it erodes the
    mask to find the scar core and dilates it to sample the skin ring, so a
    wrong mask is a wrong colour, silently. The bbox fill is a last resort, used
    only when the RLE is missing AND the mask really was a rectangle.

    `crop_box` is replayed verbatim rather than recomputed, so the rebuilt
    arrays are the same slice of the same frame the retained path would have
    kept — identical by construction rather than by re-deriving the padding.

    On ANY failure this returns a reason and no pixels. The caller must leave
    auto_color as None and say why. Substituting a nearby frame, or falling back
    to the bbox for a real SAM2 mask, would produce a colour that looks exactly
    as authoritative as a correct one.
    """
    ...

def _mask_is_just_the_bbox(mask: np.ndarray, bbox: Dict) -> bool:
    """True when the mask carries no shape the green bbox does not already show.

    The bbox tracker's "mask" is a filled rectangle covering the bbox — and since
    `tracks.tracker_type` defaults to 'bbox' when the config section is absent
    (which it is in production), that is every mask prod produces. Tinting it
    applies 0.8*original + 0.2*cyan across 100% of the scar interior and draws a
    cyan contour on the exact coordinates as the green rectangle.

    That matters because this preview is the image the annotator judges
    `human_color` from in the verify modal. Measured on a pinkish patch, the wash
    moved BGR (150,130,180) -> (120,155,195): it pushes pink toward cyan-grey, on
    the one decision the preview exists to support. A real SAM2 mask has shape
    worth drawing, so only the degenerate rectangle case is skipped.
    """
    ...

def render_preview_jpeg(frame_bgr: np.ndarray, mask: np.ndarray, bbox: Dict, max_edge: int=960, quality: int=85) -> bytes:
    """Compose one preview frame (mask contour + bbox) and encode as JPEG bytes."""
    ...

def propagate_and_score(propagator, video_path: str, seed_frame_idx: int, seed_bbox: Dict, scoring_cfg, color_cfg, preview_dir: Optional['Path']=None, seed_point: Optional[Tuple[int, int]]=None, pose_inferencer=None, pose_zone_cfg=None, pose_top_k: int=3) -> Dict:
    """Full pipeline: propagate → score → pick best frame → auto-color → pose hints.

    Phase 2: when pose_inferencer is provided, runs pose on the top-K
    detections by composite_score and aggregates zone/side hints.

    pose_inferencer: an instance of segmentation.pose_inference.PoseInferencer
                     (or None to skip pose entirely — Phase 1 behavior preserved).
    pose_zone_cfg:   ZoneConfig from segmentation.pose_zones; required if
                     pose_inferencer is set.
    pose_top_k:      how many highest-scoring frames to run pose on.

    Returns:
        {
          'detections': [ {frame_number, bbox, mask_rle, sam2_score, sharpness_score,
                          area_score, composite_score, mask_pixels, rejected,
                          pose_json (top-K only)}, ... ],
          'best_frame_number': int,
          'frame_count': int,
          'confidence_aggregate': float,
          'auto_color': str or None,
          'auto_color_confidence': float,
          # Phase 2 fields (None if pose was unavailable or disabled):
          'auto_zone': str or None,
          'auto_zone_confidence': float,
          'auto_side': str or None,
          'auto_side_confidence': float,
          'auto_on_fin': bool,
          'pose_status': str or None,
          'pose_model_version': str or None,
        }
    """
    ...
