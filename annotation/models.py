"""
Data models for Shark Scar Annotation Platform.
Exact mapping to the Google Form for shark scar scoring.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import json

class SideVisible(Enum):
    ...

class ScarType(Enum):
    ...

class BodyZone(Enum):
    ...

class ScarColor(Enum):
    ...

class YesNo(Enum):
    ...

@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    def to_dict(self):
        ...

    def to_coco(self):
        ...

@dataclass
class Keypoint:
    name: str
    x: float
    y: float
    v: int = 2
    confidence: float = 1.0

    def to_dict(self):
        ...

@dataclass
class ScarAnnotation:
    """
    One scar — maps exactly to one Google Form submission.
    Multiple scars per encounter are saved individually.
    """
    scar_id: str
    encounter_code: str
    scar_type: str
    confidence: int
    side: str
    zone: str
    color: str
    bbox: Optional[Dict] = None
    mask_rle: Optional[str] = None
    area_pixels: int = 0

    def to_dict(self):
        ...

@dataclass
class CustomObservation:
    """Free-text labeled bounding box for anything interesting in frame."""
    obs_id: str
    label: str
    frame_number: int
    bbox: Dict

    def to_dict(self):
        ...

@dataclass
class SharkEncounter:
    """
    Complete annotation for one shark encounter (one video / one frame session).
    """
    encounter_code: str
    frame_number: Optional[int] = None
    body_bbox: Optional[Dict] = None
    body_mask_rle: Optional[str] = None

    def to_dict(self):
        ...

    def to_json(self):
        ...

    @classmethod
    def from_dict(cls, d: Dict) -> 'SharkEncounter':
        ...

class TrackSource(Enum):
    ...

class TrackStatus(Enum):
    ...

class PropagationStatus(Enum):
    ...

@dataclass
class TrackDetection:
    """One per-frame detection within a track. Mirrors the `track_detections` DB row."""
    frame_number: int
    bbox: Dict
    mask_rle: Optional[str] = None
    sam2_score: Optional[float] = None
    sharpness_score: Optional[float] = None
    area_score: Optional[float] = None
    composite_score: Optional[float] = None
    pose_json: Optional[str] = None

    def to_dict(self) -> Dict:
        ...

@dataclass
class Track:
    """A scar followed across multiple frames via SAM2 video propagation.

    Phase 1: the verified scar's TYPE / human-confirmed COLOR / NOTES are stored
    directly on the track. The graduated relational `scars` table arrives in Phase 3.
    """
    video_id: str
    encounter_code: str
    source: str
    seed_frame_number: int
    seed_annotator: str
    seed_bbox: Dict
    best_frame_number: Optional[int] = None
    frame_count: int = 0
    confidence_aggregate: Optional[float] = None
    auto_color: Optional[str] = None
    auto_color_confidence: Optional[float] = None
    auto_zone: Optional[str] = None
    auto_zone_confidence: Optional[float] = None
    auto_side: Optional[str] = None
    auto_side_confidence: Optional[float] = None
    auto_on_fin: bool = False
    pose_status: Optional[str] = None
    pose_model_version: Optional[str] = None
    human_color: Optional[str] = None
    human_zone: Optional[str] = None
    human_side: Optional[str] = None
    human_confidence: Optional[int] = None
    scar_type: Optional[str] = None
    human_verified: bool = False
    propagation_error: Optional[str] = None
    deleted_at: Optional[str] = None
    track_id: Optional[int] = None

    def to_dict(self) -> Dict:
        ...

def _leading_token(raw: Any) -> str:
    """Uppercase, then keep everything before the first separator."""
    ...

def normalize_zone(raw: Any) -> str:
    """Fold an Area label to its BodyZone code ('6 _FLANK' / '6-FLANK' -> '6')."""
    ...

def normalize_color(raw: Any) -> Tuple[str, str]:
    """Fold a Color answer to (ScarColor value, raw-if-not-exact).

    Returns OTHER plus the original text whenever the answer is not one of the
    four enum colours, INCLUDING for values that are plainly informative but not
    colours ("TAG PRESENT", "MISSING PARTS, NOT COLOR"). Those are observations
    the form had nowhere else to put, and folding them to a colour would invent
    data; dropping them would lose it. The caller keeps both.

    'MOSTLY GREY' and the recurring typo 'MOSTY WHITE' DO fold, because they name
    a colour and a hedge, not a different colour.
    """
    ...

def normalize_multiple_scars(raw: Any) -> str:
    """Fold the six legacy Multiple_scars instruction strings to YES / NO / ''.

    The live code tests `== "YES"`, which no legacy value matches — so the
    secondary-scar gate in compute_encounter_consensus could never open on
    imported data, and every secondary in a zone was dropped silently. Both
    separator conventions appear: 'YES _Submit and then score the next scar in
    this ZONE separately' and 'YES - Submit additional form'.
    """
    ...

def multiple_scars_in_same_zone(raw: Any) -> bool:
    """True only for the variant that declares the NEXT row is another scar in
    the SAME zone. Ordered by submission time that is recorded multiplicity, not
    a guess — it is the only evidence in the corpus for how many distinct marks a
    rater saw in one zone."""
    ...
