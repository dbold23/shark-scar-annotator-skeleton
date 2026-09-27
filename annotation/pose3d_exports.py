"""Stream H — export projections over `pose3d_masks` / `pose3d_segments`.

Same decision as Darwin Core (`dwc_adapter.py`) and Stream F (`signal_exports.py`): the
two tables are the truth, and this module projects them **read-only** into formats that
already have readers. Nothing here writes to the database.

    coco          COCO instance segmentation (RLE) -> shark-pose-3d's COCO adapter and
                  `shark_pose/integration/annotator_bridge.py`, unchanged
    sidecar       per-frame {px_per_m, referent_plane, axis, chords[]} -> the metric-scale
                  and mask-IoU terms of the per-video fit
    measurements  flat CSV of the MANUAL morphometrics -- both training signal and the
                  baseline the 3D fit has to beat
    json          everything, unprojected, for debugging

Why `measurements` is not an afterthought: the closest published analogue to this pipeline
(model-based metric 3D reconstruction of wild dolphins, IJCV 2026) reports that the manual
2D measurement is *often more accurate* than their 3D fit, which only wins on larger
specimens. Exporting the manual numbers is how anyone can tell whether the puppet is an
improvement rather than assuming it.
"""
from __future__ import annotations
import csv
import io
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from annotation import db_pose3d as dbp

def _bbox_from_rle(rle: Optional[str]) -> Optional[List[float]]:
    ...

def _frame_key(m: dict) -> Tuple[str, int]:
    ...

def _group_segments(segments: Sequence[dict]) -> Dict[Tuple[str, int], List[dict]]:
    ...

def _axis_of(segs: Sequence[dict]) -> Optional[dict]:
    ...

def collect(*, video_id: Optional[str]=None, encounter_code: Optional[str]=None, annotator: Optional[str]=None, include_rejected: bool=False) -> Tuple[List[dict], Dict[Tuple[str, int], List[dict]]]:
    """Fetch the rows one export pass needs.

    `include_rejected` defaults to False for the training-data projections — a rejected
    frame asserts "there is no usable silhouette here", so shipping it into a COCO file as
    an annotation would be a contradiction. The rows are still exported by `to_json`,
    because "the segmenter failed on these frames" is exactly the signal that improves it.
    """
    ...

def to_coco(masks: Sequence[dict], by_frame: Dict[Tuple[str, int], List[dict]], *, description: str='SharkScarAnnotator — verified silhouettes (Stream H)') -> dict:
    """COCO instance segmentation with RLE `segmentation`.

    `view_class`, `fins_included` and the derived `px_per_m` ride along per-annotation
    under `attributes`. All three are load-bearing downstream and none has a standard COCO
    home: a consumer that averages a lateral and a dorsal silhouette, or mixes
    fins-in with fins-out contours, gets a shape that is nobody's shark.
    """
    ...

def to_sidecar(masks: Sequence[dict], by_frame: Dict[Tuple[str, int], List[dict]]) -> dict:
    """Per-frame scale, axis and chords, keyed the same way the COCO images are.

    A frame with no scale referent gets `"px_per_m": null`, never a default. "Not scaled"
    and "scaled to 1.0" are different claims, and only one of them is true here.
    """
    ...

def to_measurements_csv(masks: Sequence[dict], by_frame: Dict[Tuple[str, int], List[dict]]) -> str:
    """One row per chord, or one row per frame when a frame carries no chords.

    Long format rather than wide: chord stations are chosen per frame ("acquire a
    cross-section wherever there is a significant change in shape"), so a wide layout would
    need a fixed station grid that the annotation protocol deliberately does not impose.
    """
    ...

def to_full_json(masks: Sequence[dict], by_frame: Dict[Tuple[str, int], List[dict]]) -> dict:
    ...

def build(fmt: str, *, video_id: Optional[str]=None, encounter_code: Optional[str]=None, annotator: Optional[str]=None) -> Tuple[str, str, Any]:
    """Dispatch one export. Returns (mimetype, filename, payload)."""
    ...
