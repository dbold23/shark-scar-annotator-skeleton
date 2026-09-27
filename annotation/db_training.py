"""Training set storage — the expert answer key, the survey rows, and each rater's score.

Three things live here and nothing else: WHICH encounters make up the lab's training
set, WHAT the experts said is on each of them (the key), and WHAT each labeler said
(survey rows imported from the Google-Forms "Training Survey", plus rows the app
itself has collected on the same encounters). The arithmetic — normalising the
vocabulary, deduping a rater's rows into signatures, and marking one rater against the
key — lives in ``annotation/training_scoring.py``, which is pure (no sqlite3, no
Flask) and is the only thing here that knows what a Signature is.

Rules this module keeps:

* **Every connection is ``database.get_conn()``.** It is what turns
  ``PRAGMA foreign_keys`` on; a second connection factory would re-open that hole.
* **One human, one rater.** ``annotator`` is folded through
  ``identity.norm_annotator`` at the door, so a survey row typed with a capital
  letter and an app row from the JWT are the same person.
* **Scoring never touches ``users``.** ``compute_all_scores`` writes
  ``training_scores`` and returns; ``apply_scores`` is the ONLY path that calls
  ``database.update_user_weights``, so recomputing a score can never change anybody's
  weight as a side effect. An admin decides to apply, explicitly, with a floor on how
  many encounters the number rests on.
* **"Known no-scar" survives import.** An encounter the expert looked at and marked
  as carrying nothing is stored as a key row with ``scar_type = ''``; without that
  row the encounter would be indistinguishable from one the key never covered, and a
  rater who correctly reported nothing could not be credited for it.
* **Tables are created by ``init_training_tables()`` at the entry points**, not by a
  migration only — migrations do not run in production (see CLAUDE.md).
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from annotation import database as _db
from annotation.database import get_conn
from annotation.identity import norm_annotator

def init_training_tables() -> None:
    """Idempotent CREATE TABLE IF NOT EXISTS, memoised per process per DB path."""
    ...

def _now() -> str:
    ...

def _ts():
    """The pure scoring module, imported at call time.

    Late so the storage layer imports even where the algorithm module is not yet
    present, and so a test can substitute it through ``sys.modules``.
    """
    ...

def _s(v: Any) -> str:
    ...

def _enc(v: Any) -> str:
    """An encounter code as the catalog spells it (``training_scoring.norm_encounter``:
    stripped, upper-cased). Every code that enters storage goes through this so a
    hand-typed ``apt22062203`` and the video's ``APT22062203`` are one encounter."""
    ...

def set_training_encounters(codes: Iterable[str]) -> Dict[str, Any]:
    """Make ``codes`` THE training set. Replaces, never appends.

    Returns ``{"n": <size>, "added": [...], "removed": [...]}`` so the admin can see
    what a re-import changed.
    """
    ...

def training_encounters() -> List[str]:
    ...

def _is_absence_marker(row: Dict[str, Any]) -> bool:
    """A "there is nothing on this encounter" row: no type, and the rater said No."""
    ...

def replace_key(rows: Iterable[Dict[str, Any]], source: str='') -> Dict[str, Any]:
    """Replace the whole answer key in one transaction.

    ``rows`` are already normalised (``training_scoring.norm_*``): each carries
    ``encounter_id, side, zone, scar_type, color`` and optionally ``scars_visible``
    and ``notes``. An encounter whose only row is an absence marker (``scar_type ''``
    and ``scars_visible 'No'``) is stored as ONE row with ``scar_type ''`` — that is
    how "known no-scar" survives, and it is what lets a rater be credited for
    reporting nothing there.

    A row with no type that is not an absence marker says nothing and is dropped;
    a scar row missing its side or zone cannot be matched and is dropped too. Both
    are counted back to the caller rather than silently swallowed.
    """
    ...

def key_rows() -> List[Dict[str, Any]]:
    ...

def key_by_encounter() -> Dict[str, List[Signature]]:
    """The key in the shape ``training_scoring.score_rater`` takes.

    An encounter listed with an empty list is "known no-scar".
    """
    ...

def key_colors_by_encounter() -> Dict[str, Dict[Signature, str]]:
    """The expert's colours, keyed like ``key_by_encounter`` — kept out of the key
    itself (colour is not identity) and fed to ``score_rater`` for ``color_agreement``."""
    ...

def key_version() -> str:
    """Short content hash of the key, so a stored score says which key it was marked
    against. Colour is included: it changes ``color_agreement`` even though it is not
    part of identity."""
    ...

def _norm_report(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fold one raw survey row into the stored shape, or None if it names nobody."""
    ...

def import_reports(rows: Iterable[Dict[str, Any]], source: str) -> Dict[str, Any]:
    """Store survey rows. ``INSERT OR IGNORE`` on ``(source, source_row)`` so a sheet
    re-imported twice adds nothing; a row without a ``source_row`` takes its position
    in the batch."""
    ...

def report_rows() -> List[Dict[str, Any]]:
    ...

def count_reports() -> int:
    ...

def reports_from_annotations(encounter_ids: Sequence[str]) -> List[Dict[str, Any]]:
    """Rows shaped like ``training_reports`` from what the app itself has collected.

    Joins ``annotations`` to ``videos`` on ``video_id`` and takes the encounter code
    from the VIDEO (falling back to the annotation's own column) — the blob's copy
    disagrees on real rows. Mirrors how ``compute_encounter_consensus`` reads a scar
    dict: a scar's ``side``/``zone``/``scar_type``/``color``, and the frame's
    ``scars_visible == "NO"`` as the absence marker. A frame that was never asked
    about scars (empty ``scars_visible``, no scars) contributes nothing: it is "not
    asked", not "reported none". ``no_shark`` is NOT an absence claim: it says there
    is no animal in THIS FRAME, which is a statement about the footage, not about
    the animal's skin — the shipped consensus engine ignores it for scars too, and
    reading it as "no scars" would mark every key scar a miss for a labeler who
    stopped on an empty frame.
    """
    ...

def _absent_encounters(rows: Iterable[Dict[str, Any]]) -> set:
    """Encounters this rater explicitly reported as carrying nothing.

    Derived from the raw rows rather than trusted from ``dedupe``'s companion key,
    so the storage layer does not depend on how that key is spelled. A "No" beside
    a reported scar is not an absence claim.
    """
    ...

def _dedupe(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Dict[str, Any]]], set]:
    ...

def _jsonable(obj: Any) -> Any:
    ...

def compute_all_scores() -> List[Dict[str, Any]]:
    """Mark every rater who has rows on the training set, and store one row each.

    Survey rows and app rows are merged as more rows of the same rater — the app's
    rows win nothing. Never calls ``update_user_weights``; see ``apply_scores``.
    """
    ...

def _score_row(r) -> Dict[str, Any]:
    ...

def latest_scores() -> List[Dict[str, Any]]:
    """One row per annotator (``compute_all_scores`` replaces), unredacted."""
    ...

def own_score(annotator: str) -> Optional[Dict[str, Any]]:
    """What a labeler may see about their own score: the headline numbers only.

    Goes through ``training_scoring.redact_for_labeler`` so the key's content and the
    per-encounter detail (which would reveal the answers) never leave the server.
    """
    ...

def apply_scores(min_encounters: int=5) -> List[Dict[str, Any]]:
    """Copy each sufficiently-grounded proficiency onto the user's weight.

    The ONLY caller of ``update_user_weights`` in this module. A score resting on
    fewer than ``min_encounters`` attempted encounters is skipped: one lucky
    encounter must not set a semester's weight. An unscorable rater (``proficiency``
    None — nothing attempted) is skipped too.

    **An expert is never written.** ``compute_all_scores`` marks everyone with rows
    on the training encounters, and that includes the person who wrote the key
    (their app annotations on those clips are rows like anybody else's). Writing
    their F1 through ``update_user_weights`` would move BOTH ``proficiency_weight``
    and the ``quiz_weight`` baseline of the one account whose weight is fixed at
    1.5/1.0 by ``is_expert`` — the next consensus refresh resets the first, the
    baseline stays wrong forever. Skipped, like a row under the floor.
    """
    ...

def key_from_annotations(annotator: str, source: str='') -> Dict[str, Any]:
    """Make one annotator's own app work on the training set THE answer key.

    The lab lead annotates every training clip in the same tool the students use,
    then presses this: their deduped signatures per encounter become the key, and
    an encounter they answered "no scars visible" on (and boxed nothing) becomes a
    known no-scar. Encounters they have not touched are left OUT of the key —
    absence of an answer is not an answer of absence.
    """
    ...

def key_from_reports(min_agreement: float, source: str='') -> Dict[str, Any]:
    """Derive a key from the survey rows: a scar is "known" when at least
    ``min_agreement`` of the raters who reported on that encounter listed it
    (side, zone, type). An encounter is known no-scar when that share said
    "no scars visible"; an encounter where nothing reaches the bar is LEFT OUT,
    not written as empty — "nobody agreed" is not "nothing is there".

    ``min_agreement`` is a fraction in (0, 1]; there is deliberately no default,
    because the bar IS the definition of the key.
    """
    ...

def encounter_feedback(annotator: str, encounter_id: str) -> Optional[Dict[str, Any]]:
    """One labeler's result on ONE training encounter, shaped for the "How you did"
    panel (static/js/gold_result.js, task 'scars'): the key's scars with a status
    of ok/missed, the number of extra ones, and the encounter's F1 as the score.
    ``None`` when the encounter is not in the key (nothing to mark against).
    The panel is the teaching: it names what was missed, so it is shown only AFTER
    the labeler has finished every clip of the encounter (the caller decides that).
    """
    ...

def summary() -> Dict[str, Any]:
    ...
