"""
Pose-derived zone/side hint geometry — pure numpy, no I/O, no ML.

Inputs are arrays of (x, y) keypoint pixel coordinates and per-keypoint confidences.
Outputs are zone/side string labels with explicit failure-status enums so the worker
can render hints conservatively (no chip when the model is unreliable).

Designed bad-pose-proof — every numerical path returns an explicit status; nothing
raises on garbage input. See plan i-think-ive-been-zazzy-swan.md for the
14-failure-mode matrix this module backstops.

Keypoint order (matches yolo_v4_best.pt training set, kpt_shape=[16,3]):
    [0]  snout_tip
    [1]  eye_center
    [2]  gill_slit
    [3]  pectoral_base
    [4]  pectoral_tip
    [5]  first_dorsal_base    (annotator-tool name: front_dorsal_base)
    [6]  first_dorsal_tip
    [7]  second_dorsal_base   (annotator-tool name: back_dorsal_base)
    [8]  second_dorsal_tip
    [9]  pelvic_fin_tip
    [10] anal_fin_tip
    [11] caudal_notch
    [12] caudal_upper_tip
    [13] caudal_lower_tip
    [14] body_midpoint_dorsal
    [15] body_midpoint_ventral

Body zones (mapping to scar-annotator BodyZone enum):
    1 Head, 2 Nape, 3 Above Gills, 4 Gills, 5 Saddle, 6 Flank,
    7 Aft Dorsal, 8 Pelvis, 9 Peduncle, D Dorsal Fin, P Pectoral Fin, T Tail
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

def remap_from_detector(kpts, conf):
    """Reorder detector keypoints into this module's schema.

    Every geometry function here indexes by `KP_IDX`, so anything arriving straight
    from the detector must pass through this first. Names with no detector
    counterpart come back at confidence 0 rather than at a wrong coordinate: an
    absent anchor is handled everywhere; a plausible-but-wrong one is not.

    Returns (kpts_native, conf_native) as fresh arrays, or (None, None) if the input
    is unusable. NEVER raises.
    """
    ...

@dataclass
class ProjectionResult:
    """Output of project_to_skeleton — one frame, one scar."""
    zone: Optional[str] = None
    t: Optional[float] = None
    perpendicular_distance: float = 0.0
    confidence: float = 0.0

@dataclass
class SideResult:
    side: Optional[str] = None
    confidence: float = 0.0

@dataclass
class FinResult:
    fin_zone: Optional[str] = None
    confidence: float = 0.0

@dataclass
class FrameOutcome:
    """All hint outputs for a single frame."""
    zone: Optional[str] = None
    zone_confidence: float = 0.0
    side: Optional[str] = None
    side_confidence: float = 0.0
    on_fin: bool = False
    fin_zone: Optional[str] = None

@dataclass
class TrackPoseSummary:
    """Top-K aggregated outputs persisted on the track row."""
    auto_zone: Optional[str] = None
    auto_zone_confidence: float = 0.0
    auto_side: Optional[str] = None
    auto_side_confidence: float = 0.0
    auto_on_fin: bool = False

@dataclass
class ZoneConfig:
    """Loaded from config.yaml [pose] section."""
    min_kpt_conf: float = 0.25
    head_on_ratio: float = 0.4
    fin_radius_frac: float = 0.15
    zone_cuts: Tuple[float, ...] = (0.0, 0.1, 0.18, 0.26, 0.34, 0.46, 0.62, 0.74, 0.86, 1.0)
    outlier_segment_multiplier: float = 2.5
    show_hint_threshold: float = 0.35

def _is_valid_kpt(kpts: np.ndarray, conf: np.ndarray, idx: int, min_conf: float) -> bool:
    ...

def _project_point_onto_segment(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> Tuple[float, np.ndarray, float]:
    """Return (param_t_on_segment, projected_point, perpendicular_distance).

    param_t_on_segment is clamped to [0, 1].
    """
    ...

def _point_in_fin_ellipse(p: np.ndarray, base: np.ndarray, tip: np.ndarray, width_frac: float) -> Tuple[bool, float]:
    """Test if point p is inside an oblong ellipse along base→tip axis.

    The ellipse is centered at the midpoint of base→tip with:
      - major axis = base→tip length (along the fin)
      - minor axis = width_frac × major axis (perpendicular to the fin)

    Returns (inside, confidence) where confidence is 1.0 at the fin's center
    line and 0.0 at the ellipse boundary. Reasonable approximation of a
    triangular fin shape — slightly more permissive at the base, less at the
    tip; in practice scars are usually on the broader portion (closer to base),
    so this works well enough.
    """
    ...

def _point_in_triangle(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> Tuple[bool, float]:
    """Barycentric point-in-triangle test. Used for caudal fin (3 kpts).

    Returns (inside, confidence) where confidence ~ 1.0 at centroid, ~0.0 at edges.
    """
    ...

def _estimate_shark_length(kpts: np.ndarray, conf: np.ndarray, cfg: ZoneConfig) -> Optional[float]:
    """Compute shark length in pixels from the most-distant pair of confident
    body-axis anchors. Falls back through anatomical pairs in priority order
    so even partial pose detections give a usable shark_length.

    Returns None if no pair is available.
    """
    ...

def _build_polyline(kpts: np.ndarray, conf: np.ndarray, names_in_order: Sequence[str], min_conf: float) -> List[Tuple[str, np.ndarray]]:
    """Filter the named anchors by confidence, return [(name, point)] in order."""
    ...

def detect_outlier_keypoints(kpts: np.ndarray, conf: np.ndarray, cfg: ZoneConfig) -> List[int]:
    """Identify keypoints that are anatomically misplaced.

    Strategy: check that ENDS of the body axis (snout_tip, caudal_notch) are
    actually closest to their expected adjacent anchor. A misplaced snout in
    the middle of the body will be closer to first_dorsal_base or
    second_dorsal_base than to gill_slit — that's the signal we catch.

    This is a coarse but reliable check. We don't try to detect every possible
    misplacement (e.g. swapped left/right pectoral) — those failure modes are
    less catastrophic for zone projection because the polyline endpoints
    determine the body-axis arc-length parameter.

    Returns list of keypoint indices considered outliers.
    """
    ...

def project_to_skeleton(scar_xy: Tuple[float, float], kpts: np.ndarray, conf: np.ndarray, cfg: ZoneConfig) -> ProjectionResult:
    """Map a scar bbox center to a body zone (1..9) by projecting onto the
    snout→caudal polyline and binning by arc-length fraction.

    Returns ProjectionResult; status='insufficient_anchors' if the polyline
    can't be built reliably. NEVER raises.
    """
    ...

def determine_side(scar_xy: Tuple[float, float], kpts: np.ndarray, conf: np.ndarray, cfg: ZoneConfig) -> SideResult:
    """Determine which biological side of the shark is visible.

    Convention: in image coords (y-down) with shark dorsal-up:
      - shark facing left in frame  → biological LEFT side visible
      - shark facing right in frame → biological RIGHT side visible

    DO NOT "FIX" THIS BY FLIPPING THE SIGN. The prose here used to say the
    opposite, and the returned values are the ones that are correct — an earlier
    author noticed the mismatch on real data, corrected the sign, and explained it
    as "we use a screen convention, not a biological one". It is in fact the
    biological answer; only the explanation was wrong. Derivation, with left =
    dorsal × anterior and a right-handed image frame (screen-right = +X,
    screen-up = +Y, toward-viewer = +Z): a shark facing image-left has anterior
    a = −X, dorsal d = +Y, so left = d × a = Y × (−X) = +Z — pointing at the
    camera. The LEFT flank is the one you can see. Flipping the sign to match the
    old prose would invert every stored auto_side.

    Implemented via cross-product sign of body-axis × dorsal-up. Falls back to
    'Both' when shark is head-on (snout↔caudal collapsed), and to FACING DIRECTION
    with status='assumed_dorsal_up' when dorsal/ventral cannot be read — which, on
    the shipped detector, is always.

    Body axis is derived from the BEST AVAILABLE head-end + tail-end anchors,
    not just snout + caudal_notch — a frame with snout=0.38, caudal=0.23
    (dropped), second_dorsal_base=0.41 should still give a valid axis from
    snout → second_dorsal_base. Without this fallback, determine_side returned
    'insufficient_anchors' on real data where the body axis is clearly visible.

    NEVER raises.
    """
    ...

def detect_fin(scar_xy: Tuple[float, float], kpts: np.ndarray, conf: np.ndarray, cfg: ZoneConfig) -> FinResult:
    """Detect whether the scar is on a fin (D=Dorsal, P=Pectoral, T=Tail).

    Geometric algorithm — fins are REGIONS, not points:
      - Dorsal fin (D): oblong ellipse along first_dorsal_base → first_dorsal_tip.
        Width = 0.4 × axis length (typical great-white dorsal aspect ratio).
      - Caudal fin (T): true triangle with vertices at caudal_notch,
        caudal_upper_tip, caudal_lower_tip — barycentric point-in-triangle test.
      - Pectoral fin (P): oblong ellipse along pectoral_base → pectoral_tip.
        Width = 0.6 × axis length (broader than dorsal).

    Fallback when only one of a pair is confident: shrink to a circle of
    fin_radius_frac × shark_length around the available kpt. shark_length
    is estimated from any pair of confident body-axis anchors via
    _estimate_shark_length (handles the common case where snout/caudal
    confidence is below threshold but gill+second_dorsal_base are visible).

    Picks the highest-confidence match, with priority T > D > P used as a
    tiebreaker only when matches are close in confidence.

    NEVER raises.
    """
    ...

def compute_frame_outcome(scar_xy: Tuple[float, float], kpts: np.ndarray, conf: np.ndarray, cfg: ZoneConfig) -> FrameOutcome:
    """Compose project_to_skeleton + determine_side + detect_fin into a single
    per-frame result, with status reflecting the most informative failure mode.

    NEVER raises.
    """
    ...

def aggregate_top_k(per_frame: List[Tuple[FrameOutcome, float]]) -> TrackPoseSummary:
    """Aggregate top-K frames' outcomes into a single track summary.

    Args:
        per_frame: list of (FrameOutcome, frame_composite_score) — one per
                   top-K detection. Ordered any way.

    Aggregation rules:
      - auto_zone: weighted-mode by (zone_conf × composite_score). Tie → first.
      - auto_side: weighted-mode similarly. ANY 'head_on' frame forces 'Both'
                    with confidence capped at 0.4.
      - auto_on_fin: True if ≥2 frames flagged on_fin (or only one frame and
                    it flagged).
      - pose_status: 'no_detection' if all frames are no_detection;
                     'low_confidence' if all frames are low_confidence;
                     'head_on' if any head_on; else 'ok'.
    """
    ...

def zone_arc_span(zone: int, cfg: Optional['ZoneConfig']=None) -> Optional[Tuple[float, float]]:
    """Arc-length fraction span [t0, t1] along snout→caudal for a body zone 1..9.

    Returns None for zones with no arc range: the fin and tail zones (D, P, T) are
    defined by their own geometry, not by a position along the body axis.
    """
    ...

def zone_region_on_polyline(zone: int, kpts: 'np.ndarray', conf: 'np.ndarray', cfg: Optional['ZoneConfig']=None) -> Optional[Dict[str, Any]]:
    """Image-space region for a body zone, from a posed skeleton.

    Returns ``{"start": (x, y), "end": (x, y), "width": w}`` where start/end are the
    zone's endpoints along the body axis and ``width`` is a suggested band thickness
    (derived from the animal's own scale, so it works at any resolution or zoom).

    None when the pose is too weak to trust, which is the honest answer: a wrong
    highlight is worse than none, because it sends the annotator to the wrong part
    of the animal with confidence.
    """
    ...
