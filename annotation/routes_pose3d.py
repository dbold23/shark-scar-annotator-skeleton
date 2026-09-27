"""Stream H — Flask blueprint for 3D lift & volumetrics annotation.

Per `plans/00-SHARED-CONTEXT.md` §3.1 this is a per-stream blueprint module: `app.py`
gains a single `_register_pose3d()` call and nothing else. Registered ONLY when
`pose3d.enabled` is true (**default OFF**), so with the flag off these routes do not
exist (404) and the annotator UI is byte-identical to today — the frontend gates on
`GET /api/pose3d/health`, the same contract `tracks`, `roi` and `signals` use.

    GET    /api/pose3d/health                     availability + UI vocabularies (no auth)
    GET    /api/pose3d/queue                      frames still needing a silhouette
    GET    /api/pose3d/frame                      one frame's mask + segments + scale
    GET    /api/pose3d/masks                      list (own by default)
    POST   /api/pose3d/masks                      create or replace own silhouette
    DELETE /api/pose3d/masks/<id>                 soft-delete own (admins may correct)
    GET    /api/pose3d/segments                   list
    POST   /api/pose3d/segments                   create a scale_ref | axis | chord
    DELETE /api/pose3d/segments/<id>              soft-delete own (admins may correct)
    GET    /api/pose3d/export/<fmt>               coco | sidecar | csv | json
    GET    /api/pose3d/agreement                  one frame's inter-annotator agreement
    GET    /api/pose3d/agreement/summary          roll-up + per-annotator scorecards
    GET    /api/pose3d/stats                      corpus coverage                  [admin]

Default read scope is **own work**. This is a measurement task, and a labeler who can see
where a peer put the waterline will put theirs there too — the anchoring that a
multi-rater design exists to measure, not to induce. Same reasoning as Stream F's
`redact_for()`; for the CRUD routes it is simpler because scoping the query is enough.

The two agreement routes are the exception, and they need two guards rather than one:

  * a non-admin may only read a group they are IN, and only once their own row exists.
    Before that, "the other two called this dorsal" is a hint about a frame they have not
    drawn yet. After it, their answer is already committed and cannot be moved.
  * even then the result is passed through `db_pose3d.redact_agreement_for`, which
    removes peer names, the per-annotator view map, the named pair table and peer
    scorecards. It never has to remove geometry, because `frame_agreement` returns none.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, Optional
from flask import Blueprint, Response, jsonify, request
from annotation import db_pose3d as dbp
from annotation import pose3d_exports as exports

def _err(msg: str, code: int=400):
    ...

def create_blueprint(pcfg: Optional[dict], require_login, require_admin):
    """Build the pose3d blueprint. ``pcfg`` is the ``pose3d:`` config section.

    ``require_login``/``require_admin`` are passed in rather than imported so this works
    under both ``python app.py`` (module ``__main__``) and ``gunicorn app:app``.
    """
    ...
