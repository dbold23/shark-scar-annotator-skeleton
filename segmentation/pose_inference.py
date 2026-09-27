"""
Lazy-loaded YOLOv8-pose wrapper for Phase 2 zone/side hints.

Mirrors the pattern from segmentation/sam2_video.py:
  - lazy load on first call
  - never raises during inference (returns None on any failure)
  - graceful unavailability when ultralytics is missing or model file is gone

The output is consumed by segmentation/pose_zones.py (pure-numpy geometry).
This module ONLY does: load model → predict on a frame → pick the best detection
relative to a track bbox → return (kpts_xy, kpts_conf, model_bbox).

Failure modes handled here (matching plan i-think-ive-been-zazzy-swan.md):
  1.  No detection             → infer() returns None
  2.  Multiple sharks           → pick highest IoU vs track bbox
  3.  Wrong shark (low IoU)     → infer() returns None (with reason='wrong_subject')
  10. Model fails to load       → unavailable=True, never tries again
  11. Inference crash           → infer() returns None (with reason='inference_error')
"""
from __future__ import annotations
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np

@dataclass
class PoseInferenceConfig:
    enabled: bool = True
    min_iou_with_track_bbox: float = 0.15
    imgsz: int = 640

@dataclass
class PoseFrameResult:
    """Output for a single frame — fed into pose_zones.compute_frame_outcome()."""
    kpts_xy: np.ndarray
    kpts_conf: np.ndarray
    model_bbox: Tuple[int, int, int, int]
    iou_with_track_bbox: float
    detection_count: int

def is_available(cfg: PoseInferenceConfig) -> Tuple[bool, str]:
    """Report whether pose inference can run, without paying import cost."""
    ...

def _bbox_iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    """IoU between two (x, y, w, h) bboxes. Returns 0 on degenerate."""
    ...

def _bbox_contains(container: Tuple[int, int, int, int], scar_xy: Tuple[float, float]) -> bool:
    """True if the scar bbox center lies inside the container bbox."""
    ...

class PoseInferencer:
    """Single-shot YOLOv8-pose wrapper. Thread-safe via internal lock."""

    def __init__(self, cfg: PoseInferenceConfig):
        ...

    def model_version(self) -> str:
        """Used to tag track rows for telemetry."""
        ...

    def _ensure_loaded(self) -> bool:
        """Return True if the model is ready. Caches failures so we don't keep retrying."""
        ...

    def infer(self, frame_bgr: np.ndarray, track_bbox: Tuple[int, int, int, int], scar_xy: Tuple[float, float]) -> Optional[PoseFrameResult]:
        """Run pose on one BGR frame; return the shark detection that best
        matches the track bbox.

        track_bbox: (x, y, w, h) in original-image pixel coords (the scar
                    track's bbox on this frame, used to pick the right shark).
        scar_xy:    (x, y) center of the scar bbox in original-image coords —
                    used as a sanity check (the picked shark must contain it).

        Returns None on any failure mode 1, 3, 10, 11. Logs once at INFO/WARN.
        """
        ...

def get_pose_inferencer(cfg: PoseInferenceConfig) -> PoseInferencer:
    """Module-level singleton — one PoseInferencer per process.

    Safe to call from multiple threads; lazy-loads on first .infer().
    """
    ...

def reset_pose_inferencer():
    """Forget the cached singleton — used by tests / config reloads."""
    ...
