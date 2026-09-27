"""Stream D (annotator UX & tracks UI) — ROI marks + additive track edits.

Per the integration contract (plans/00-SHARED-CONTEXT.md §3.2) this is a per-stream DB
module: it reuses `get_conn()` from annotation/database.py and NEVER edits the database.py
monolith or the consensus algorithm. The `roi_marks` table is created by
scripts/migrate_schema_v40.py; the defensive `init_roi_tables()` here mirrors that DDL so the
module also works before the formal migration runs (fresh checkouts / tests).

ROI marks are deliberately lightweight: a box on one frame with NO scar form and NO
propagation — a quick flag or crop capture (re-ID gallery later, or promote to a track).
"""
from __future__ import annotations
import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional
from annotation.database import get_conn
_MAX_RETRY = 3

def _add_missing_columns() -> None:
    """`CREATE TABLE IF NOT EXISTS` silently no-ops on an existing table, so a
    column added only to the DDL above never reaches a DB that already has
    roi_marks. Prod is exactly that case."""
    ...

def init_roi_tables() -> None:
    """Idempotently ensure the roi_marks table exists (mirrors v40)."""
    ...

def _retry_write(fn):
    """Run a write closure, retrying on 'database is locked' (mirrors core CRUD)."""
    ...

def _clean_bbox(bbox: dict) -> Optional[dict]:
    """Validate/normalize a bbox to {x,y,width,height} floats. None if invalid."""
    ...

def _row_to_dict(row: sqlite3.Row) -> dict:
    ...

def create_roi_mark(*, video_id: str, bbox: dict, annotator: str, encounter_code: Optional[str]=None, frame_number: Optional[int]=None, time_sec: Optional[float]=None, note: str='', crop_b64: Optional[str]=None, permanence: Optional[str]=None, image_w: Optional[int]=None, image_h: Optional[int]=None) -> Optional[dict]:
    """Insert one ROI mark. Returns the stored row (with parsed bbox) or None on bad input."""
    ...

def get_roi_mark(mark_id: int) -> Optional[dict]:
    ...

def list_roi_marks(video_id: str, *, annotator: Optional[str]=None) -> List[dict]:
    """Live ROI marks for a video, newest first. Optionally filter to one annotator."""
    ...

def update_roi_note(mark_id: int, note: str, *, annotator: Optional[str]=None) -> Optional[dict]:
    """Set the note on one ROI mark. `annotator` scopes it to the owner; None = admin.

    Only the note is writable. A mark's geometry and frame are what it IS -- letting
    an edit move the box would silently change which pixels a colleague already
    reviewed, and there is no version of that anybody asked for.
    """
    ...

def delete_roi_mark(mark_id: int, *, annotator: Optional[str]=None) -> bool:
    """Soft-delete an ROI mark. If `annotator` is given, only the owner may delete."""
    ...
