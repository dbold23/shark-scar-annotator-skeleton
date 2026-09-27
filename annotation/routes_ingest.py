"""Stream G HTTP surface: staged field-trip ingest.

Registered by `app.py` only when `ingest.enabled` is true (default OFF), so with the
flag absent — which is how production's minimal `config.yaml` ships — these routes do
not exist and the app is byte-identical to today. The frontend gates on
`GET /api/ingest/health`, the same contract `tracks`, `roi` and `signals` use.

    GET    /api/ingest/health                      availability + UI knobs (no auth)
    GET    /api/ingest/trips                       every field day, most recent first
    GET    /api/ingest/trips/<trip_key>            one day: encounters in order + gaps
    POST   /api/ingest/batches                     start a drop                 (admin)
    GET    /api/ingest/batches                     recent drops                 (admin)
    POST   /api/ingest/batches/<id>/manifest       stage what the browser read  (admin)
    GET    /api/ingest/batches/<id>/items          review the staged drop       (admin)
    PATCH  /api/ingest/items/<id>/code             name a parked clip           (admin)
    POST   /api/ingest/items/<id>/commit           move it into the catalog     (admin)
    POST   /api/ingest/proposals/<id>/decide       accept/reject/correct        (admin)

**No video bytes traverse this blueprint.** nginx caps bodies at 50MB, Flask at 50MB and
Cloudflare at roughly 100MB, while a GoPro card clip is 1-4GB — so the browser reads each
file's name, size and header locally and posts a small JSON manifest. The media itself
reaches Drive by the lab's existing route, and the catalog stores only a `drive_id`.
"""
from __future__ import annotations
import logging
from typing import Optional
from flask import Blueprint, jsonify, request
MAX_MANIFEST_ENTRIES = 5000

def create_blueprint(icfg: Optional[dict], require_login, require_admin):
    """Build the ingest blueprint. `icfg` is the `ingest:` config section.

    `require_login`/`require_admin` are passed in rather than imported so this works
    under both `python app.py` (module `__main__`) and `gunicorn app:app` — the same
    reason `routes_signals` and `routes_gamification` take them as arguments.
    """
    ...
