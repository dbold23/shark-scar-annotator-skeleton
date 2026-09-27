"""Mission suggestions — Flask blueprints.

Registered ONLY when ``gamification.cooperative.suggestions.enabled`` is true
(default OFF by absence, per plans/12), so with it off these routes 404 and the
annotator UI is byte-identical. The frontend gates on ``GET /api/missions/health``
rather than on config, the same contract as ``/api/tracks/health``.

Two blueprints, because they are two audiences with two different risks: the
labeler surface is a WRITE route open to every signed-in student and is rate
limited, capped and own-scoped; the admin surface answers.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from annotation import db_datasets, db_gamification, db_missions
_DEFAULT_MAX_OPEN = 3

def _cfg(cfg: dict | None) -> dict:
    ...

def _email() -> str:
    ...

def create_blueprint(cfg: dict | None=None, require_login=None, rate_limit=None):
    """The labeler surface. `rate_limit` is app.py's limiter decorator factory."""
    ...

def create_admin_blueprint(cfg: dict | None=None, require_admin=None):
    """The lab-lead surface: read what is waiting, and answer it."""
    ...
