"""Stream F — Flask blueprint for signal annotation (waterfall + biologging).

Per `plans/00-SHARED-CONTEXT.md` §3.1 this is a per-stream blueprint module: `app.py`
gains a single `_register_signals()` call and nothing else. Registered ONLY when
`signals.enabled` is true (default OFF), so with the flag off these routes do not exist
(404) and the annotator UI is byte-identical to today — the frontend gates on
`GET /api/signals/health`, the same contract `roi` and `tracks` use.

Route map (F0):

    GET    /api/signals/health                          availability + UI knobs (no auth)
    GET    /api/signals/vocabularies                    label registries + terms
    GET    /api/signals/deployments                     assigned (annotator) or all (admin)
    POST   /api/signals/deployments                     create                      [admin]
    GET    /api/signals/deployments/<id>                full manifest for the workspace
    POST   /api/signals/deployments/<id>/sources        attach + probe a file       [admin]
    POST   /api/signals/deployments/<id>/assign         assign to an annotator      [admin]
    GET    /api/signals/deployments/<id>/labels         labels (optionally windowed)
    POST   /api/signals/deployments/<id>/labels         create a label
    PATCH  /api/signals/labels/<id>                     edit own label
    DELETE /api/signals/labels/<id>                     soft-delete own label
    PATCH  /api/signals/sources/<id>/offset             re-align a source          [admin]
    GET    /api/signals/sources/<id>/tiles/<n>.png      one waterfall tile
    GET    /api/signals/deployments/<id>/export/<fmt>   raven | boris | rf | json

and (F3):

    GET    /api/signals/deployments/<id>/consensus          stored run (?compute=1 previews)
    POST   /api/signals/deployments/<id>/consensus/refresh  recompute + store        [admin]
    GET    /api/signals/deployments/<id>/scorecard          own row; all rows        [admin]
    POST   /api/signals/labels/<id>/gold                    mark a calibration item  [admin]

The manifest returned by `GET /deployments/<id>` carries each waterfall source's frozen
lattice, so the **browser** converts pixels to (time, frequency) itself and posts real
seconds and hertz. The server therefore never has to reverse-engineer a pixel, and a
client with a stale cached tile still writes coordinates in physical units.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from flask import Blueprint, Response, jsonify, request
from annotation import db_signals as dbs
from annotation import signal_consensus as scons
from annotation import signal_exports as exports
_TILE_MAX_AGE = 86400

def _err(msg: str, code: int=400):
    ...

def create_blueprint(scfg: Optional[dict], require_login, require_admin):
    """Build the signals blueprint. ``scfg`` is the ``signals:`` config section.

    ``require_login``/``require_admin`` are passed in rather than imported so this works
    under both ``python app.py`` (module ``__main__``) and ``gunicorn app:app`` — the same
    reason `routes_gamification` and `routes_mlops` take them as arguments.
    """
    ...

def seed_vocabularies(scfg: Optional[dict]) -> int:
    """Upsert the vocabularies declared under ``signals.vocabularies`` in config.

    Runs at registration so a config edit reaches the labelers on the next restart with
    no migration. Returns how many vocabularies were ensured.
    """
    ...
