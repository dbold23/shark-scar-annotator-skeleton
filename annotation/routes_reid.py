"""Stream A (re-ID) — Flask blueprint: morphometrics capture + admin ops.

Per plans/00-SHARED-CONTEXT.md §3.1/§3.5 this is a per-stream blueprint module. app.py only
gains a single `_register_reid()` call; everything else lives here. Registered ONLY when
`reid.enabled` is true (default OFF), so a partial stream can never affect prod.

Provides:
  - A post-save capture hook (`after_app_request`) that persists morphometrics for each
    successful `POST /api/annotations`, without editing the save route or database.py.
  - Admin routes (all require_admin) to backfill morphometrics, inspect them, and run the
    multi-view re-ID crop exporter — each long job uses the shared status-dict+lock pattern.
"""
from __future__ import annotations
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, jsonify, request
from annotation import database as db
from annotation import db_reid

def _DbJob(job_id: str, kind: str=_JOB_KIND) -> 'db.DbJob':
    """The name this module's jobs are constructed under on the audit branch.

    A thin alias over database.DbJob rather than a second implementation: two
    classes backing the same `jobs` rows is how they drift.
    """
    ...

def capture_morphometrics_from_save(body: dict, email: str) -> int:
    """Persist morphometrics for one just-saved annotation. Returns measures written.

    `email` MUST be the authenticated user's email — `database.save_annotation` keys the
    annotation id as f"{video_id}_{frame_number}_{email}", so we reconstruct it identically.
    Pure enough to unit-test directly (no Flask request needed).
    """
    ...

def create_blueprint(rcfg: dict | None=None, require_login=None, require_admin=None):
    """Build the reid blueprints. `rcfg` is the `reid:` config section.

    Returns ``(bp, perm_bp)`` — the admin blueprint and the annotator-facing
    permanence blueprint. The caller registers BOTH; this function must never
    reach into the app module to register one itself (see below).

    The decorators are passed in rather than imported from ``app`` — the same
    convention routes_gamification.py documents. Under ``python app.py`` the
    running module is ``__main__``, so ``import app`` does not find it in
    sys.modules and executes app.py a SECOND time, building a second Flask app.
    That is how the permanence routes went missing in dev: they were registered
    on the shadow app while the original served traffic, and the re-entry then
    failed with "name 'reid_permanence' is already registered" — logged as
    non-fatal, so the route 404'd with nothing obviously broken. Gunicorn
    imports ``app:app``, so prod was unaffected and the gap only ever appeared
    locally.
    """
    ...
