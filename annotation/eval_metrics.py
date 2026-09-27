"""Stream B (MLOps) — pure evaluation metrics for the golden-set harness.

No DB, no model, no numpy: takes ground-truth + predictions as plain Python and
returns reproducible metrics. Kept dependency-free so it imports anywhere and so
the numbers are byte-stable for the eval gate (B3). Three metric families:

  * detection   — IoU matching → per-class AP (VOC all-point) + mAP + P/R
  * classification — accuracy, per-class P/R/F1, macro-F1, confusion matrix
  * pose        — PCK@alpha (keypoints within alpha·norm of truth)

The scar-type head is a CLASSIFIER (categorical), so classification metrics are
the primary signal for the verified-track golden set; detection AP applies when a
box-predicting model is scored; pose PCK applies to the keypoint model.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

def _xywh(b) -> Optional[Tuple[float, float, float, float]]:
    """Normalize a bbox (dict {x,y,width,height} or sequence [x,y,w,h]) → tuple."""
    ...

def bbox_iou(a, b) -> float:
    """IoU of two boxes in {x,y,width,height} (or [x,y,w,h]) form. 0.0 if disjoint."""
    ...

def _voc_ap(rec: List[float], prec: List[float]) -> float:
    """VOC all-point average precision from a PR curve."""
    ...

def detection_metrics(items: Sequence[Dict], preds_by_item: Sequence[Sequence[Dict]], iou_thr: float=0.5) -> Dict[str, Any]:
    """Detection AP/mAP. Each item has one GT box: ``{"bbox":..., "label":...}``.
    ``preds_by_item[i]`` = list of ``{"bbox":..., "score":..., "label":...}``.

    A prediction is a TP if it matches its item's GT (same label, IoU≥thr) and that
    GT is not already claimed by a higher-scoring prediction. Per-class AP via the
    VOC all-point rule; mAP = mean over classes with ≥1 GT.
    """
    ...

def classification_metrics(true_labels: Sequence[Optional[str]], pred_labels: Sequence[Optional[str]], classes: Optional[Sequence[str]]=None) -> Dict[str, Any]:
    """Accuracy + per-class P/R/F1 + macro-F1 + confusion. Items where the truth is
    None are skipped; a None prediction counts as a wrong answer (model abstained)."""
    ...

def pck(true_kpts_by_item: Sequence[Sequence[Tuple[float, float, int]]], pred_kpts_by_item: Sequence[Sequence[Tuple[float, float, int]]], norms: Sequence[float], alpha: float=0.1) -> Dict[str, Any]:
    """PCK@alpha: a predicted keypoint is correct if within ``alpha*norm`` of the
    GT keypoint. ``norm`` is per-item (e.g. bbox diagonal). Only GT keypoints with
    visibility>0 count. Returns overall + per-keypoint-index PCK."""
    ...
