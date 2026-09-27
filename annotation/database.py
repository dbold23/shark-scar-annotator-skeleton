"""
Database manager for SharkScarAnnotator.
Handles the video catalog, assignments, and annotation storage.
"""
import os
import csv
import sqlite3
import json
import logging
import time
import uuid
import threading
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from annotation.models import normalize_zone, normalize_color, normalize_multiple_scars, multiple_scars_in_same_zone

def _normalize_email(email: str) -> str:
    """Fix known email typos from historical CSV data."""
    ...

def _seed_semesters(conn):
    """Seed semester_quotas table with Spring/Summer/Fall entries and mark current as active."""
    ...

def get_conn() -> sqlite3.Connection:
    """Get or create a thread-local SQLite connection."""
    ...

def close_conn():
    """Close thread-local connection if it exists."""
    ...

def foreign_key_violations(limit: int=200) -> List[Dict]:
    """Rows that violate a declared foreign key, via `PRAGMA foreign_key_check`.

    Enabling enforcement does NOT retro-validate rows already on disk -- SQLite only
    checks statements issued from then on. So a DB that collected orphans while the
    pragma was off keeps them, and they only surface later as an IntegrityError on an
    unrelated UPDATE. Run this after migrating to see what is already broken.

    Each dict: {table, rowid, parent, fkid} -- `rowid` is None for WITHOUT ROWID tables.

    Capped at `limit` rows, and a full result means "at least this many": callers that
    print a count must say so rather than reporting the cap as the total.
    """
    ...
_OUTBOX_RECLAIM_SECONDS = 300
_OUTBOX_MAX_ATTEMPTS = 6
_OUTBOX_RETRY_DELAY_SECONDS = 60

def make_annotation_id(video_id: str, frame_number: int, annotator: str) -> str:
    """Deterministic annotation primary key. One row per (video, frame, annotator)."""
    ...

def init_durability_tables():
    """Create the durability substrate on startup (like init_encounter_tables).

    Runs at import so the tables exist on the persistent DB without depending on
    the versioned migration chain (which the running app does not execute — see
    app.py startup). The assignments UNIQUE(video_id, annotator_email) guard is
    created here only when the data is already clean; if duplicates exist we skip
    and defer to scripts/migrate_schema_v50.py, which backs up and de-dupes
    first. We never auto-delete rows at boot.
    """
    ...

def enqueue_outbox(conn: sqlite3.Connection, payload_json: str, kind: str='annotation_sync') -> int:
    """Insert a durable sync task. MUST be called inside an already-open
    transaction (the same `conn`) so the outbox row commits atomically with its
    source row (e.g. the annotation). Do not open a new connection here."""
    ...

def claim_next_outbox() -> Optional[Dict]:
    """Atomically claim the next pending (or abandoned) outbox task.

    Returns {id, kind, payload_json, attempts} or None if nothing is claimable.
    Safe under concurrency: SQLite serializes writes, and the conditional UPDATE
    (guarded by rowcount) guarantees only one caller wins each row — so it is
    correct even if every Gunicorn worker runs its own drain loop."""
    ...

def finish_outbox(outbox_id: int) -> None:
    """Mark a sync task done. Delete on success to keep the table small."""
    ...

def fail_outbox(outbox_id: int, error: str, max_attempts: int=_OUTBOX_MAX_ATTEMPTS) -> Optional[str]:
    """Record a failed attempt: requeue for retry, or park as 'failed' once the
    attempt budget is exhausted (left in the table for manual inspection).
    Returns the new status so the caller can shout when a task is PARKED — the
    frame JPEG inside a parked task exists nowhere else."""
    ...

def count_failed_outbox() -> tuple[int, Optional[str]]:
    """(how many sync tasks are parked, when the oldest was parked) — for /health."""
    ...

def count_pending_outbox() -> int:
    """Count sync tasks still owed (pending or in-flight). Used by tests/health."""
    ...

def set_job(job_id: str, kind: str, *, status: Optional[str]=None, progress_pct: Optional[float]=None, progress_msg: Optional[str]=None, detail: Optional[Dict]=None, error: Optional[str]=None, reset: bool=False) -> None:
    """Upsert a background job's shared status. `reset=True` starts a fresh row
    (all fields overwritten); otherwise only the provided fields are merged, so
    frequent progress ticks don't clobber the status/result."""
    ...

def get_job(job_id: str) -> Optional[Dict]:
    """Read a job's shared status from any worker. Returns None if unknown."""
    ...

class DbJob:
    """Dict-like background-job status backed by the shared `jobs` table.

    Lives here rather than in app.py so blueprints can use it. It cannot be
    imported from app.py at all: `annotation/routes_reid.py` is imported ~3,400
    lines before the class was defined there, and under `python app.py` the running
    module is `__main__`, so `import app` misses sys.modules and re-executes the
    file — building a second Flask app, the exact failure routes_reid's own
    docstring records.

    The point is cross-worker visibility. A module-level dict is per-process, so
    under four Gunicorn workers roughly three of four status polls land on a worker
    that never ran the job and report "idle" for something actively running.

    Supports both the plain-item style (job["status"] = "running") and the
    keyword style (job.update(status="running", progress="3/10")), plus dict()
    and iteration, so existing call sites work unchanged either way.
    """

    def __init__(self, job_id: str, kind: str):
        ...

    def claim(self, stale_after: Optional[timedelta]=None) -> bool:
        """Atomically move idle→running across ALL workers. False if one is in flight.

        One UPDATE inside one write transaction is the whole guard: SQLite serialises
        the two writers, so the loser matches 0 rows. A threading.Lock cannot do this
        — it is per-process, and prod runs four. Without it, an admin who sees "idle"
        because their poll landed on a different worker clicks again and starts a
        second concurrent run of the same job.

        The staleness clause is what stops a worker that died mid-run from wedging
        the job forever: its row stays 'running' with an `updated_at` that never
        advances, and after `stale_after` the next caller may take it.
        """
        ...

    def reset(self, status: str='running', progress: str='', result: Any=None, error: Any=None) -> None:
        ...

    def update(self, **kw: Any) -> None:
        """Set several fields in ONE write.

        Not just sugar: the per-item progress loops in routes_reid call this on
        every item, and doing four separate set_job round-trips per tick would turn
        a progress bar into four UPDATEs a frame.
        """
        ...

    def __setitem__(self, key: str, value: Any) -> None:
        ...

    def __getitem__(self, key: str) -> Any:
        ...

    def get(self, key: str, default: Any=None) -> Any:
        ...

    def keys(self):
        ...

    def __iter__(self):
        ...

    def progress(self, msg: Any) -> None:
        """Advance the progress line without touching status."""
        ...

    def complete(self, result: Any=None) -> None:
        ...

    def fail(self, error: Any) -> None:
        ...

    def snapshot(self) -> Dict[str, Any]:
        ...

def clear_job(job_id: str) -> None:
    ...

def active_job_of_kind(kind: str, statuses: Tuple[str, ...]=('running', 'downloading')) -> Optional[Dict]:
    """Return an in-flight job of this kind (cross-worker guard), or None."""
    ...

def _archive_consensus_import(conn, encounter_id: str, *, overwrite: bool) -> None:
    """Copy this encounter's non-computed cache row into `consensus_imports`.

    `overwrite=True` is for the importers themselves — a re-import is authoritative
    about its own archive. Every other caller passes False and therefore can only
    ever ADD an archive row, never replace one: the row being copied may already
    have been degraded in place (refresh_all_consensus NULLs the score of any row
    with <2 annotators), and a degraded copy must not overwrite the real one.
    """
    ...

def _not_poorer(conn, encounter_id: str, incoming: Dict) -> bool:
    """Whether an incoming import may overwrite the archived one.

    A re-import of the same complete sheet is authoritative about its own
    archive. A PARTIAL or mis-scoped upload is not: replacing a 7-rater archived
    consensus with a 2-rater one destroys the only record of the first, and
    nothing anywhere can rebuild it. Never replace a scored row with a
    NULL-score needs_analysis one (the single-rater import branch).
    """
    ...

def _store_import_consensus(conn, encounter_id: str, payload: Dict) -> None:
    """Write one IMPORTED consensus row — the only way the two importers may.

    Two rules, both about the population nothing can rebuild:
      1. An importer never replaces a `source='computed'` row. The computed row
         self-heals on the next cron pass, but INSERT OR REPLACE used to clobber
         it AND then archive the import over the encounter's previous archive.
         When the live slot is held by a computed row, the import goes straight
         to the archive instead (a bare skip would drop it — the archive helper
         SELECTs from the live slot).
      2. The archive is replaced only when the incoming row is not poorer
         (`_not_poorer`). Not `overwrite=False` wholesale: every encounter on the
         live catalog already has an archive row, so INSERT OR IGNORE would make
         every future archive write a permanent no-op.
    `payload` carries the CONSENSUS_ARCHIVE_COLUMNS values (encounter_id is
    filled in here); absent keys are NULL.
    """
    ...

def _archive_then_delete_consensus(conn, encounter_id: str) -> None:
    """Invalidate one encounter's consensus row, having first archived it.

    ONE invariant, and it is the whole point of v44: **nothing deletes a consensus
    row it has not first copied into `consensus_imports`.** Stating it as an order
    of operations rather than as a cleverer WHERE clause is deliberate — the
    `source` predicate is only as good as the classification having already run,
    and the classification runs in `init_encounter_tables()`, which the save path
    does not call. Archive-then-delete needs no such assumption.

    The archive only ever copies rows that are not `computed`, so a row this
    process wrote itself moments ago costs one no-op INSERT.

    If `consensus_imports` is missing, NEITHER step happens. A DB whose schema
    pre-dates v44 and has not been re-inited is exactly the case where a delete
    would be unrecoverable, so the safe answer is a stale cache row, not a lost
    one.
    """
    ...

def get_imported_consensus(encounter_id: str) -> Optional[Dict]:
    """The archived legacy-Forms consensus for an encounter, or None.

    Read-only and never recomputed. For 1,485 encounters this is the only record
    of the cohort that produced it.
    """
    ...
_ENCOUNTER_TABLES_TTL_S = 3600.0

def init_encounter_tables(force: bool=False):
    """Create encounter priority tables if they don't exist.

    Idempotent and, since the memo above, effectively free after the first
    call per process per DB. `force=True` runs it regardless -- for a caller
    that has just changed the schema underneath a running process.
    """
    ...

def _init_encounter_tables_now():
    ...

def add_video(video_name: str, drive_id: str='', video_path: str='', encounter_code: str='', site: str='', year: int=0, date: str='', notes: str='', added_by: str='', media_type: str='video') -> str:
    ...

def import_csv(csv_path: str, added_by: str='') -> Tuple[int, List[str]]:
    """
    Bulk-import from CSV.
    Expected columns: encounter_code, video_name, drive_id, site, year, date, notes
    Returns (count_added, list_of_errors)
    """
    ...

def list_videos(annotator_email: str='', admin: bool=False) -> List[Dict]:
    ...

def get_video(video_id: str) -> Optional[Dict]:
    ...

def update_video_status(video_id: str, status: str):
    ...

def portable_video_path(local_path: str) -> str:
    """Store a cache path RELATIVE to the repo root whenever it lives inside it.

    Absolute paths rot. This catalog carried 324 rows pointing at
    /Volumes/.../SharkScarAnnotator/tmp_videos/... — the location the repo sat in
    before it moved under projects/marine-cv/ — and every one of them was a dead
    file that presented as a blank canvas rather than as a missing video. The path
    is a pointer into OUR OWN cache directory, so it has no business encoding where
    the checkout happens to live today.

    Paths outside the root (an operator pointing at an external drive via
    video.extra_dirs) are left absolute, because for those the location IS the
    information.
    """
    ...

def update_video_path(video_id: str, local_path: str):
    ...

def clear_video_path(local_path: str) -> None:
    """Clear the cached local path for any video pointing at it. Called after LRU
    eviction of a tmp_videos file so the next stream falls through to a fresh
    re-download instead of 404ing on the deleted file.

    Matches on both spellings: rows written before paths were stored root-relative
    still hold the absolute form, and an eviction that failed to clear them would
    leave the catalog pointing at a file that is gone.
    """
    ...

def update_video_drive_link(video_id: str, drive_id: str, video_name: str):
    """Update a video's drive_id and name after finding on Drive."""
    ...

def get_assignments_for_video(video_id: str) -> List[Dict]:
    """Get all assignments for a video."""
    ...

def assign_video(video_id: str, annotator_email: str, assigned_by: str, priority: str='medium', due_date: str='', notes: str='') -> int:
    ...

def is_assigned_to(annotator_email: str, video_id: str) -> bool:
    """Does this annotator hold an assignment on this video, in any state?

    Used as the permission basis for contributing a track verification when
    multi-rater verification is enabled: assignment is the existing model for
    "this person is trusted with this footage", so reusing it widens access to
    exactly that group rather than to anyone holding a login.

    Any status counts, `completed` included — finishing the pass over a clip does
    not stop you being a legitimate second opinion on a scar found in it.
    """
    ...

def update_assignment_status(video_id: str, annotator_email: str, status: str):
    ...

def complete_video(video_id: str, annotator_email: str) -> Dict:
    """Mark an annotator's work on a video as complete.

    Updates assignment status, video status (if all assignments done),
    encounter completion count, and returns the next assigned video.
    """
    ...

def init_core_tables():
    """Create the four baseline tables: videos, assignments, annotations, users.

    These are the oldest tables in the product and, until now, had the WEAKEST
    creation guarantee of any of them. They were built only by scripts/init_db.py,
    which reaches a running production container by neither of its two paths:

      - the Dockerfile runs it at BUILD time, writing into /app/database inside the
        image — a directory docker-compose then shadows with the ./database bind
        mount, so the tables it made are never the ones served;
      - app.py calls init_db() inside `if __name__ == "__main__"`, which Gunicorn
        never executes.

    An existing volume is fine because it predates all this, but a fresh host with
    an empty ./database would start with no core tables at all — while every NEWER
    module (reid, roi, signals, mlops, gamification, datasets) ensures its own on
    first use. Calling this unconditionally at import, as app.py already does for
    the encounter and track tables, closes that gap. DDL is shared with
    scripts/init_db.py so the two cannot drift.
    """
    ...

def _column_exists(conn, table: str, col: str) -> bool:
    ...

def init_annotation_columns():
    """Phase 1: denormalized per-annotation counts for the progress hot path.

    Adds nullable `n_scars` / `n_keypoints` columns (additive, byte-identical
    when already present). They are written on every save and populated for
    historical rows by scripts/migrate_schema_v51.py. Created at import (like the
    other init_*_tables) so they exist on the persistent DB; get_progress_counts
    falls back to parsing the JSON blob until the backfill has run, so counts are
    never wrong in the meantime."""
    ...

def annotation_counts(json_data: Dict) -> Tuple[int, int]:
    """Return (n_scars, n_keypoints_placed) for one annotation blob.

    This is the single source of truth for the denormalized progress columns —
    it MUST mirror the per-annotation logic in get_progress_counts (scars =
    len(scars); a pose 'counts' when any keypoint has visibility v>0)."""
    ...

class UnknownVideoError(ValueError):
    """save_annotation was handed a video_id with no row in `videos`.

    Only reachable now that get_conn enforces foreign keys. Previously the write
    succeeded and produced an annotation that could never be joined back to a
    video -- exactly the damage scripts/fix_relink_annotations.py had to undo
    after video ids were reassigned in March 2026.
    """
CLIENT_ASSUMED_FPS = 30.0

def init_frame_provenance_columns():
    """Provenance for the frame_number backfill (plan 13 §6.0).

    Additive and byte-identical when already present, like init_annotation_columns.
    Created at import rather than only in a versioned migration because migrations
    run at Docker BUILD time against a throwaway layer and never reach the mounted
    prod volume — the same trap that left track_verifications absent in production.

    frame_number_raw  the value as originally stored. NULL means this row has never
                      been touched by the backfill. It is the undo, and it is also
                      what makes the backfill idempotent: the corrected value is
                      always recomputed from raw, never from the current column.
    frame_fps         the authoritative fps (cv2.CAP_PROP_FPS) used for the mapping.
    frame_correction  one of: corrected | identity | skipped_image | no_video |
                      no_fps. Never NULL once the row has been processed."""
    ...

def corrected_frame_number(raw: int, real_fps: float) -> int:
    """Map a browser-reported frame index onto the real one cv2 will seek to.

    The client stored round(currentTime * 30), so currentTime == raw / 30 and the
    true index is round(currentTime * real_fps). Single source of truth for this
    conversion — scripts/backfill_frame_numbers.py must not reimplement it."""
    ...

def save_annotation(video_id: str, frame_number: int, encounter_code: str, annotator: str, json_data: Dict, outbox_payload: Optional[str]=None, active_ms: Optional[int]=None) -> str:
    """Persist a frame annotation. If `outbox_payload` (a JSON string) is given,
    a durable Sheets/Drive sync task is written in the SAME transaction, so the
    sync intent can never be lost by an in-memory queue drop on worker recycle."""
    ...

def load_annotation(ann_id: str) -> Optional[Dict]:
    ...

def get_annotations_for_video(video_id: str) -> List[Dict]:
    ...

def upsert_user(email: str, name: str='', role: str='annotator'):
    ...

def get_user(email: str) -> Optional[Dict]:
    ...

def get_tutorial_states(email: str) -> Dict[str, bool]:
    """Return per-tour completion booleans for every name in TUTORIAL_NAMES."""
    ...

def mark_tutorial_complete(email: str, tutorial_name: str):
    """Mark a specific tutorial as completed."""
    ...

def mark_tutorial_seen(email: str):
    """Legacy wrapper — marks the overview tutorial as seen."""
    ...

def _progress_counts_from_blobs(conn, email: str) -> Tuple[int, int]:
    """Fallback for get_progress_counts: parse each annotation blob. Used until
    the n_scars/n_keypoints columns are backfilled (migrate_schema_v51), so the
    displayed numbers are correct even mid-deploy. Dedups to the latest row per
    (video_id, frame_number) — a no-op given the PK is unique per that triple,
    kept for parity with the historical behavior."""
    ...

def get_progress_counts(email: str) -> Dict:
    """Count scars and pose frames annotated by this user.

    Fast path aggregates the denormalized n_scars/n_keypoints columns (no blob
    parsing on this per-save / per-login hot path). Falls back to parsing the
    JSON blobs whenever any of the user's rows aren't backfilled yet, so the
    number is always correct. Returns {"scar_count": int, "pose_count": int}.
    """
    ...

def get_scar_count(email: str) -> int:
    """Legacy wrapper — returns combined count for backwards compatibility."""
    ...

def update_encounter_notes(encounter_id: str, notes: str, flag: Optional[str]=None):
    """Update admin notes, and the flag ONLY when one is explicitly supplied.

    ``flag=None`` leaves admin_flag untouched. This used to write both columns
    unconditionally, which was actively destructive: admin_flag holds the triage
    TIER imported by scripts (ROUTINE / DROP / POSE-GOLD / DOMAIN — 1,362 rows),
    but the dashboard's dropdown offered a completely different vocabulary
    ('review'/'mirrored'/'mislabeled'/'skip'). No real tier matched an option, so
    every encounter opened showing "No flag" and saving a note silently overwrote
    the tier with '' — losing the ranking signal that goal-weighted assignment
    reads, with no error and no undo.

    The guard lives here rather than in the client so no caller can repeat it.
    """
    ...

def list_flagged_encounters() -> List[Dict]:
    """Return all encounters that have an admin flag or notes."""
    ...

def list_users() -> List[Dict]:
    ...

def _experience_tier(count: int, is_expert: bool=False) -> float:
    """Map annotation count to experience weight using Colab's discrete 100-step tiers.
    0-100→0.1, 101-200→0.2, ..., 801-900→0.9, 901+→1.0, experts→1.5."""
    ...

def seed_annotator_weights(weights: dict=None, experts: set=None):
    """Seed proficiency weights from a provided dict (admin API or migration).

    Args:
        weights: {email: proficiency_weight} mapping. If None, no-op.
        experts: set of expert emails. If None, no experts set.
    """
    ...

def update_experience_weights():
    """Recompute experience_weight for every active user from `annotation_count`.

    ONE derivation, the same one `update_user_weights` uses when it un-flags an
    expert, and the same number the Proficiency tab prints beside the tier — so
    the tier and the count it is derived from can no longer contradict each
    other on screen. `annotation_count` is the whole history (the Forms tally the
    legacy import assigned, plus every in-app save since); it is safe to derive
    from now that `import_raw_scar_csv` writes its tally to
    `legacy_annotation_count` instead of overwriting this column.

    Iterates USERS, not the `annotations` GROUP BY: the old loop only ever
    touched people with in-app rows, so 24 of 33 users on the live catalog
    carried whatever the last import left, un-recomputed for months.

    experience_weight == 0.0 is a DELIBERATE exclusion from consensus and is left
    alone (tests/test_annotator_weights.py pins that 0.0 survives).
    """
    ...

def get_annotator_weights(email: str) -> Tuple[float, float]:
    """Return (experience_weight, proficiency_weight) for an annotator.

    NULL columns fall back to the schema defaults declared for them (0.1 / 0.5), so a
    legacy row predating those columns scores the same as a newly created user.

    `is not None`, never `or` — see _annotator_weight. A deliberate 0.0 must survive
    as 0.0; under the old `or` form, zeroing an annotator's weight to exclude them
    from consensus silently restored the default instead.
    """
    ...

def update_user_weights(email: str, proficiency_weight: float=None, is_expert: bool=None, set_baseline: bool=True):
    """Admin setter for annotator weights.

    `set_baseline=False` writes the derived weight WITHOUT moving `quiz_weight`. It
    exists for the computed feeders (`db_mlops.feed_proficiency_weight`), whose output
    is a blend OF the baseline: letting their result become the next baseline would
    rebuild exactly the recurrence `update_composite_proficiency` was fixed to remove.
    A human admin always moves the baseline, which is the default.
    """
    ...

def merge_duplicate_users():
    """Merge typo email records into canonical emails."""
    ...

def scar_consensus_thresholds() -> Dict[str, float]:
    """`scars.consensus` thresholds, defaults applied key by key.

    Read from config.yaml here rather than threaded down from app.py, because this
    module is also driven by scripts and tests that never build the Flask app.
    Production runs a MINIMAL config.yaml with no `scars:` section at all, so every
    lookup carries its own explicit default and an absent or malformed file
    degrades to `_SCAR_CONSENSUS_DEFAULTS` rather than raising inside a save.
    Cached: this is read once per scar per consensus recompute.
    """
    ...

def _coerce_bool(v) -> bool:
    """YAML already gives real booleans; this catches the quoted forms."""
    ...

def scar_location(side, zone, scar_type) -> Tuple[str, str, str]:
    """Where a scar is and what it is — everything about its identity EXCEPT
    colour. Normalised in one place so no caller invents its own casing."""
    ...

def color_is_identifying(colors_by_rater: Dict[str, set]) -> bool:
    """At ONE location, is colour naming separate scars or describing one?

    The old key answered "separate" always, so two raters who found the same
    mark and split on its colour did not disagree — they reported two scars.
    Measured over the 376 multi-rater encounters in this catalog, that
    manufactured 478 scars (13.0% of the corpus), 165 of them BLACK-vs-GREY
    alone, and left 134 location groups with no colour variant reaching
    `reliable` while their merged vote would have.

    Answering "one scar" always is equally wrong, and the repo already has the
    counterexample in its own tests: three annotators who EACH reported a WHITE
    and a BLACK scar in zone 6 are not disagreeing, they are three people
    independently saying there are two scars there.

    The discriminator is the rater, exactly as in `_merge_roi_boxes`'s
    same-annotator guard and Stream F's "one annotator can never corroborate
    themselves": nobody reports one scar twice in two colours, so a rater
    holding two colours at one location is asserting two scars. If ANY single
    rater does, colour identifies here. Otherwise the split is across raters —
    that is a disagreement about one mark, and it merges.

    Note this is deliberately not a vote: one rater seeing two scars is
    evidence the location holds two, even if everybody else found only one.
    Splitting keeps both, and each still has to earn its own agreement.
    """
    ...

def _merge_color_variants(signature_votes: Dict) -> Dict:
    """Collapse colour variants of one scar; leave genuinely distinct scars alone.

    In: {(side,zone,type,color) → [vote, ...]}.
    Out: the same shape, with merged groups re-keyed to a BLANK colour slot so a
    reader (and `compute_annotator_calibration`) can tell which locations were
    merged without re-deriving the decision.
    """
    ...

def compute_encounter_consensus(encounter_id: str) -> Optional[Dict]:
    """
    Count-based consensus for an encounter's scar annotations.

    Key improvements over previous version:
    - Deduplicates per-annotator across frames (keeps highest confidence)
    - Accounts for absence: annotators saying NO/UNKNOWN count against all scars
    - Count-based decisions: 3+ agree @ conf>=3 → CONFIRMED, 2 → PROBABLE, else UNCONFIRMED
    - Filters to primary scar per area + secondaries with >50% agreement
    - NEEDS_REVIEW for <3 total annotators
    - Annotator weights used as tiebreaker only, not in agreement ratio

    ⚠ THIS FUNCTION'S OUTPUT CHANGED, AND SOME ALREADY-PUBLISHED NUMBERS MOVE.
    Two rules were added, both of which can only ever LOWER a label:

      * a per-scar `disputed` state, for a scar most of the raters who answered
        say is not there. Measured, holding confidence at 5:

              saw it  said NO  raters  agreement  status BEFORE → AFTER  quality
                   3       17      20       0.15  confirmed → disputed   high → low
                   4       20      24      0.167  confirmed → disputed   high → low

        `reliable_scars` counts only `confirmed`, so both of those go 1 → 0. The
        vocabulary (confirmed / probable / disputed / unconfirmed) matches
        signal_consensus.py and scar_consensus.py rather than inventing a fifth
        word for the same idea.
      * `quality_label='high'` now also requires the mean agreement ratio to clear
        `scars.consensus.high_agreement_min` (default 0.5). The ratio was always
        computed and stored; the label simply never read it, so an encounter whose
        single scar 85% of the cohort denied published as HIGH — the strongest
        label in the vocabulary on the weakest evidence in the corpus.

    Encounters where the cohort actually agreed are unaffected: at agreement 1.0
    with no absence votes every branch takes the path it took before. Re-running
    "Refresh consensus" is what applies the new rules to existing rows; imported
    legacy rows are never recomputed at all (see `consensus_imports`).

    Returns None only if zero annotations exist.
    """
    ...

def compute_annotator_calibration(encounter_id: str, consensus_result: Dict) -> Dict[str, float]:
    """
    For each annotator who contributed to this encounter, compute what fraction
    of consensus scars they correctly identified.
    Returns {email: agreement_rate} where agreement_rate is 0.0-1.0.

    Only annotators who took part in the SCAR task are scored. The population is
    `consensus_result["all_annotators"]`, which compute_encounter_consensus builds
    from annotators who were actually asked about scars; scoring anyone else means
    writing an agreement rate for a task they were never shown.
    """
    ...

def update_composite_proficiency(calibration_by_encounter: Dict[str, Dict[str, float]]):
    """
    Update each annotator's proficiency_weight as a composite of:
    - Quiz score (users.quiz_weight, a stable baseline): 50%
    - Consensus agreement rate (rolling average across encounters): 50%
    - Expert override: always 1.0

    calibration_by_encounter: {encounter_id: {email: agreement_rate}}

    The quiz term is read from `quiz_weight`, NOT from `proficiency_weight`, which
    is this function's own OUTPUT. Reading the output back in made the update a
    recurrence, p(n+1) = 0.5*p(n) + 0.5*rate, so the documented "50% quiz" was
    worth 0.5^N after N clicks of an admin button that looks read-only. The live
    DB still shows the trace (0.5 -> 0.75 -> 0.875 -> 0.9375 at rate 1.0, with no
    new annotations in between). With a stored baseline the composite is
    idempotent: recomputing with the same inputs yields the same weight.
    """
    ...

def cache_consensus(encounter_id: str) -> Optional[Dict]:
    """Compute the IN-APP consensus and cache it. Returns the result.

    The row written here always describes the per-frame `annotations` cohort and
    is stamped `source='computed'` to say so. Any imported legacy-Forms row for
    the same encounter is copied into `consensus_imports` FIRST, so taking over
    the live slot can no longer destroy it — the measured failure was a 20-rater
    import at 0.91/'high' replaced by a 1-rater row at NULL/'needs_review' with no
    path back.
    """
    ...

def _unpack_consensus_row(row) -> Dict:
    """sqlite row → the dict shape callers have always received."""
    ...

def iter_all_consensus(include_imports: bool=True) -> List[Dict]:
    """Every cached consensus row, for the whole-corpus export.

    READ-ONLY and deliberately dumb: it never calls `compute_encounter_consensus`
    and never writes a cache row. `refresh_all_consensus` (the admin button and
    the hourly cron) is what makes these numbers current; an export that
    recomputed on the way out would hand an admin figures the encounter table
    beside it does not show, and would put an O(corpus) recompute on a download.

    `include_imports=False` drops the legacy Forms cohort. It is ON by default
    because that cohort is 1,485 of this catalog's rows and the only surviving
    record of what those raters agreed on — excluding it by default would make
    "all scars ever" mean "the handful annotated in-app".
    """
    ...

def get_cached_consensus(encounter_id: str) -> Optional[Dict]:
    """Consensus for an encounter, computing fresh if no row is cached.

    TWO POPULATIONS, AND THE ANSWER SAYS WHICH ONE IT IS.
    An encounter can carry both a legacy-Forms consensus (imported, never
    recomputable) and an in-app one (rebuilt from `annotations`). They are not
    versions of each other — different people, different instrument, different
    years — so the result names its `source` and, when the other population also
    exists, carries it alongside under `imported` / `computed`.

    The headline fields (consensus_score, quality_label, …) are whichever
    population has MORE raters, because the question being asked is "how well do
    we know this encounter's scars", and 20 legacy raters at 0.91 is a better
    answer than one student's first frame. Ties go to the computed row: it is the
    fresher instrument, and it is also what happens on every encounter with no
    import at all, so the tie rule is the no-import behaviour too.
    """
    ...

def refresh_all_consensus() -> Dict:
    """Batch recompute consensus for all encounters with annotations.
    Also downgrades any cached single-annotator entries from CSV imports.
    After recomputing, runs annotator calibration and updates composite proficiency."""
    ...

def import_consensus_csv(csv_path: str) -> Dict:
    """
    Import pre-computed consensus scores from the Colab notebook output CSV.
    CSV columns: Shark_encounter, Side, Area, Scar_type, Color, mean_conf,
                 agreement_percent, Scar_votes, scar_entries, ...
    Aggregates per encounter and stores in consensus_cache.
    """
    ...

def _norm_scar_type(raw) -> str:
    """Fold a Forms scar-type label to its enum name.

    Mirrors db_datasets.normalize_scar_type; duplicated deliberately because
    db_datasets imports THIS module, so importing it back would be circular.
    tests/test_legacy_reports.py asserts the two agree on every real value.
    """
    ...

def init_legacy_reports_table():
    """Per-annotator scar reports recovered from the raw Google Forms export.

    import_raw_scar_csv already parsed these rows -- {email, side, zone,
    scar_type, color, confidence} per submission -- and then THREW THEM AWAY,
    keeping only the aggregated consensus_cache row. That discard is why the
    system has "no multi-rater raw material": the live annotations table has 0
    encounters with scars from more than one person, while the CSV on disk has
    **397 encounters with 2+ raters** (up to 20), 5,291 scar rows among them,
    Sides_visible on 100% of 8,374 rows, and 359 explicit Scars_visible=No --
    the absence signal the live table has exactly zero of.

    Storing them makes the grading layer testable now rather than next semester.

    Both raw and normalised values are kept. The normalisation folds 55
    parenthesised scar types, 25 hyphenated zones and a pile of free-text colours
    (MOSTY WHITE, TAG PRESENT), and every one of those calls is a judgement a
    human may want to revisit -- so the original string travels with it.

    Created at import like the other init_* functions, NOT only in a migration:
    migrations run at Docker build time against a throwaway layer and never reach
    the mounted prod volume. That is what left track_verifications missing.
    """
    ...

def encounter_copepods(encounter_id: str) -> Dict:
    """What the raters who saw this whole encounter said about copepods.

    Copepods are a property of the ANIMAL, not of a frame. A parasite does not
    attach and detach between frame 176 and frame 196 — but the per-frame form
    recorded exactly that, twice, from the same person on the same clip. The
    question can only be answered by somebody who watched the encounter, and 33
    people already did: `legacy_scar_reports` carries one row per submission with
    that rater's answer.

    So this reads rather than asks. Returns, for each of body and wound:

      answer     YES | NO | DISPUTED | None      (None = nobody was asked)
      yes, no    how many raters said each
      raters     how many answered at all
      agreement  fraction holding the majority view (1.0 = unanimous), else None
      unanimous  True only when every rater who answered agreed

    A tie is DISPUTED, never silently resolved — with two raters split one-all
    there is no majority to report, and picking one would publish a finding the
    corpus does not contain. A non-unanimous majority IS reported, but `agreement`
    and `unanimous` travel with it so a caller can refuse it: 65 of the 1,369
    answered encounters have raters who genuinely disagree.

    Blank is not NO. 2,547 of the 8,374 submissions never answered, and "not asked"
    and "answered no" are different facts.
    """
    ...

def import_raw_scar_csv(csv_path: str, source_file: Optional[str]=None) -> Dict:
    """
    `source_file` is the identity the per-row votes are deduped on
    (UNIQUE(source_file, source_row) in legacy_scar_reports). It defaults to the
    file's name, which is right for a CSV somebody uploaded once and wrong for the
    Sheet sync, which streams the same sheet into a randomly named tempfile on
    every run — 8,374 rows appended per sync. The Sheet routes pass a stable
    identity ("sheet:<id>:<tab>") instead.

    Import raw scar annotation data from the Google Forms CSV to:
    1. Count per-annotator submissions → update experience_weight
    2. Create user records for all annotators
    3. Create encounter_priority entries for encounters not already tracked
    4. Populate encounter_completions with per-annotator completion status
    5. Compute consensus scores from scar details (type, zone, side, color, confidence)
    CSV columns: Email, Shark Encounter Code (LOCYYMMDDnn), Scar_type, Confidence,
                 Side, Area, Color, Notes, ...
    """
    ...

def get_active_semester() -> Optional[Dict]:
    """Return the currently active semester."""
    ...

def set_active_semester(semester_id: int):
    """Set a semester as active (deactivate all others)."""
    ...

def update_annotator_quota(email: str, quota: int):
    """Set per-annotator semester quota."""
    ...

def get_annotator_workload() -> List[Dict]:
    """
    Return each annotator's workload: assignment counts, quota progress.

    Quota progress = work COMPLETED inside the active semester. Three things this
    query gets right that the old 2N-queries-per-user version did not:
      * basis: `completed_at`, not `assigned_date` — work assigned in June and
        finished in September counts for the term it was finished in;
      * the window is half-open on `end_date + 'T24'`, because the old
        `completed_at <= '2026-12-31'` was a TEXT comparison and dropped the whole
        final day of every semester ('2026-12-31T09:00' > '2026-12-31');
      * `encounter_completions.annotator_name` holds CSV header text, so it is
        joined through `annotator_name_map` like every other consumer, instead of
        being compared to an email.
    Two counts ride along, LABELLED: `inapp_annotation_count` (rows in
    `annotations`, the population experience_weight is derived from) and
    `legacy_annotation_count` (the Forms tally). `annotation_count` stays for
    back-compat.
    """
    ...

def goal_rank_sql(goal: str) -> str:
    """SQL rank expression for a goal. Unknown goals fall back to balanced, so a
    typo in config degrades to today's behaviour instead of raising."""
    ...

def get_assignment_candidates(limit: int=20, site: str='', exclude_annotator: str='', goal: str=DEFAULT_GOAL, exclude_drop: bool=False) -> List[Dict]:
    """
    Return encounters ordered by annotation need.
    Factors in live annotation counts and active assignments so priority
    shifts dynamically as people work.

    Tier 0: no consensus / needs_analysis (most urgent)
    Tier 1: low consensus (<0.4)
    Tier 2: moderate consensus (0.4-0.7)
    Excludes high consensus and not_in_folder.

    `goal` (pose|scar|segmentation|balanced) breaks ties WITHIN a tier using the
    triage overlay in ep.admin_flag. See _GOAL_RANK_SQL.

    `exclude_drop` drops DROP-flagged encounters from the pool entirely. OFF by
    default and deliberately so: the goal rank already sorts DROP last, but
    priority_tier outranks it, so a tier-0 DROP is still served before tier-1
    work. Excluding fixes that — at the cost of trusting an automated heuristic
    to permanently withhold work. That heuristic is not yet proven (43 of 110
    POSE-GOLD encounters turned out to be close-up artifacts on first
    inspection), so this stays opt-in until DROP precision is measured against
    annotator feedback.
    """
    ...

def smart_batch_assign(annotator_email: str, batch_size: int=10, assigned_by: str='', site: str='', goal: str=DEFAULT_GOAL, exclude_drop: bool=False, with_stats: bool=False):
    """
    Auto-assign a batch of encounters to an annotator.
    Picks encounters they haven't already annotated, prioritized by need.
    `goal` biases selection within a consensus tier — see _GOAL_RANK_SQL.

    Returns the list of assigned rows; with `with_stats=True` returns
    `{"assigned": [...], "video_rows_created": N}` so a caller can SAY how many
    media-less `videos` rows this call minted instead of hiding them inside
    "Assigned N encounters".
    """
    ...

def recycle_stale_assignments(stale_days: int=30, dry_run: bool=True, annotator_email: str='', include_in_progress: bool=False) -> Dict:
    """Return long-untouched 'pending' assignments to the pool.

    WHY THIS MATTERS MORE THAN IT LOOKS: auto_replenish only fires when an
    annotator has fewer than `threshold` (5) pending items. Measured on this
    database, EVERY annotator sits at 5-47 pending, all assigned in March 2026.
    So auto_replenish has not fired for anyone in months and no new work — of
    any priority — can reach them. A queue that is never drained is also never
    refilled, which is the mechanism behind the ~11% student completion rate.

    Marks stale rows 'expired' rather than deleting them, so the assignment
    history survives. get_assignment_candidates counts 'expired' in its
    per-annotator exclusion, so a recycled encounter is not handed straight back
    to the person who let it lapse, but is immediately available to everyone
    else.

    Touches status='pending' by default. `include_in_progress` extends it to
    'in_progress' rows older than the cutoff — needed in practice, because
    recycling only 'pending' left 9 of 13 annotators still above the replenish
    threshold on stale in_progress work from March. An item opened five months
    ago is abandoned, not active, and nothing is lost by recycling it: saved
    annotations live in the `annotations` table, not in the assignment row.
    Kept opt-in so a genuinely active session is never yanked out from under
    someone mid-encounter.
    """
    ...

def auto_replenish(annotator_email: str, threshold: int=5, goal: str=DEFAULT_GOAL, exclude_drop: bool=False) -> List[Dict]:
    """Auto-assign more work if annotator's pending queue is below threshold.
    Returns list of newly assigned encounters (same format as smart_batch_assign).

    `goal` is threaded through because auto_replenish is the path MOST work
    actually arrives by (fired on an empty /api/videos and on every complete),
    so a goal applied only to admin smart-assign would miss the majority of
    assignments."""
    ...

def smart_assign_pose_frames(annotator_email: str, batch_size: int=15, assigned_by: str='') -> List[Dict]:
    """Assign a batch of unassigned pose frames to an annotator.

    Picks image frames not yet assigned to this annotator, stratified by
    site for diversity. Returns list of assigned frame dicts.
    """
    ...

def auto_replenish_pose(annotator_email: str, threshold: int=10) -> List[Dict]:
    """Auto-assign more pose frames if annotator's pending image queue is below threshold.

    Only counts image (pose frame) assignments, not video (scar) assignments.
    Returns list of newly assigned frames.
    """
    ...

def get_pose_frame_stats() -> Dict:
    """Return pool stats for pose frames: total, unassigned, per-annotator breakdown.

    ONE basis: `assignments`. The summary used to read `videos.status`, which only
    flips to 'completed' when EVERY assignment on the row completes and which
    recycle_stale_assignments never resets — a write-once flag, not a pool size.
    Measured: the summary said 12 completed while the per-annotator table under
    it, which reads assignments, summed to 275, and 32 recycled frames reported
    as assigned forever. `expired` is returned too; a fifth of the rows were
    invisible without it.
    """
    ...

def _parse_site(enc_id: str) -> str:
    ...

def _classify_cell(value: str) -> str:
    ...

def _is_dupe_row(cells: list) -> bool:
    ...

def import_priority_csv(csv_path: str) -> Tuple[int, int, List[str]]:
    """
    Import the Encounter ID Priority CSV.
    Returns (encounters_imported, duplicates_skipped, errors).

    Replacing the pool is intentional (this is a completion-MATRIX importer), but
    the ADMIN OVERLAY on each encounter is not the importer's to own. Four columns
    are human-entered and no CSV carries them:

        admin_flag       triage tier (ROUTINE / DROP / POSE-GOLD / DOMAIN) that
                         get_assignment_candidates ranks and filters on
        admin_notes      free text
        data_source      which importer created the row
        shark_catalog_id the adjudicated individual-shark link that becomes
                         dwc:organismID on publication

    They used to be dropped simply because the re-INSERT named seven columns, so a
    routine "Import from Sheet" silently reverted 1,362 triage tiers with an HTTP
    200 and no warning. They are now carried across the delete/re-insert, and any
    encounter that leaves the pool still holding one is reported to the caller.
    This is the same invariant update_encounter_notes already enforces.
    """
    ...

def _has_admin_overlay(row) -> bool:
    """True if an encounter_priority row carries human-entered state.

    `data_source` is excluded on purpose: it is set by importers, not by a human,
    so it is carried forward but its loss is not worth warning about.
    """
    ...

def list_encounters(site: str='', sort_by: str='completion_count', sort_dir: str='asc', offset: int=0, limit: int=50, search: str='', hide_not_in_folder: bool=False) -> Tuple[List[Dict], int]:
    """Paginated encounter priority list. Returns (rows, total_count)."""
    ...

def get_encounter_detail(encounter_id: str) -> Optional[Dict]:
    """Get full encounter detail including all annotator completions."""
    ...

def get_encounter_summary() -> Dict:
    """Aggregate stats for dashboard header cards."""
    ...

def get_annotator_name_map() -> List[Dict]:
    """Get all CSV name -> email mappings."""
    ...

def update_annotator_name_map(csv_name: str, user_email: str) -> bool:
    """Map a CSV annotator name to an app user email. Returns whether a row changed.

    An upsert, not a bare UPDATE: the old UPDATE could never CREATE a mapping (the
    modal offered no way in that a Priority CSV import had not already opened) and
    answered "ok" for an unknown csv_name having changed nothing.
    """
    ...

def link_encounter_to_video(encounter_id: str, video_id: str):
    """Link an encounter to a video record."""
    ...

def init_track_tables():
    """Create tracks / track_detections / track_verifications and bring their
    columns up to the current schema if they already exist.

    IMPORTANT — this init path must stay a SUPERSET of every column the track
    code writes or reads by name. In production the running app only calls the
    init_*_tables() functions against the persistent volume DB; the versioned
    migration chain (scripts/migrate_schema_v*.py) runs at Docker *build* time
    against a throwaway DB and never touches the volume. So anything a migration
    added (v4–v12) has to be re-applied here via the defensive ALTER loops
    below, or a fresh-volume deploy will crash on the first create_track() /
    verify / recompute call with "no such column" / "no such table".

    Mirrors the CREATE-IF-NOT-EXISTS + try/except ALTER idiom in
    init_encounter_tables().
    """
    ...

def init_track_provenance_columns():
    """Which proposer produced a track, and how sure it was (plan 13 §6.7).

    A dedicated column rather than reusing `signature_json`, which plan 13
    originally suggested: that field is the re-ID embedding payload parsed by
    segmentation/reid_match.parse_signature as {vec, model}, so writing proposer
    metadata into it would silently break re-ID matching for every auto track.

    proposer_json: {"proposer": str, "version": str, "score": float, ...} — the
    model's own confidence, kept separate from every human_* field. Without it a
    rejected track records only THAT a human said no, never what the model had
    claimed, which is exactly the pairing that makes a hard negative useful."""
    ...

def create_track(video_id: str, encounter_code: str, source: str, seed_frame_number: int, seed_annotator: str, seed_bbox: Dict, seed_source: str='human', proposer: Optional[Dict]=None, seed_scar: Optional[Dict]=None) -> int:
    """Insert a new track in 'proposed' status with propagation_status='pending'.

    seed_source: 'human' (current default) or 'auto' (Phase 5a — created by the
    candidate proposer worker, no human bbox click required).
    proposer: optional provenance for an auto track — {"proposer", "version",
    "score"}. Ignored for human seeds. Never merged into any human_* field.

    Returns the new track_id. Caller is responsible for kicking off propagation
    and calling update_track_propagation_result() when complete.
    """
    ...

def add_track_detection(track_id: int, frame_number: int, bbox: Dict, mask_rle: Optional[str], sam2_score: Optional[float]=None, sharpness_score: Optional[float]=None, area_score: Optional[float]=None, composite_score: Optional[float]=None, pose_json: Optional[str]=None) -> int:
    """Insert a single per-frame detection for a track.

    pose_json: optional Phase 2 pose hint payload (only populated for top-K frames).
    """
    ...

def update_track_propagation_result(track_id: int, best_frame_number: int, frame_count: int, confidence_aggregate: float, auto_color: Optional[str]=None, auto_color_confidence: Optional[float]=None, color_delta_l: Optional[float]=None, color_delta_a: Optional[float]=None, auto_zone: Optional[str]=None, auto_zone_confidence: Optional[float]=None, auto_side: Optional[str]=None, auto_side_confidence: Optional[float]=None, auto_on_fin: Optional[bool]=None, pose_status: Optional[str]=None, pose_model_version: Optional[str]=None):
    """Called when propagation finishes successfully — sets summary fields and status='done'.

    Phase 2 fields (auto_zone, auto_side, auto_on_fin, pose_status, pose_model_version)
    default to NULL/0 if pose was unavailable; the UI will then render no hint chip.
    """
    ...

def mark_track_auto_accepted(track_id: int) -> None:
    """Record that this track's human_* answers were COPIED from its auto_*
    ones by a one-click accept, not judged by a person.

    `get_hint_calibration` excludes these. Without the flag a one-click accept
    is indistinguishable from a human independently arriving at the model's
    answer, and every such row would count as a correct prediction -- so the
    more the accept button is used, the better the model would appear to be,
    which is precisely backwards.
    """
    ...

def update_track_propagation_error(track_id: int, error: str):
    """Called when propagation fails — records the error message."""
    ...

def requeue_track(track_id: int):
    """Polish 5 F1 — flip a failed track back to pending so the retry shows
    up correctly in the UI and queue endpoint. Clears propagation_error."""
    ...

def update_track_pose_fields(track_id: int, *, auto_zone: Optional[str]=None, auto_zone_confidence: Optional[float]=None, auto_side: Optional[str]=None, auto_side_confidence: Optional[float]=None, auto_on_fin: Optional[bool]=None, pose_status: Optional[str]=None, pose_model_version: Optional[str]=None):
    """Narrow writer for backfilling pose fields on existing tracks WITHOUT
    touching propagation_status, best_frame_number, frame_count, or
    confidence_aggregate (those were set by the original propagation run and
    re-running pose alone shouldn't disturb them).

    Used by scripts/backfill_pose_existing_tracks.py.
    """
    ...

def reject_track(track_id: int):
    """Soft-delete a track (preserves detections so we have negative-example data).

    Rejecting also releases a track that is still sitting at
    `propagation_status='pending'`. That row counts against its seeder's
    `max_concurrent_propagations` cap (`count_active_propagations` counts pending rows
    regardless of `deleted_at`), and the ONLY things that ever move a row off 'pending'
    are the in-memory queue worker finishing and the 30-minute stale reclaim. So a
    student whose propagation died with its worker — a redeploy, a `--max-requests`
    recycle, an OOM — saw the obvious self-heal, "reject the stuck track", leave them
    capped anyway, with no seeding possible until the reclaim window elapsed.

    It becomes 'error', not 'done': the propagation genuinely did not produce
    detections, and 'done' is the flag the training-data and eval pools select on
    (`db_mlops`, `get_tracks_for_training`). Only a 'pending' row is touched, so a track
    rejected after a successful propagation keeps its real history.
    """
    ...

def merge_track(track_id: int, into_track_id: int, merged_by: str) -> Dict:
    """Mark `track_id` as a duplicate of `into_track_id` (intra-video stitching).

    Soft-merge: the row stays in the DB for audit; queries that need "live"
    tracks filter `merged_into_track_id IS NULL`. Validation:
      - both tracks exist
      - both belong to the same video_id
      - neither has already been merged
      - track_id != into_track_id

    Returns the resulting `tracks` row or {"error": ...}.
    """
    ...

def update_track_signature(track_id: int, signature_json: Optional[str]):
    """Persist the embedding signature on a track. None is a valid value
    (means: extractor was a stub / wasn't called). Cheap write, no other
    fields touched."""
    ...

def set_track_gold(track_id: int, is_gold: bool) -> Dict:
    """Toggle the gold-standard flag on a track. Admin-only at the route layer."""
    ...

def record_track_verification(track_id: int, annotator: str, *, scar_type: Optional[str], human_zone: Optional[str], human_side: Optional[str], human_color: Optional[str], human_confidence: Optional[int], notes: str='', no_scar: bool=False):
    """Insert-or-replace one annotator's verification of a track.

    Composite key = (track_id, annotator). Re-verifying overwrites the prior
    row so an annotator can change their mind without inflating consensus.

    `no_scar=True` records "I looked at this track and there is no scar here".
    Until v44 there was no way to say it, so a rater who saw nothing was silently
    ABSENT from the tally rather than on the other side of it — see
    compute_track_consensus. The classification fields are forced NULL on an
    absence vote, because "there is no scar" and "the scar is a BITE on the flank"
    cannot both be this rater's answer, and a half-filled form left over from
    before they changed their mind would otherwise keep voting.

    Defaults to False, so every existing caller writes exactly the row it wrote
    before.
    """
    ...

def _annotator_weight(conn, email: str) -> float:
    """Look up combined experience × proficiency weight for an annotator.

    No user row (or no email) → 1.0, a neutral multiplier: someone absent from the
    roster should not be silently down-weighted.

    A row whose columns are NULL also falls back to 1.0. NOTE this is NOT the same
    fallback get_annotator_weights() uses for the encounter engine, which falls back
    to the schema defaults (0.1 / 0.5) — so a user with NULL columns is weighted 1.0
    here and 0.05 there. Unifying them changes scores rather than fixing a defect, so
    it is left as a deliberate decision rather than folded into a bug fix.

    `is not None`, never `or`. `0.0 or 1.0` is 1.0 in Python, so the `or` form turned
    a weight an admin had deliberately set to zero — the documented way to exclude an
    annotator, permitted by POST /api/admin/annotator-weights — into FULL weight, and
    made the max(0.0, ...) clamp below unreachable.
    """
    ...

def is_assigned_to(annotator_email: str, video_id: str) -> bool:
    """Does this annotator hold an assignment on this video, in any state?

    The permission basis for contributing a track verification once multi-rater
    review is on. Assignment is the existing model for "this person is trusted
    with this footage", so reusing it widens access to exactly that group rather
    than to anyone holding a login.

    Any status counts, `completed` included -- finishing the pass over a clip
    does not stop you being a legitimate second opinion on a scar found in it.
    """
    ...

def has_verified_track(track_id: int, annotator: str) -> bool:
    """Has this specific person already voted on this track?

    The one question blind review turns on: a rater who has voted may see the
    running consensus, a rater who has not must not.
    """
    ...

def compute_track_consensus(track_id: int, *, target_raters: int=1) -> Dict:
    """Weighted-mode aggregation of all per-annotator verifications for a track.

    Single-annotator case (current state pre-deploy): trivially returns that
    one annotator's values. Multi-annotator case: each annotator's vote is
    weighted by experience × proficiency × confidence/5; the highest-weight
    value wins per field, with ties broken by most-recent verified_at.

    Writes the consensus values back to `tracks.human_*` so existing readers
    (UI, exports, queue) see a single canonical answer. Returns the consensus
    dict.

    `target_raters` is the quota a track must reach before it counts as verified.
    At the default of 1 this is byte-identical to the previous behaviour. Above 1,
    a track BELOW quota keeps status='proposed' so it stays in the queue for the
    next rater -- previously the FIRST verification flipped it to 'verified' and
    removed it from everyone's queue permanently, which alone made a second
    opinion impossible.

    `status` is authoritative and `human_verified` is derived from it, rather than
    two independent flags for one fact that can disagree.

    ABSENCE IS A VOTE (v44). A rater who marked `no_scar` says the track shows no
    scar at all. Those rows contribute no value to any field — there is no zone for
    a scar that is not there — but they DO enter the denominator of every agreement
    figure, and when they outnumber the presence votes the track is not allowed to
    reach 'verified', however many people voted.

    Before this there was no absence row type at all and a null field was skipped
    (`if v in (None, ""): continue`), so a rater who looked and saw nothing could
    neither say so nor lower anybody's agreement. Measured: 1 rater said BITE, 2
    left every field null, and the track came back scar_type='BITE',
    status='verified', agreement 1.0 on all four axes.

    With no absence rows present — every deployment today, since nothing wrote them
    before v44 — every number below is byte-identical to the previous behaviour.
    """
    ...

def recompute_all_track_consensus(target_raters: int=1) -> int:
    """Recompute consensus for every track that has at least one verification.
    Useful after annotator weights change. Returns number recomputed.

    `target_raters` is NOT optional in practice. It used to be omitted here while
    every other call site passed the configured value, so this function — the one
    behind the admin "Recompute consensus" button — ran the whole corpus at a
    quota of 1 and flipped every below-quota track to status='verified'. One click
    closed every track that had a single vote, removed them all from the queue,
    and ended the second opinion the quota exists to collect. Measured: a track at
    1 of 3 votes went 'proposed' -> 'verified' and stopped being served.
    """
    ...

def init_catalog_dwc_columns():
    """Phase 1 (structure-now): give shark_catalog — which IS a dwc:Organism (one
    row per individual shark) — a stable Darwin Core identity: a permanent
    `organism_id` (dwc:organismID) plus `scientific_name` / `scientific_name_id`
    (the taxon, e.g. a WoRMS AphiaID URI). Additive; created at import like the
    other init_*_tables so every catalog entry gets a portable, rename-proof
    identifier BEFORE the catalog is seeded — no retrofit later.

    Deliberately NO georeference / eventDate here: those are per-occurrence, have
    no clean home in the current app tables, and there is no capture writing them
    — they belong to the DwC export projection when that work begins."""
    ...

def create_shark(display_name: str, notes: str='', scientific_name: str='', scientific_name_id: str='') -> Dict:
    """Insert a new shark catalog entry (a dwc:Organism). display_name must be
    unique; a stable organism_id (dwc:organismID) is minted automatically."""
    ...

def list_sharks() -> List[Dict]:
    """All catalog entries with encounter counts."""
    ...

def get_shark(shark_id: int) -> Optional[Dict]:
    ...

def update_shark(shark_id: int, *, display_name: Optional[str]=None, notes: Optional[str]=None, scientific_name: Optional[str]=None, scientific_name_id: Optional[str]=None) -> Dict:
    ...

def delete_shark(shark_id: int):
    """Delete a catalog entry. Does NOT cascade — encounters get their
    shark_catalog_id set to NULL."""
    ...

def get_hint_calibration(axes: Optional[List[str]]=None) -> Dict[str, Dict]:
    """How often has each auto_* suggestion matched the human's own answer?

    The loop this closes: the model proposes, the labeler accepts or corrects,
    and BOTH values are kept -- so every verification is a graded prediction.
    Nothing was reading that back, which meant a suggestion's own track record
    could not inform whether to keep showing it.

    Three rules, each load-bearing:

    * **One-click accepts are excluded.** `POST /api/tracks/<id>/verify` with
      `use_auto` COPIES auto_* into human_*, so counting those rows is the model
      grading its own homework -- they agree by construction and would drag any
      axis towards 100%. `auto_accepted` is why that is a WHERE clause and not a
      hope. Rows written before that column existed default to 0, which is the
      truthful claim for them: `use_auto` only ever arrived from the card grid.
    * **COPEPODS carries no colour**, so it is excluded from the colour axis
      only -- it still has a zone and a side worth scoring.
    * **`n` counts CHECKS, not tracks.** Below `min_n` a percentage is theatre;
      the caller decides the bar, this function only reports.

    Per-axis so the UI can withhold a suggestion that has stopped earning its
    place on ONE axis without silencing the others.
    """
    ...

def get_color_calibration() -> Dict:
    """Back-compat shim — the colour axis of `get_hint_calibration`.

    Kept because removing a name is not the same as removing a reader, and this
    one is reachable from an annotator-facing route.
    """
    ...

def get_auto_vs_human_metrics() -> Dict:
    """Polish 5 E1 — admin metrics: how often does the model's auto_* match
    the human_* ground truth?

    Returns:
      - zone_agreement_rate / side_agreement_rate / color_agreement_rate
        (overall, only on rows where BOTH auto_* and human_* are populated)
      - confusion matrices (auto → human counts) for zone, side, color
      - pose_status distribution across all verified tracks
      - per-scar-type counts (which classes are best represented)
      - per-scar-type avg human_confidence (where do annotators feel certain?)

    Excludes merged + soft-deleted tracks. COPEPODS rows are excluded from
    color metrics (no color label).
    """
    ...

def link_encounter_to_shark(encounter_id: str, shark_id: Optional[int]) -> Dict:
    """Attach (or detach with shark_id=None) an encounter to a catalog entry.
    Updates the catalog's first_seen / last_seen on attach.
    """
    ...

def get_track(track_id: int, include_detections: bool=True) -> Optional[Dict]:
    """Fetch a track row plus optionally all its detections."""
    ...

def get_tracks_for_video(video_id: str, include_rejected: bool=False, annotator_email: Optional[str]=None) -> List[Dict]:
    """List tracks for a video. If annotator_email given, only that annotator's tracks."""
    ...

def multi_rater_scope(annotator_email: Optional[str], target_raters: int=1) -> Tuple[str, List[Any]]:
    """The `WHERE` fragment that decides which tracks one person may be asked about.

    ONE definition, because there are two samplers over the same pool
    (`get_unverified_tracks` here and `db_mlops.sample_unverified_tracks`) and a
    queue that means different things depending on which one config selected is
    not a queue.

    `target_raters` is the only control. At 1 the queue serves only tracks this
    person seeded — byte-identical to what shipped for years, and the reason
    `track_verifications` had 0 rows: a labeler could only ever see their OWN
    seeds, so two people could not grade one scar even in principle.

    Above 1 it serves everyone's proposals EXCEPT this person's own seeds (you
    cannot corroborate your own proposal) and except the ones they have already
    answered, and retires a track once it has the votes it needs.

    There used to be a second switch, `tracks.multi_rater_verification`, from a
    branch that landed alongside this one. It set the serving rule without
    setting the quota, so the first vote drove the track to 'verified' and the
    second opinion the flag existed to enable could never be recorded. Measured,
    not reasoned: rater B saw the seed, voted, and rater C was served nothing. A
    quota and a serving rule are one decision; they cannot be two flags.
    """
    ...

def get_unverified_tracks(annotator_email: Optional[str]=None, video_id: Optional[str]=None, limit: int=50, strategy: str='most_uncertain', gold_inject_ratio: float=0.0, target_raters: int=1) -> List[Dict]:
    """List tracks waiting for verification.

    `target_raters` changes what `annotator_email` MEANS — see
    :func:`multi_rater_scope`, which owns that rule for both samplers.

    Strategy ('Polish 5 B1' active-learning sample mix):
      - 'most_uncertain' (default): sort ASC by summed auto-confidence.
        Cheapest active-learning signal; uses what's already in the DB.
      - 'diverse': pseudo-random spread (when track signatures are populated
        in a future revision, swap to embedding-based clustering — same API).
      - 'balanced': 50% uncertain + 30% diverse + 20% random, mixed.
        Mirrors the CVPR 2025 "Uncertainty Meets Diversity" hybrid.

    gold_inject_ratio (Polish 5 B2): 0.0 = no gold injection. >0 means
    injecting `floor(limit * ratio)` already-verified gold tracks (is_gold=1)
    into the result for blind inter-rater calibration. Gold tracks look
    indistinguishable from regular ones in the UI.

    Filters to status='proposed' (not verified, not rejected) and
    propagation_status='done' (we have detections + auto fields ready).
    Always excludes tracks merged into another (merged_into_track_id IS NULL).
    """
    ...

def _q_uncertain(base_sql: str, base_params: List[Any], n: int):
    ...

def _q_diverse(base_sql: str, base_params: List[Any], n: int):
    """Today: pseudo-random across the eligible set. When signature_json is
    populated by the (future) DINOv2 wrapper, swap this for k-means-style
    farthest-first sampling on the embedding. The function signature stays
    the same."""
    ...

def _q_random(base_sql: str, base_params: List[Any], n: int):
    ...

def _q_gold(annotator_email: Optional[str], video_id: Optional[str], n: int):
    """Already-verified tracks flagged as gold. Used as blind calibration."""
    ...

def _interleave_gold(regular, gold, cap: int):
    """Spread gold tracks evenly through the regular result up to cap items."""
    ...

def _row_to_track_dict(r) -> Dict:
    ...

def get_video_detections_grouped(video_id: str, annotator_email: Optional[str]=None) -> List[Dict]:
    """Polish 6 — every live track's full per-frame bbox map for canvas overlays.

    Single round trip + Python-side group-by. Excludes deleted, merged, and
    rejected tracks (canvas should never paint a ghost for something the user
    already said "no" to).

    Honors trim window: detections outside [trim_start_frame, trim_end_frame]
    (when set) are dropped, mirroring how downstream consumers (training export)
    treat trims.

    Returns: list of {track_id, status, scar_type, human_color, auto_color,
                       human_zone, seed_annotator, is_gold,
                       frames: {N: {x,y,width,height}}}
    """
    ...

def count_recent_propagations(annotator_email: str, hours: int=1) -> int:
    """Count tracks created by this annotator in the last N hours (for rate limiting)."""
    ...

def count_active_propagations(annotator_email: str) -> int:
    """Count tracks currently in propagation_status='pending' for this annotator."""
    ...
