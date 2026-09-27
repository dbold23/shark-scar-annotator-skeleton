"""Stream C (gamification) — annotator-facing engagement routes.

Phase C0 exposes ``GET /api/me/stats`` (quota progress, experience level, and —
optionally — existing quality signals). Phase C1 extends that payload with a
``calibration`` block (blind-gold Q-score feedback) and adds an admin batch
recompute endpoint. Phase C2 adds ``achievements`` / ``streak`` / ``impact``
blocks to the payload plus ``GET /api/me/achievements``. Phase C3 adds skill-aware
routing (``GET /api/me/next-task``, which drives Stream B's AL sampler by measured
skill) and an opt-in, non-zero-sum cooperative goal (``GET /api/team/goal``, an
opt-in toggle, and an admin goal-create). Phase C4 adds citizen-science hardening
behind the ``gamification.profile: lab|public`` seam: a per-user trust view
(``GET /api/me/trust``), a Q-score-gated + redundancy-checked consensus view
(``GET /api/gamification/track/<id>/consensus``), an admin gating summary, and
admin moderation hooks. C4 adds ONLY new routes — ``get_user_stats`` is untouched,
so the default ``lab`` ``/api/me/stats`` payload is byte-identical. No existing
routes are touched; no consensus logic changes (the canonical
``database.compute_track_consensus`` is never edited; the gated view is read-only).

``create_blueprint()`` takes the ``require_login`` / ``require_admin`` decorators
as arguments rather than importing them from ``app``: under ``python app.py`` the
app module is ``__main__``, so a top-level ``from app import require_login`` would
re-execute app.py. Passing them in is robust in both dev (``python app.py``) and
prod (``gunicorn app:app``). If a decorator is somehow missing the routes FAIL
CLOSED (503) rather than serving unauthenticated.
"""
from __future__ import annotations
from functools import wraps
from flask import Blueprint, jsonify, request
from annotation.db_gamification import get_user_stats, recompute_all_qscores, build_signals, evaluate_achievements, get_next_task, get_team_goal_payload, set_coop_opt_in, create_team_goal, resolve_profile, get_trust_payload, aggregate_gated_consensus, gating_summary, set_moderation, list_moderation

def _fail_closed(message: str):
    """A decorator that refuses every request — used when an auth decorator was
    not supplied, so a wiring mistake can never expose a route unauthenticated."""
    ...

def _has_verified(track_id: int, email: str) -> bool:
    """True if this annotator has already submitted their own verification of the
    track — the precondition for showing them anyone else's answer."""
    ...

def create_blueprint(gam_cfg=None, require_login=None, require_admin=None):
    ...
