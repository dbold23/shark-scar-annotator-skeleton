"""The one curated list of every model this project uses, and what it scored.

WHY A COMMITTED FILE AND NOT A TABLE
------------------------------------
`model_registry` already exists as a SQLite table (v20, written by
`annotation/db_mlops.py`). It is the ORCHESTRATOR's ledger: artifacts that
Stream B trained itself, with the golden-set metric its eval gate compared. It
can only ever hold models the orchestrator made.

Most of the models actually in play were not made by the orchestrator. SAM2 is a
foundation checkpoint downloaded from Meta. The deployed pose model predates the
orchestrator entirely and its training run is not identified. The scar
classifier is a config scaffold with no weights at all. An aggregator like
`annotation/encounter_side.py` has real measured performance and no weights file
of its own. None of those can be a row in a table whose columns are
`trained_from_run_id` and `golden_set`, and inventing values so they fit would
put fiction in the ledger the eval gate reads.

So the curated catalogue is a committed JSON file that a human writes and a test
checks, and the admin view MERGES it with the table. Each entry says where it
came from: source "file" (curated) or source "db" (the orchestrator's ledger).
Nothing here ever writes to that table.

THE TWO RULES THIS MODULE ENFORCES
----------------------------------
1. A model with no registry entry is not deployed. `validate` refuses a
   `deployed` entry with no `consumers`, because "deployed" with nothing naming
   it is a claim nobody can check.
2. A metric with no denominator is not a metric. Every metrics block must carry
   the split size it was measured on. 0.9634 mAP50 on 29 test images and 0.9634
   on 2,900 are different facts, and the number alone cannot tell them apart.

PURE, STDLIB ONLY. No Flask, no sqlite3, no third-party imports. The Flask route
imports this and passes db rows in; the test suite is ML-free and imports it
directly. `tests/test_model_registry.py` pins the purity in a subprocess, the
same way `tests/test_identity.py` pins `annotation/identity.py`.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
SCHEMA_VERSION = 1

def load_registry(path: str | Path) -> Dict[str, Any]:
    """Read the catalogue. Raises rather than returning a partial registry: a
    silently empty catalogue would make the admin view report "no models",
    which is the one answer that is never true."""
    ...

def entries(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    ...

def validate(obj: Dict[str, Any]) -> List[str]:
    """Return every problem found, as plain sentences. Never raises, never stops
    at the first one: an operator fixing a catalogue wants the whole list.

    Accepts either a whole registry (`{"schema_version": .., "models": [..]}`)
    or a single entry. Uniqueness and `depends_on` resolution are registry-level
    facts, so a single entry is checked against itself alone and those two
    checks simply have nothing to say."""
    ...

def _validate_registry(registry: Dict[str, Any]) -> List[str]:
    ...

def validate_entry(entry: Dict[str, Any], known_ids: Iterable[str]=(), *, caveats_may_be_absent: bool=False) -> List[str]:
    """Check one entry. `known_ids` is what `depends_on` may point at.

    `caveats_may_be_absent` is for the db projection ONLY. The v20 ledger has no
    caveats column, and `None` there is the honest encoding of "nobody was ever
    asked"; `[]` would read as "somebody checked and there are none". A curated
    entry gets no such licence -- the whole point of writing one by hand is that
    a person considered what a reader needs to know first.
    """
    ...

def _check_file(entry: Dict[str, Any], where: str) -> List[str]:
    ...

def _check_metrics(entry: Dict[str, Any], where: str) -> List[str]:
    ...

def merge_with_db(file_entries: Iterable[Dict[str, Any]], db_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One list the admin view can render, from two populations that will never
    have the same shape.

    The file is curated by a human and covers every model; the v20
    `model_registry` table is the orchestrator's own ledger of what it trained
    and gated. A db row is projected onto the file's shape rather than the other
    way round, because the file's shape is the one that can express a foundation
    checkpoint or an aggregator. Fields the table simply does not have are stated
    as absent rather than filled with a plausible default: the ledger has no
    `caveats` column, so the projected list SAYS that instead of coming back as
    `[]`, which would read as "somebody checked and there are none".

    The projection is held to the same rules as the file half. It did not used
    to be: `merge_with_db` emitted rows that `validate_entry` refused, so a
    champion arrived at the admin card as `deployed` with no consumers, which is
    exactly the state the deployed-needs-a-consumer rule exists to refuse. Use
    `validate_db_projection` on the merged list; a rule the machine half is
    exempt from is a rule that only ever catches humans.
    """
    ...

def validate_db_projection(merged: Iterable[Dict[str, Any]]) -> List[str]:
    """Hold the projected ledger rows to the same rules as the curated half.

    A rule the machine half is exempt from is a rule that only ever catches
    humans, and the two rules here are exactly the ones a ledger row is likely
    to break: a champion is `deployed`, so something must be named that loads
    it, and the eval gate's golden score is a number that needs its denominator
    like any other. The one relaxation is `caveats`, which the table has no
    column for.

    Reported separately from the file's problems, and never fatal: the ledger is
    written by the orchestrator, so an operator reading the admin card cannot
    fix a row here by editing a file. It is a diagnosis, not a chore list.
    """
    ...

def _slugify(text: str) -> str:
    """`model_type` is a free-text column, and a projected id has to satisfy the
    same slug rule a curated one does. Anything outside the alphabet becomes an
    underscore rather than being dropped, so two model types cannot collapse
    onto one id."""
    ...

def _db_row_to_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    ...

def source_counts(merged: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    ...

def _num(value: Any, places: int=4) -> str:
    ...

def figure(value: Any) -> Dict[str, Any]:
    """Split one metric figure into its value, its own denominator and what
    that denominator counts.

    Two encodings are legal and both have to render. A plain number takes the
    block's `n_<split>` -- correct when every figure in the block was measured
    on the same population. A figure measured on its OWN population is written
    `{"value": .., "n": .., "of": ".."}`, which is the encoding `_check_metrics`
    asks for and which existed for a while with nothing able to display it: it
    validated, then rendered as a raw dict in MODELS.md and not at all on the
    dashboard. An encoding a reader never sees is one an author will not use.
    """
    ...

def format_figure(value: Any, places: int=4) -> str:
    """`0.9634`, or `0.6 (n=5 encounters answered)` when the figure carries its
    own denominator. The block header states the n only when the whole block
    shares one, so the two never contradict each other."""
    ...

def _split_map(entry: Dict[str, Any], split: str) -> Dict[str, Any]:
    ...

def _n_for(entry: Dict[str, Any], split: str) -> Any:
    ...

def _map_cell(entry: Dict[str, Any], split: str) -> str:
    ...

def _lineage_cell(entry: Dict[str, Any]) -> str:
    """Whether anybody can say where these weights came from, in the SUMMARY
    row rather than only in the detail. The one entry in this catalogue that
    cannot say is also the deployed one, and a table that shows `deployed` --
    the strongest word in the vocabulary -- with nothing marking the gap reads
    as an ordinary model until somebody opens it."""
    ...

def _md_escape(text: Any) -> str:
    """Pipes would split a table cell. Nothing else is escaped: this file is
    read as much in a terminal as in a renderer, and backslash noise costs more
    than it buys."""
    ...

def render_markdown(registry: Dict[str, Any]) -> str:
    """The catalogue as a page a human reads. Deterministic: same JSON in, byte
    identical Markdown out, so a stale MODELS.md is a test failure rather than
    something nobody notices for a semester."""
    ...

def _render_entry(e: Dict[str, Any]) -> List[str]:
    ...
