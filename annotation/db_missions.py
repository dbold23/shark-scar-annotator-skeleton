"""Mission suggestions: a labeler proposes work, a lab lead answers.

A mission in this app is a ``dataset_specs`` row. The queue already calls them
missions and stamps every card with one. So a suggestion is NOT a second kind of
mission; it is a request that one be created, and once accepted it holds nothing
but a pointer to the spec that resulted.

That pointer is the whole design. The obvious alternative is to store a lifecycle
on the suggestion itself (proposed, accepted, running, finished) and keep it in
step with the spec. It will not stay in step: the only thing that ever activates
or freezes a mission here is a human clicking a button in a different surface, so
a stored copy drifts and then lies. Instead four states are STORED, and anything
that depends on the spec is DERIVED at read time by ``derive_state``.

Two rules carried over from things this codebase already learned:

  * No terminal rejection. ``declined`` can be reopened. ``spec_practice``'s first
    version stranded the labeler with no route forward, and there is no reason to
    repeat that with somebody's idea.
  * Nothing is hard-deleted. Withdrawing sets ``withdrawn_at``, so a suggestion
    that was answered still resolves for the person who wrote it.

Deliberately absent: votes, counts of other people's suggestions, and any byline
shown to a peer. The gamification layer is private and non-competitive by design,
and a suggestion box with a score attached is a popularity contest that would
start inducing exactly the herding the multi-rater design exists to measure.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from .database import get_conn
from . import db_datasets
TITLE_MAX = 120
RATIONALE_MAX = 2000

def init_mission_tables() -> None:
    """Create the tables if absent.

    Runs from every public entry point below, and at blueprint registration, so the
    tables reach a production volume DB without a manual migration pass. Migrations
    execute at Docker build time against a throwaway layer; a table that exists only
    in a migration script never arrives.

    ``init_dataset_tables()`` first, because ``spec_id`` references ``dataset_specs``
    and ``get_conn()`` has foreign keys ON: creating the child before the parent
    would fail on the first insert, not at CREATE, which is the worse failure.
    """
    ...

def _now() -> str:
    ...

def _norm(email: str) -> str:
    ...

def create_suggestion(*, title: str, rationale: str, task_type: str, suggested_by: str) -> Dict[str, Any]:
    """Record a proposal. Raises ValueError with a message meant for the labeler."""
    ...

def withdraw_suggestion(sid: int, *, annotator: Optional[str]=None) -> bool:
    """Take a suggestion back. ``annotator=None`` means an admin, who may withdraw
    anybody's; a labeler passes their own address and can only reach their own.

    Scoping lives HERE rather than in the route, the same shape ``db_roi`` uses, so
    a second caller cannot forget it.
    """
    ...

def review_suggestion(sid: int, *, decision: str, note: str, actor: str, spec_id: Optional[int]=None) -> Dict[str, Any]:
    """Answer a suggestion. ``decision`` is accept, decline or reopen.

    A decline REQUIRES a note, enforced here rather than only in the UI: the note is
    shown to the person word for word, and "no" with no reason is the version of this
    feature that stops anybody suggesting anything again.

    Accepting LINKS a spec; it does not activate one. Starting dispatch stays behind
    the existing spec-status route, so there is exactly one door through which work
    reaches students.
    """
    ...

def derive_state(sug: Dict[str, Any]) -> str:
    """What to SHOW, as opposed to what is stored.

    Anything downstream of acceptance is a fact about the spec, so it is read from
    the spec every time rather than copied onto the suggestion where it would go
    stale the first time somebody froze a mission.
    """
    ...

def _hydrate(row) -> Dict[str, Any]:
    ...

def get_suggestion(sid: int) -> Optional[Dict[str, Any]]:
    ...

def list_for_author(annotator: str) -> List[Dict[str, Any]]:
    """One person's own suggestions, newest first. There is no route by which a
    labeler reads anybody else's: whose idea it was is not a thing peers need."""
    ...

def open_count(annotator: str) -> int:
    """How many are still awaiting an answer. The cap this feeds exists to keep one
    enthusiastic person from burying the review list, not to ration ideas."""
    ...

def list_for_review(status: str='proposed') -> List[Dict[str, Any]]:
    """The admin queue, defaulting to the people actually waiting on an answer."""
    ...

def events(sid: int) -> List[Dict[str, Any]]:
    ...
