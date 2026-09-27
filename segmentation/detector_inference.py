"""
Phase 5a — scar detector inference + per-video frame walker.

Mirrors the lazy-load pattern of segmentation/pose_inference.py. Wraps a YOLO
detection model trained by scripts/train_detector.py. Returns None on every
failure mode so the caller (the auto-propose endpoint) can degrade gracefully
to "no candidates this round" instead of hard-failing.

Public API:
  - is_available(cfg)          → (bool, reason)
  - get_detector(cfg)          → DetectorInferencer or None
  - DetectorInferencer.infer(frame_bgr)
        → List[Detection]      one frame's detections, NMS already done by YOLO
  - DetectorInferencer.walk_video(video_path, *, interval_sec, top_k)
        → List[Candidate]      best top-K candidates across the whole video,
                               deduplicated globally by spatial overlap
"""
from __future__ import annotations
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

@dataclass
class DetectorConfig:
    enabled: bool = False
    imgsz: int = 640
    conf_threshold: float = 0.3
    iou_threshold: float = 0.45
    interval_sec: float = 2.0
    top_k_per_video: int = 12
    dedup_iou: float = 0.4
    dedup_max_time_sec: float = 5.0

@dataclass
class Detection:
    bbox: Tuple[int, int, int, int]
    class_id: int
    class_name: str
    score: float

@dataclass
class Candidate:
    frame_number: int
    time_sec: float
    bbox: Tuple[int, int, int, int]
    class_id: int
    class_name: str
    score: float

def is_available(cfg: DetectorConfig) -> Tuple[bool, str]:
    """Report whether detector inference can run, without paying import cost."""
    ...

def _bbox_iou(a, b) -> float:
    ...

class DetectorInferencer:
    """Lazy-loaded scar detector. Mirrors PoseInferencer's defensive pattern."""

    def __init__(self, cfg: DetectorConfig):
        ...

    def _ensure_loaded(self) -> bool:
        ...

    def infer(self, frame_bgr: np.ndarray) -> Optional[List[Detection]]:
        """Run the detector on one BGR frame. None on any failure mode."""
        ...

    def walk_video(self, video_path: str, *, interval_sec: Optional[float]=None, top_k: Optional[int]=None) -> Optional[List[Candidate]]:
        """Sample the video every `interval_sec` seconds, run the detector on
        each sample, dedupe the resulting candidate set globally, and return
        the top-K by score.

        None if the video can't be opened or the detector is unavailable.
        """
        ...

def get_detector(cfg: DetectorConfig) -> Optional[DetectorInferencer]:
    """Lazy module-level instance. Returns None if unavailable."""
    ...

def reset_detector():
    """Test hook — drop the cached instance."""
    ...
