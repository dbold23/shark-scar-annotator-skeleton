"""Body mask — where the shark is, and which parts of it are not skin.

Plan 13 §6.1. This is the half of the texture-anomaly question that is actually
SOLVED, and it is worth shipping whether or not a scar proposer ever exists.

WHY IT MATTERS, measured. Every one of the four anomaly methods in the Aug-2026
study produced the same top-5 false positives, and none of them is skin:

  1. the animal/water silhouette   (3/5 DINOv2, 4/5 residual, 4/5 LAB, 4/6 classical)
  2. the eye and the gill slits    — a dark round eye IS the most abnormal thing
                                     on a shark, and every appearance-based
                                     one-class model will say so, forever
  3. fin edges, then sun caustics

Masking is the rare change that improves precision AND raises AUC: 0.694 -> 0.744
for the illumination residual, 0.678 -> 0.795 for the LAB family's best statistic.
It also improves auto-colour, best-frame scoring, and pose-zone hints, none of
which depend on anomaly detection.

BACKENDS, in descending quality and ascending cost:

  sam3       text-prompted "shark" -> pixel-tight silhouette. Needs `transformers`
             and local weights. transformers is deliberately NOT in
             requirements.txt: the prod image is dependency-light and CPU-only, so
             SAM3 is an OFFLINE BATCH tool, never imported by the Flask app.
  sam2       already vendored in this repo; prompted with the pose box.
  pose_hull  convex hull of confident keypoints, numpy/cv2 only. Always available,
             and the honest floor — it is a coarse envelope, not a silhouette.

STATUS IS NOT A BOOLEAN. A caller must be able to tell "there is no animal here"
from "there is an animal but I could not find its eye". Those licence different
downstream behaviour, and collapsing them is how a mask silently starts including
the eye again.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
import numpy as np
IDX_SNOUT, IDX_EYE = (0, 1)
IDX_GILL_FRONT, IDX_GILL_BACK = (2, 3)
IDX_CAUDAL_NOTCH = 13
FIN_TIP_IDX = (5, 7, 10, 11, 12, 14, 15)
FIN_BASE_IDX = (4, 6, 8, 9)

@dataclass
class BodyMaskConfig:
    enabled: bool = False
    score_threshold: float = 0.3
    erode_frac: float = 0.02
    exclude_eye: bool = True
    eye_radius_frac: float = 0.06
    exclude_gills: bool = True
    gill_radius_frac: float = 0.055
    exclude_fin_tips: bool = True
    fin_radius_frac: float = 0.05
    exclude_fin_bases: bool = True
    fin_base_radius_frac: float = 0.06
    min_area_frac: float = 0.004
    require_pose_for_exclusions: bool = True

    @classmethod
    def from_dict(cls, cfg: Optional[dict]) -> 'BodyMaskConfig':
        ...

@dataclass
class BodyMask:
    mask: Optional[np.ndarray]
    status: str
    exclusions_applied: bool = False
    area_frac: float = 0.0

    @property
    def ok(self) -> bool:
        ...

def is_available(cfg: BodyMaskConfig) -> Tuple[bool, str]:
    """Whether a mask can be produced, without paying any import cost."""
    ...

def animal_diagonal(kpts: np.ndarray, conf: np.ndarray, min_conf: float=0.2) -> float:
    """Scale reference in pixels: the spread of confident keypoints.

    Preferred over the pose box because a box around a diagonally-oriented shark
    is much larger than the animal."""
    ...

def _disk(shape: Tuple[int, int], cx: float, cy: float, r: float) -> np.ndarray:
    ...

def apply_exclusions(mask: np.ndarray, kpts: Optional[np.ndarray], conf: Optional[np.ndarray], cfg: BodyMaskConfig, min_conf: float=0.2) -> Tuple[np.ndarray, List[str]]:
    """Remove the anatomy that is on the animal but is not skin.

    Pure and separately testable. Returns (mask, names_removed). Silent no-op when
    keypoints are absent — the CALLER decides whether that is acceptable, because
    "a mask with no exclusions" is a materially different product from "a mask"."""
    ...

def erode_mask(mask: np.ndarray, px: int) -> np.ndarray:
    """Pull the mask in from its own boundary.

    This is what kills the silhouette family: every method's #1 false positive was
    a box straddling animal and water, which is a genuine within-frame rarity and
    always will be. The fix is to stop offering those pixels as candidates."""
    ...

def pose_hull_mask(shape: Tuple[int, int], kpts: np.ndarray, conf: np.ndarray, min_conf: float=0.2) -> Optional[np.ndarray]:
    """Convex hull of confident keypoints. The honest floor: an envelope, not a
    silhouette. Its periphery is water, which is exactly why callers must erode."""
    ...

class BodyMasker:

    def __init__(self, cfg: BodyMaskConfig):
        ...

    def _load_sam3(self):
        ...

    def _sam3_once(self, pil, prompt: str) -> Optional[np.ndarray]:
        ...

    def _silhouette_sam3(self, frame_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], str]:
        ...

    def _silhouette_sam2(self, frame_bgr, box) -> Tuple[Optional[np.ndarray], str]:
        ...

    def mask_for_frame(self, frame_bgr: np.ndarray, keypoints: Optional[Sequence[Sequence[float]]]=None, kpt_conf: Optional[Sequence[float]]=None, pose_box: Optional[Tuple[int, int, int, int]]=None, pose_status: str='unknown') -> BodyMask:
        ...

def get_masker(cfg: BodyMaskConfig) -> Optional[BodyMasker]:
    ...

def reset_masker():
    ...
