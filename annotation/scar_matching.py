"""Spatial (IoU-based) clustering of scar annotations.

Building block for a spatially-aware consensus: cluster scars from multiple
annotators into "same physical scar" groups by bounding-box overlap, so that
the same categorical label at *different* locations is not falsely merged, and
the same physical location with *different* zone labels is not falsely split.

This is self-contained and unit-tested (tests/test_scar_matching.py). It is
deliberately NOT yet wired into database.compute_encounter_consensus: that
would change a production algorithm and must be validated against real
multi-annotator + bbox data first. Fallback contract: scars without a usable
bbox each form their own singleton cluster, so legacy annotations with no boxes
behave exactly as the existing categorical-signature path does.
"""
from typing import Dict, List
from annotation.eval_metrics import bbox_iou

def has_bbox(scar: Dict) -> bool:
    """True if the scar carries a usable (positive-area) bounding box."""
    ...

def cluster_scars_by_iou(scars: List[Dict], iou_threshold: float=0.4) -> List[List[Dict]]:
    """Greedily cluster scars into "same physical scar" groups by bbox overlap.

    Args:
        scars: scar dicts, each optionally carrying a ``bbox`` ({x,y,width,height}
            or [x,y,w,h]).
        iou_threshold: minimum IoU for two boxes to be considered the same scar.

    Returns:
        A list of clusters; each cluster is a list of the input scar dicts.
        A scar joins a cluster if it overlaps ANY member of that cluster at or
        above ``iou_threshold`` (single-link). Scars without a usable bbox are
        returned as singleton clusters, appended after the spatial clusters.
        Input order is otherwise preserved.
    """
    ...
COPEPOD_ON_WOUND_COVERAGE = 0.5

def _xywh_of(scar: Dict):
    ...

def coverage_of_first(a: Dict, b: Dict) -> float:
    """Fraction of scar `a`'s box that lies inside scar `b`'s box. 0.0 if disjoint."""
    ...

def derive_copepods(scars: List[Dict], declared: Dict=None) -> Dict:
    """Infer copepod presence from the boxed scars, falling back to a declared answer.

    A COPEPODS box is positive evidence. Its ABSENCE is not negative evidence: the
    type has never once been used in the live corpus, which is exactly what a labeler
    who does not reach for it looks like. So "no copepod box" yields UNKNOWN, not NO —
    unless somebody actually answered the old question, in which case that answer is
    preserved and reported as `declared`.

    Returns on_body / on_wound in the YES|NO|UNKNOWN vocabulary the rest of the
    encounter fields use, plus the evidence, so a reader can audit the call.
    """
    ...
