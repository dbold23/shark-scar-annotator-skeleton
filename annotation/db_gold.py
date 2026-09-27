"""Gold standards: the answer key a walkthrough is marked against.

A lab lead annotates a handful of frames the way they should be done. Those frames
become the walkthrough every new labeler serves, and the recurring skill check
thereafter. Storage only — the comparison lives in ``annotation/gold_scoring.py``,
the queue mechanics in ``db_datasets``, exactly the split ``signal_consensus.py``
uses.

Three rules are enforced *in the schema* rather than in a caller, because each is
unrecoverable once broken:

  * **A labeler never meets the same gold frame twice.** ``UNIQUE(gold_id,
    annotator)`` on the attempts table. The second sitting on a frame you have
    already been marked on measures memory, not skill, and the retry-on-failure
    path exists precisely so nobody re-answers a question they were just shown the
    answer to.
  * **Attempts are kept, never overwritten.** A gold answer that is later edited
    does not rewrite the history of who was marked against what.
  * **Gold answers are retired, not deleted** — same rule as a signal vocabulary
    term. An attempt row is meaningless if the question it answered has vanished.

Annotator emails are stored **lower-cased**. The JWT preserves whatever casing the
identity provider hands over while `work_items.leased_by` and `spec_practice` do
not agree on it; without normalising, one human becomes two, and the no-repeat
guarantee above quietly stops holding for whichever spelling is new.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from annotation.database import get_conn
from .identity import norm_annotator as _norm_annotator

def init_gold_tables() -> None:
    """Idempotent CREATE TABLE IF NOT EXISTS, called from the public entry points.

    Not migration-only, deliberately: migrations run at Docker build time against a
    throwaway layer, so a table that exists only in a migration never reaches the
    production volume DB. Same reasoning as ``db_datasets.init_dataset_tables``.
    """
    ...

def _now() -> str:
    ...

def _row(r) -> Dict[str, Any]:
    ...

def create_gold(*, task_type: str, video_id: str, frame_number: Optional[int], answer: Dict[str, Any], created_by: str='', teach_note: str='', spec_id: Optional[int]=None) -> Dict[str, Any]:
    """Store (or replace) the answer key for one frame.

    Re-authoring the same frame UPDATES it rather than raising: an admin who
    notices a mistake in their own exemplar must be able to fix it. Existing
    attempt rows are left alone — they record what was asked at the time.
    """
    ...

def get_gold(gold_id: int) -> Optional[Dict[str, Any]]:
    ...

def gold_for_frame(task_type: str, video_id: str, frame_number: Optional[int]) -> Optional[Dict[str, Any]]:
    """The active answer key for a (task, video, frame), if one exists."""
    ...

def list_gold(*, task_type: Optional[str]=None, status: Optional[str]='active') -> List[Dict[str, Any]]:
    """Gold answers with their usage count — what the admin table renders."""
    ...

def retire_gold(gold_id: int) -> bool:
    """Take a gold answer out of circulation without deleting it — the attempts that
    were marked against it must keep resolving."""
    ...

def count_active(task_type: Optional[str]=None) -> int:
    ...

def _table_exists(conn, name: str) -> bool:
    ...

def _unseen_clause(conn) -> tuple:
    """The WHERE fragment and its parameters, skipping tables that do not exist.

    `work_items` and `annotations` are owned by other modules and a caller may be
    running against a partial schema (tests, a fresh volume). A missing table
    degrades to the older, weaker rule rather than raising.
    """
    ...

def unseen_gold(annotator: str, task_type: str, limit: int=3) -> List[Dict[str, Any]]:
    """Active gold for this task that ``annotator`` has never been asked.

    The heart of the no-repeat rule: a retry after a failed walkthrough draws from
    here, so the second sitting is a different set of frames. See `_UNSEEN_MARKED`
    for what "never been asked" has to mean, and why the narrower reading (never
    been MARKED) let the same question come back.
    """
    ...

def count_unseen(annotator: str, task_type: str) -> int:
    """How many questions are left for this person on this task.

    The gate consults this BEFORE it starts a run: a walkthrough sized larger than
    the pool can never be completed, and a labeler stuck at "2 of 3" with nothing
    left to serve is the strand this whole design refuses. It therefore has to
    count exactly what `unseen_gold` would hand out — same clause, one definition.
    """
    ...

def gold_candidates(task_type: str, *, limit: int=20, per_video: int=2) -> List[Dict[str, Any]]:
    """Frames worth turning into an answer key — a shortlist, not a blank picker.

    Drawn from work that already exists, because a gold frame has to be one where
    the right answer is unambiguous, and the best evidence of that is somebody
    experienced having already annotated it completely:

      * pose → a COMPLETE 16-point skeleton. A partial skeleton makes a poor
        answer key: every point the exemplar omits is a point the labeler is
        marked on against nothing.
      * bbox / segment → at least one scar, since a frame with no scars cannot
        distinguish "found nothing" from "looked at nothing".

    Experts first (``users.is_expert``), then the most complete annotation. Capped
    per video: ten frames of one clip is not a walkthrough, it is one clip.
    """
    ...

def record_attempt(*, gold_id: int, annotator: str, score: Optional[float], passed: bool, kind: str='walkthrough', detail: Optional[Dict[str, Any]]=None, spec_id: Optional[int]=None, annotation_id: Optional[str]=None) -> Optional[Dict[str, Any]]:
    """Record one marked sitting. A second attempt on the same gold by the same
    person is IGNORED, not overwritten — that combination is the thing the schema
    exists to prevent, and silently replacing the first result would let a reload
    turn a fail into a pass."""
    ...

def attempts(annotator: str, *, kind: Optional[str]=None, limit: int=50) -> List[Dict[str, Any]]:
    ...

def scorecard(annotator: str, *, task_type: Optional[str]=None, window: int=10) -> Dict[str, Any]:
    """This labeler's standing on gold: the trailing mean and what it is made of.

    Reported separately from the gamification q-score on purpose. That value feeds
    ``compute_skill`` → ``route_policy`` → task routing, so folding a quiz result
    into it would silently re-route somebody's work as a side effect of a check.
    """
    ...

def latest_attempt(annotator: str, gold_id: int) -> Optional[Dict[str, Any]]:
    ...

def flagged(threshold: float, *, window: int=5) -> List[Dict[str, Any]]:
    """Labelers whose recent gold work sits below the bar — the admin's flag list.

    Ordered worst-first. Says nothing about coverage: a gold answer only measures
    the frames somebody was actually shown.
    """
    ...
