"""
Export module for SharkScarAnnotator.
Supports COCO JSON, Google Forms CSV, and full JSON dump.
"""
import json
import csv
import io
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from annotation.models import ScarType
from annotation.db_datasets import sides_from_model

def _sides_cells(enc: Dict) -> Dict[str, str]:
    """The human's flank-coverage answer and the model's, kept in separate cells.

    Since 2026-09-02 the SIDES SEEN control is PRE-SELECTED with the model's
    per-clip answer, so a labeler who never touches it still saves a
    `sides_visible`. Publishing that under their email — in a CSV a researcher
    reads, or a DwC record an aggregator indexes — states that a person made a
    coverage claim they never made, and nothing downstream could tell.

    So the human column carries a value ONLY when a person put it there. A
    machine answer exports BLANK, which is what blank has always meant in these
    columns ("not recorded"), and the model's answer goes beside it under a name
    nobody can mistake for a human one.

    The model cell is populated whether or not the human touched the control:
    where they DID answer, having both side by side is the whole comparison the
    suggestion is judged by. It falls back to `sides_visible` when an accepted
    hint somehow carries no side of its own, so the value is never lost — only
    re-attributed.
    """
    ...

def _is_numeric(s: str) -> bool:
    ...

def _needs_csv_escape(s: str) -> bool:
    """True if `s` would be parsed as a formula, or would become one after the
    escape prefix is stripped (so escaping stays reversible)."""
    ...

def csv_safe(value: Any) -> Any:
    """Neutralize a leading formula trigger in a CSV cell. Non-strings and
    values that are not formula-shaped pass through unchanged."""
    ...

def csv_unescape(value: Any) -> Any:
    """Exact inverse of `csv_safe`: recover the author's original text."""
    ...

def _safe_row(row: Dict, enabled: bool) -> Dict:
    ...

def export_coco(annotations: List[Dict], include_keypoints: bool=True) -> Dict:
    """
    Build a COCO-format dict from a list of SharkEncounter dicts.
    Categories: shark_body, scar, observation (custom bboxes).
    """
    ...
from annotation.models import AREA_FORM_FORMAT, SCAR_TYPE_FORM_FORMAT, MULTIPLE_SCARS_FORM_FORMAT

def _encounter_copepods_cells(encounter_code: str) -> Dict[str, str]:
    """The encounter's copepods answer, as two CSV cells.

    Copepods are a property of the animal, so the answer comes from raters who saw
    the whole encounter rather than from whoever boxed this one scar. Only a
    UNANIMOUS answer is exported: a split cohort is a finding about the cohort, and
    writing one side of it into a column that reads as fact would launder a
    disagreement into a measurement. Unknown and disputed both export blank, which
    is what this column has always meant by blank.

    Import failures degrade to blank rather than raising — an export must not die
    because a lookup table predates this build.
    """
    ...

def export_google_forms_csv(annotations: List[Dict], formula_safe: bool=True, include_model_columns: bool=True) -> str:
    """
    Export one row per scar, matching Google Form column structure
    so existing Colab SQL notebooks work without modification.
    Returns CSV as string.

    `formula_safe` (default ON) prefixes cells that a spreadsheet would parse as
    a formula with an apostrophe — see `csv_safe`. Pass False for the Google
    Sheets path, which is already guarded by valueInputOption="RAW".

    `include_model_columns` (default ON) appends `Sides_visible_model`. It is ON
    for a file somebody downloads, where every row is written fresh in one pass,
    and OFF for the Google Sheets path — see the call sites in
    `google_sheets_export.py`, which explain why that sheet cannot take a new
    column safely. `Sides_visible` itself carries the HUMAN answer in both cases:
    that is a correctness rule, not a formatting one, and it is not optional.
    """
    ...

def export_keypoint_csv(annotations: List[Dict], formula_safe: bool=True) -> str:
    """
    Export one row per frame with 16 keypoint coordinates in wide format.
    Returns CSV as string.

    `formula_safe` — see `export_google_forms_csv`.
    """
    ...

def export_full_json(annotations: List[Dict]) -> str:
    ...

def _consensus_detail_rows(row: Dict) -> List[Dict]:
    """Flatten one `consensus_cache` row into its per-scar entries, normalising
    the two detail shapes. Returns [] for a row with no usable details — a
    malformed blob is skipped, never emitted as a scar with zero agreement."""
    ...

def flatten_consensus(rows: List[Dict], min_agreement: int=0) -> Dict:
    """Project `consensus_cache` rows onto one row per consensus scar.

    `min_agreement` keeps only scars at least that many raters agreed on (the
    user-facing "3+ agreement" filter). A scar whose count is missing is DROPPED
    by any filter above 0 and kept at 0 — an unknown count must not pass a bar it
    was never measured against, and must not be silently rewritten to zero either.

    Returns {"scars": [...], "summary": {...}} so a caller can always report the
    denominator. An export that says "256 scars" without saying "out of 3,702,
    from 93 of 1,485 encounters" reads as a corpus size.
    """
    ...

def export_consensus_csv(rows: List[Dict], min_agreement: int=0, formula_safe: bool=True) -> str:
    """One row per consensus scar. Header is always written, so an empty result
    is a table with no rows rather than an empty file."""
    ...

def export_consensus_json(rows: List[Dict], min_agreement: int=0) -> str:
    ...

def export_golden_items_csv(sets: List[Dict], formula_safe: bool=True) -> str:
    """Flatten every frozen eval set's items. `sets` are rows from
    `list_golden_eval_sets()` each carrying an `items` list."""
    ...

def export_gold_json(sets: List[Dict], answers: List[Dict]) -> str:
    """Every gold standard set and every answer key, in one bundle.

    An empty result is reported AS empty, with a note saying which of the two
    things is missing — a bare `[]` here is indistinguishable from "this feature
    was never switched on", and those need different responses from an admin.
    """
    ...
