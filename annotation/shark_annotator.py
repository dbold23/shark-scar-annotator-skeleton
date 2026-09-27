"""
Shark Scar Annotation System
Extends SAM2Segmenter for interactive shark body and scar annotation.
"""
import os
import sys
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import logging
from datetime import datetime
import json
from segmentation.sam2_segmenter import SAM2Segmenter, SegmentationResult
from annotation.models import SharkEncounter, ScarAnnotation, Keypoint, BoundingBox, ScarType, BodyZone, ScarColor, SideVisible, YesNo, SHARK_KEYPOINT_SEQUENCE, MORPHOMETRIC_PAIRS
from dataclasses import dataclass as _dataclass

@_dataclass
class Point2D:
    x: float
    y: float

@_dataclass
class MorphometricMeasurement:
    name: str
    point_a: str
    point_b: str
    distance_pixels: float

class SharkScarAnnotator(SAM2Segmenter):
    """
    Extended SAM2 segmenter specifically for shark scar annotation.
    Provides interactive tools for segmenting bodies, scars, and placing keypoints.
    """

    def __init__(self, config_path: str=None):
        """
        Initialize shark scar annotator.

        Args:
            config_path: Path to config YAML file
        """
        ...

    def start_new_encounter(self, encounter_code: str, image_path: str, annotator: str='') -> SharkEncounter:
        """
        Start a new shark encounter annotation session.

        Args:
            encounter_code: Unique encounter code (LOCYYMMDDnn format)
            image_path: Path to shark image
            annotator: Name of person annotating

        Returns:
            New SharkEncounter object
        """
        ...

    def segment_shark_body(self, point_coords: Optional[List[Tuple[int, int]]]=None, bbox: Optional[Tuple[int, int, int, int]]=None, save_mask: bool=True) -> SegmentationResult:
        """
        Segment the shark body using SAM2 with point or box prompt.

        Args:
            point_coords: List of (x, y) click points on shark body
            bbox: Bounding box (x, y, w, h) around shark
            save_mask: Whether to save the mask to file

        Returns:
            SegmentationResult for shark body
        """
        ...

    def segment_scar(self, scar_id: str, point_coords: List[Tuple[int, int]], scar_type: ScarType, confidence: int, side: SideVisible, zone: BodyZone, color: ScarColor, color_other: Optional[str]=None, notes: str='', copepods_on_body: YesNo=YesNo.UNKNOWN, copepods_on_wound: YesNo=YesNo.UNKNOWN, save_mask: bool=True) -> ScarAnnotation:
        """
        Segment an individual scar and create annotation with metadata.

        Args:
            scar_id: Unique identifier for this scar
            point_coords: Click points on the scar
            scar_type: Type of scar
            confidence: Confidence rating (1-5)
            side: Which side of shark
            zone: Body zone where scar is located
            color: Scar color
            color_other: Description if color is OTHER
            notes: Additional notes
            copepods_on_body: Copepod presence on body
            copepods_on_wound: Copepod presence on wound
            save_mask: Whether to save mask to file

        Returns:
            ScarAnnotation object
        """
        ...

    def add_keypoint(self, name: str, point: Tuple[float, float], confidence: float=1.0, visible: bool=True) -> Keypoint:
        """
        Add an anatomical keypoint for morphometrics.

        Args:
            name: Keypoint name (e.g., "snout_tip")
            point: (x, y) coordinate
            confidence: Confidence score
            visible: Whether keypoint is visible in image

        Returns:
            Keypoint object
        """
        ...

    def compute_morphometrics(self) -> List[MorphometricMeasurement]:
        """
        Compute standard morphometric measurements from keypoints.

        Returns:
            List of MorphometricMeasurement objects
        """
        ...

    def draw_body_zones(self, image: np.ndarray, body_mask: Optional[np.ndarray]=None) -> np.ndarray:
        """
        Draw body zone overlay on shark image.
        Divides shark body into anatomical zones (1-T).

        Args:
            image: Input image
            body_mask: Optional body segmentation mask to guide zone placement

        Returns:
            Image with zone overlay
        """
        ...

    def visualize_annotation(self, show_body: bool=True, show_scars: bool=True, show_keypoints: bool=True, show_zones: bool=False, save: bool=True) -> np.ndarray:
        """
        Create comprehensive visualization of all annotations.

        Args:
            show_body: Show body segmentation
            show_scars: Show scar segmentations
            show_keypoints: Show keypoint locations
            show_zones: Show body zone overlay
            save: Save visualization to file

        Returns:
            Visualization image
        """
        ...

    def save_encounter(self, filepath: Optional[str]=None) -> str:
        """
        Save current encounter to JSON file.

        Args:
            filepath: Optional custom filepath. If None, uses default naming.

        Returns:
            Path to saved JSON file
        """
        ...

    def load_encounter(self, filepath: str) -> SharkEncounter:
        """
        Load encounter from JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            Loaded SharkEncounter object
        """
        ...

    def export_to_coco(self, output_path: str, encounters: List[SharkEncounter]):
        """
        Export annotations to COCO format for machine learning.

        Args:
            output_path: Path to output JSON file
            encounters: List of encounters to export
        """
        ...

def main():
    """Example usage"""
    ...
