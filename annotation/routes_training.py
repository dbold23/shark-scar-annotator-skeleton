"""Training set — ``/api/training/*`` (labeler) and ``/api/admin/training/*`` (admin).

The lab has a handful of encounters the experts have already answered (the KEY) and a
Google-Forms "Training Survey" every new labeler fills in on those same encounters.
This blueprint is the door for both: import the key, import the survey, mark every
rater against the key, and — as a separate, explicit step — copy a rater's score onto
their ``proficiency_weight``. It also hands the training clips to the fed queue so a
cohort can do them inside the app instead of on a form.

Rules:

* **Gated in app.py on ``training.enabled`` (default OFF).** With the section absent
  — which is how production's minimal config ships — nothing here is registered and
  every route 404s.
* **A labeler sees their own headline numbers and nothing else.** ``/api/training/me``
  goes through ``training_scoring.redact_for_labeler``: no per-encounter detail, no
  key content, no peer. The key is the answer sheet; a per-encounter miss list IS the
  answer sheet with one indirection.
* **Scoring and applying are two routes.** ``POST /score`` writes ``training_scores``
  and returns; ``POST /apply`` is the only thing that touches ``users``, and it takes
  a floor on how many encounters a number must rest on.
* **The Sheets service is injected**, never built here, so the blueprint mounts on a
  bare Flask app in tests and the app decides whose credentials read the sheet.
* **Unknown vocabulary is dropped and RETURNED**, never coerced. "6 _FLANK" folds to
  zone 6; a cell nothing recognises comes back to the admin as a dropped row with its
  reason, because a silently-skipped expert row is a hole in the key nobody sees.
"""
from __future__ import annotations
import hashlib
import json
import logging
import re
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Sequence
from flask import Blueprint, jsonify, request
from annotation.identity import norm_annotator

def _fold(cell: Any) -> str:
    ...

def header_map(header: Sequence[Any]) -> Dict[str, int]:
    """Column index per internal field, from a sheet's header row."""
    ...

def rows_from_values(values: Sequence[Sequence[Any]]) -> List[Dict[str, Any]]:
    """Sheet ``values`` (header first) → dicts keyed by internal field, with the
    1-based sheet row number in ``source_row`` so a re-import is idempotent."""
    ...

def row_from_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """A body row in either the sheet's column names or the internal ones."""
    ...

def normalise_rows(raw_rows: Sequence[Dict[str, Any]], *, need_annotator: bool=False, min_confidence: Optional[int]=None):
    """Fold vocabulary; split into (kept, dropped). Dropped rows carry a reason."""
    ...

def create_blueprint(cfg, require_login, require_admin, *, sheets_service_factory: Optional[Callable[[], Any]]=None, resolve_candidates: Optional[Callable[..., List[Dict]]]=None):
    """Build the training blueprint.

    ``sheets_service_factory()`` returns a googleapiclient Sheets service (or None
    when the caller has no Google credentials); ``resolve_candidates(codes, frames)``
    overrides how training clips become queue candidates (tests, or a caller with
    its own media index).
    """
    ...
