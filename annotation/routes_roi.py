"""Stream D (annotator UX & tracks UI) — Flask blueprint: ROI marks + additive track edits.

Per plans/00-SHARED-CONTEXT.md §3.1 this is a per-stream blueprint module. app.py only gains a
single `_register_roi()` call; everything else lives here. Registered ONLY when `roi.enabled`
is true (default OFF), so when disabled the routes simply do not exist (404) and the annotator
UI is byte-identical to today — the frontend gates on `GET /api/roi/health`.

D1 (this commit) provides the ROI-mark surface:
  - GET    /api/roi/health        — availability + crop-capture knobs (frontend gate)
  - POST   /api/roi               — create one ROI mark (box only; no scar form, no propagation)
  - GET    /api/roi?video_id=...  — live ROI marks for a video (overlay + list)
  - DELETE /api/roi/<id>          — soft-delete an ROI mark (owner only)

Additive track-edit endpoints (D2 POST /api/tracks/<id>/bbox, D3 permanence) are added in their
own commits without ever editing the core PATCH /api/tracks/<id> route or database.py.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from annotation import db_roi
_DEFAULT_MAX_CROP_KB = 512

def create_blueprint(rcfg: dict | None=None, require_login=None):
    """Build the ROI blueprint. `rcfg` is the `roi:` config section."""
    ...
