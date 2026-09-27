"""Stream G storage: staged field-trip ingest.

Three tables, one idea: **nothing a machine derived becomes catalog truth until a human
says so.** Same rule the track queue follows (`proposed → verified`), for the same
reason — a wrong size or date published to GBIF is unrecoverable.

    ingest_batches    one drag-and-drop, one row
    ingest_items      one dropped file, one row — WHERE A CODELESS CLIP WAITS
    ingest_proposals  one machine-derived claim, one row, superseded but never overwritten

Why items are staged instead of becoming `videos` rows immediately
------------------------------------------------------------------
`videos.id` is `str(uuid.uuid4())[:12]` and the Darwin Core occurrenceID descends from
it, so a row created and deleted is a published record orphaned. A card straight off the
boat is named `GX010042.MP4` and carries no encounter code, and `dwc_adapter` cannot mint
a stable eventID without one. So a file with no resolved code stays HERE, visible and
editable, and crosses into `videos` only once it has an identity that will not move.

Idempotency
-----------
Dropping the same trip folder twice is the single most likely user action in this
feature, so `commit_item` is adopt-not-insert: an entry matching an existing clip
updates that row and never mints a second id. Matching is by `drive_id` first (exact),
then `(encounter_code, video_name)`. `videos.drive_id` is UNIQUE as of migration v70,
which turns "we tried not to duplicate" into "the database refuses to".

Proposals are append-only
-------------------------
Accepting a value writes a NEW row and marks the old one `superseded`, rather than
mutating in place. An observation of sex can be revised, two sources can disagree, and a
review that silently overwrote its own history could not show either. `evidence` keeps
the raw token the value came from, so a human confirms against what was actually read.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from annotation.database import get_conn
from annotation.encounter_code import parse as parse_code_full

def init_ingest_tables() -> None:
    """Idempotently ensure the Stream G tables exist (mirrors migration v71).

    Migrations do not run in production — the versioned chain executes at Docker build
    time against a throwaway layer — so this is the path by which these tables reach the
    live volume DB. Both must exist and must agree.
    """
    ...

def _now() -> str:
    ...

def content_key(file_name: str, file_size: Optional[int]) -> str:
    """Fingerprint for 'the same file dropped again'.

    Name plus byte length. Not a hash: the browser never uploads the bytes, so a hash
    would require reading gigabytes client-side for every drop. Two distinct clips
    sharing a name AND an exact byte count is possible but vanishingly rare, and the
    consequence is a duplicate flag a human reviews — not a silent merge.
    """
    ...

def create_batch(*, created_by: str, label: Optional[str]=None, source_hint: Optional[str]=None, trip_key: Optional[str]=None) -> int:
    ...

def get_batch(batch_id: int) -> Optional[Dict[str, Any]]:
    ...

def list_batches(limit: int=50) -> List[Dict[str, Any]]:
    ...

def _classify(file_name: str) -> Dict[str, Any]:
    """What the filename alone can tell us. Never raises."""
    ...

def _existing_video(conn, *, drive_id: Optional[str], encounter_code: Optional[str], file_name: str) -> Optional[str]:
    """The catalog row this file already is, if any. drive_id wins — it is exact."""
    ...

def add_manifest(batch_id: int, entries: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Stage one drop. `entries` are what the BROWSER read — no bytes were uploaded.

    Each entry: {file_name, file_size?, file_mtime_utc?, drive_id?, media_type?,
    capture_started_utc?, capture_meta?}.

    Returns counts by resulting status. Re-adding the same file to the same batch is a
    no-op, so a retried or double-fired drop cannot duplicate rows.
    """
    ...

def _propose_from_item(conn, item_id: int, file_name: str, info: Dict[str, Any], entry: Dict[str, Any]) -> None:
    """Everything a machine believes about this file, as reviewable claims.

    Nothing here is written to the catalog. `evidence` records the exact token each
    value came from so a reviewer confirms against what was read, not against a summary.
    """
    ...

def list_items(batch_id: int, *, status: Optional[str]=None) -> List[Dict[str, Any]]:
    ...

def list_proposals(item_id: int) -> List[Dict[str, Any]]:
    ...

def set_item_code(item_id: int, encounter_code: str, *, by: str) -> Dict[str, Any]:
    """A human names a parked clip. This is the step that lets it become a videos row."""
    ...

def decide_proposal(proposal_id: int, *, accept: bool, by: str, value: Optional[str]=None) -> Dict[str, Any]:
    """Accept or reject a claim. Accepting with a corrected `value` supersedes rather
    than overwrites, so the original machine reading stays auditable."""
    ...

def accepted_values(item_id: int) -> Dict[str, str]:
    """field → value for this item's accepted, non-superseded claims."""
    ...

def commit_item(item_id: int, *, by: str) -> Dict[str, Any]:
    """Move one staged item into the catalog — adopting an existing row if there is one.

    Refuses a clip with no usable encounter code. That is not a limitation to work
    around: `dwc_adapter` derives eventID from the code, and a row created without one
    has no stable identity, so filling the code in later would silently move the record.
    Parked is the correct place for such a clip to live.
    """
    ...

def trip_overview(trip_key: str) -> Dict[str, Any]:
    """One field day at one site: its encounters in sequence, and how much of that day
    the catalog actually holds.

    On sequence gaps — **a gap is not a defect.** Measured across the 150 most recent
    trips, 75 of them have one, and `ANO251205` holds sharks 4, 9, 10 and 18 of an
    apparent 18. The lab numbers every shark it sights that day; only some are filmed,
    and only some of those are catalogued. So this reports gaps as COVERAGE — what we
    hold out of what was numbered — rather than as a to-do list. Presenting them as
    missing work would generate hundreds of false alarms and train people to ignore it.
    """
    ...

def code_anomalies() -> Dict[str, Any]:
    """Every encounter code the parser cannot fully trust, grouped by why.

    This is the point of `ParsedCode.status`. Measured on the live catalog these are 47
    rows out of 1,847 — small enough to fix by hand, and invisible until something lists
    them. Two of them carry an operator instruction (`2 SHARKS; DO NOT ENTER DATA`) that
    a stricter parser would have discarded along with the code.
    """
    ...

def list_trips(limit: int=200) -> List[Dict[str, Any]]:
    """Every field day the catalog knows about, most recent first."""
    ...
