"""Stream B (MLOps) — additive blueprint at ``/api/mlops/*``.

Config-gated, append-only routes that never touch core routes or ``database.py``.
Registered unconditionally by ``app._register_mlops()`` (harmless when the mlops
flags are OFF — every route checks its own ``mlops.*`` flag and degrades to an
inert response). Decorators are passed in (not imported) so this works under both
``python app.py`` and ``gunicorn app:app``.

Routes:
  GET  /api/mlops/tracks/<id>/type-suggestion   model scar-type hint for verify (B / #9)
  GET  /api/mlops/next-task                      fed AL-ranked next item (B / #1)
  GET  /api/mlops/agreement?spec_id=N            my overlap comparisons, peers redacted
  GET  /api/admin/mlops/specs/<id>/agreement     stored overlap comparisons (admin, named)
  POST /api/admin/mlops/specs/<id>/agreement/refresh  recompute + store them (admin)
  GET  /api/admin/mlops/specs/<id>/overlap       how much overlap is actually finished
  GET  /api/admin/mlops/status|runs|models       orchestrator inspection (admin)
  GET  /api/admin/mlops/golden                   frozen eval sets + why each is that size
  POST /api/admin/mlops/trigger|.../promote|rollback   orchestrator control (admin)
  GET  /api/admin/mlops/drift                    drift & degradation status (B4, admin)
  POST /api/admin/mlops/drift/check|.../baseline  run a monitor pass / re-baseline (admin)

Cross-stream routing-hook contract (consumed by Stream C gamification, and A):
  * Fed task routing — ``GET /api/mlops/next-task`` returns
    ``{next, upcoming, remaining, reason, strategy}`` for the calling annotator
    (non-admins are scoped to their own pool). C surfaces "your next task" +
    remaining; the ``reason`` is the why-this-item AL rationale.
  * Expert routing (server-side) — ``db_mlops.sample_unverified_tracks(
    annotator_email=<target>, strategy='most_uncertain', limit=N)`` returns the
    most-valuable items to route to a specific (e.g. expert) annotator. The HTTP
    surface above is the per-user view; call db_mlops directly for batch routing.
  * Per-annotator quality / per-example trust (B1, for C's skill/feedback +
    "re-check this" tasks) — ``db_mlops.get_annotator_quality()`` and
    ``db_mlops.get_track_label_quality(track_id)`` / ``low_trust_track_ids()``.
  These are read-only contracts; C/A consume them, neither rewrites B's logic.
"""
import json
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_file

def _thumb_root() -> Path:
    """Where card thumbnails live: beside the track previews, under data/ — same
    lifecycle, same .gitignore. Module-level so the annotator route that READS the
    cache and the admin route that SEEDS it cannot drift apart."""
    ...

def create_blueprint(cfg, require_login, require_admin, resolve_media=None, warm_media=None):
    """``resolve_media(video_row) -> Optional[Path]`` resolves a video row to a file
    that is ALREADY on this box. Passed in rather than imported because the path
    whitelist (``safe_video_path``) lives in app.py with ROOT and the config; and
    it is optional so the blueprint still builds standalone in tests — the one
    route that needs it then reports the capability as unavailable instead of
    guessing at a path.

    ``warm_media(items)`` is told what was just leased so the server can decode it
    ahead of the labeler. Optional and fire-and-forget: everything it warms is
    fetched normally on demand anyway."""
    ...

def create_admin_blueprint(cfg, require_login, require_admin):
    """B3 admin control surface at /api/admin/mlops/*. Read panels work regardless
    of the orchestrator flag (inspect anytime); trigger/promote/rollback are
    deliberate admin actions. Training NEVER runs in a request — trigger only
    QUEUES a run that the cron orchestrator (--process-requested) executes."""
    ...
