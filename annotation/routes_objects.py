"""Scar objects — Flask blueprint. The encounter pass and the scar board.

Per plans/00-SHARED-CONTEXT.md §3.1 this is a per-stream blueprint module; app.py
gains a single `_register_objects()` call. Registered ONLY when `objects.enabled`
is true (default OFF), so when disabled these routes do not exist (404) and the
annotator UI is byte-identical to today. The frontend gates on
`GET /api/objects/health` — never on something unconditionally true, which is the
`bbox_tracker.is_available()` mistake that hid the scar form from every student.

    GET    /api/objects/health                      availability (frontend gate)
    GET    /api/objects/encounters/<enc>/clips      every clip of the encounter
    POST   /api/objects/passes                      open/resume a sighting
    GET    /api/objects/passes/<enc>                the sighting + its clips
    PATCH  /api/objects/passes/<id>/clips/<vid>     record sides_visible + usable
    POST   /api/objects/passes/<id>/close           finish (refuses if clips unseen)
    GET    /api/objects/scars?encounter_id=...      the scar board
    POST   /api/objects/scars                       create one scar object
    POST   /api/objects/tracks/<tid>/attach         this clip's track IS that scar

Deliberately NOT here: propagation and verification. `POST /api/tracks/propagate`
and `POST /api/tracks/<id>/verify` are reused verbatim, so drawing a scar once
still produces a track exactly as it does today — this layer only adds the parent
that survives the clip boundary. No new CV code.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from annotation import db_objects

def create_blueprint(ocfg: dict | None=None, require_login=None):
    ...
