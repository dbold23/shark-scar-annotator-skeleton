"""
Google Sheets export for SharkScarAnnotator.
Pushes annotation CSV data to a Google Sheet so the Colab notebook pipeline
can read from Sheets instead of (or alongside) Google Forms responses.

Tabs:
  - "Scars"     — scar annotations from video encounters (Google Forms CSV format)
  - "Keypoints"  — keypoint/pose annotations from image frames (wide format)
  - "Admin Flags" — admin-flagged encounters (managed separately)
"""
import csv
import hashlib
import io
import logging
import random
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Optional
from annotation.export import export_google_forms_csv, FORMS_COLUMNS, export_keypoint_csv, KEYPOINT_COLUMNS

class SheetUpsertError(RuntimeError):
    """The delete half of an upsert could not be completed *safely*.

    Raised so the caller refuses to append: appending after a failed delete
    silently converts the upsert into an append and permanently duplicates that
    frame's rows in the Colab pipeline's input.
    """
_LOCK_TIMEOUT_SEC = 120.0

def _lock_path(sheet_id: str) -> Path:
    ...

@contextmanager
def sheet_upsert_lock(sheet_id: str, timeout: float=_LOCK_TIMEOUT_SEC):
    """Exclusive, cross-process lock over one spreadsheet's upsert cycle.

    Yields True when held. If the platform has no flock or the lock file cannot
    be created we yield False and proceed unlocked rather than dropping the
    sync — degraded, but no worse than the previous behaviour. Failing to
    ACQUIRE within `timeout` raises, because that means another writer is
    mid-cycle and proceeding would be exactly the race this guards.
    """
    ...

def _sheets_api_retry(fn, max_retries=3):
    """Execute a Google Sheets API call with exponential backoff + jitter."""
    ...

def _ensure_tab_with_header(sheets_service, sheet_id: str, tab_name: str, header_row: list):
    """Ensure tab exists and has a header in row 1. Creates tab if needed."""
    ...

def _get_tab_gid(sheets_service, sheet_id: str, tab_name: str) -> Optional[int]:
    """Get the numeric sheetId (gid) for a tab by name."""
    ...

def export_to_sheet(sheets_service, annotations: List[Dict], sheet_id: Optional[str]=None, sheet_title: str='SharkScar App Annotations') -> dict:
    """
    Export annotations to a Google Sheet.

    If sheet_id is None, creates a new spreadsheet.
    If sheet_id is provided, appends new data rows (skips header).

    Returns {"sheet_id": ..., "url": ..., "rows_written": int}
    """
    ...

def _key_layout(tab_name: str):
    """Where the upsert key lives on each tab.

    Returns (scan_range, clip_index) — the A1 column span to read, and the
    zero-based index of the clip cell WITHIN that span. Email/Encounter/Frame are
    always B/C/D (indices 0/1/2). Keypoints carries `Video_name` in column E
    (KEYPOINT_COLUMNS), Scars in column R (appended to FORMS_COLUMNS)."""
    ...

def _row_matches(row: list, key: tuple, clip_idx: int) -> bool:
    """`key` is (email, encounter, frame, video_name). A row written before the
    clip column existed has no clip cell, so it can never match — it is left in
    place and the new row is appended beside it. A duplicate is recoverable by
    dedup; a deleted row is not."""
    ...

def _rows_still_match(sheets_service, sheet_id: str, tab_name: str, row_indices: List[int], key: tuple) -> bool:
    """Re-read exactly the rows we are about to delete and confirm they still
    hold `key` (email, encounter, frame, video_name).

    Defence in depth behind the lock: the lock covers this app's own writers,
    but an admin export, a second container, or a human editing the sheet can
    still shift rows between the scan and the delete. Verifying content at the
    index is the difference between deleting the intended row and deleting
    whatever slid into its slot. Same span and predicate as the scan — a narrower
    re-read would never verify, burn every attempt and stall the outbox.
    """
    ...

def _delete_existing_rows(sheets_service, sheet_id: str, annotation: Dict, tab_name: str='Scars', max_attempts: int=3, video_name: Optional[str]=None) -> int:
    """Delete existing sheet rows for the same encounter+frame+annotator+CLIP.

    Returns the number of rows deleted (0 if there were none). Raises
    SheetUpsertError if it cannot GUARANTEE the stale rows are gone — the caller
    must then skip its append, leaving the previous rows in place rather than
    duplicating the frame. Callers are expected to hold `sheet_upsert_lock`.
    """
    ...

def append_annotation_to_sheet(sheets_service, annotation: Dict, sheet_id: Optional[str]=None, sheet_title: str='SharkScar App Annotations', media_type: Optional[str]=None, video_name: Optional[str]=None) -> dict:
    """
    Upsert a single annotation to a Google Sheet on save.

    Routes to the correct tab based on media_type:
      - media_type='image' → "Keypoints" tab (wide keypoint format)
      - media_type='video' or None → "Scars" tab (Google Forms CSV format)

    If sheet_id is None, creates a new spreadsheet.
    If sheet_id is provided, deletes existing rows for the same
    encounter+frame+annotator, then appends fresh rows.

    Returns {"sheet_synced": True, "sheet_url": ..., "rows_added": N}
    or {"sheet_synced": False, "sheet_error": "..."} on failure.
    """
    ...

def sync_admin_flags_to_sheet(sheets_service, encounters: List[Dict], sheet_id: str) -> dict:
    """
    Write admin flags/notes to an 'Admin Flags' tab on the export spreadsheet.
    Creates the tab if it doesn't exist. Clears + rewrites all data each sync.

    Returns {"synced": True, "count": N} or {"synced": False, "error": "..."}.
    """
    ...
