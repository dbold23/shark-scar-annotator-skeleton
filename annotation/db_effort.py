"""Storage and retrieval for effort metrics. The reading half of ``effort.py``.

Two additive columns on ``annotations`` and one query. There is no new table:
effort is a property OF an annotation, one row per annotation already exists,
and a parallel table keyed on the same triple would be a second thing to keep in
step with ``make_annotation_id`` — the exact drift that produced 68 duplicate
groups when a relink rewrote ``video_id`` without recomputing the id.

``active_ms``  Client-measured attention on this frame, accumulated across
               visits. NULL means "not recorded", which is a different claim
               from 0 and must stay distinguishable: every row written before
               ``metrics.effort.record`` was switched on is NULL forever, and a
               0 there would read as an annotation that took no time.

``save_count`` How many times this row has been written. It is the rework
               signal — a frame saved five times is one somebody kept coming
               back to — and it is also what stops ``active_ms`` lying: the save
               path is INSERT OR REPLACE, so without deliberate accumulation a
               revisit would silently DISCARD the time already banked and
               replace an hour's work with the ninety seconds of the last edit.

Both are created by ``database.init_annotation_columns`` — which
``init_core_tables`` now calls — and NOT by a versioned migration alone:
migrations run at Docker BUILD time against a throwaway layer and never reach
the mounted production volume. That is the trap that left
``track_verifications`` absent in prod for the whole life of that feature.

The columns are unconditional. ``metrics.effort.record`` governs whether the
CLIENT measures anything, never whether the column exists to receive it — a flag
that changes the schema turns "we switched it on" into a migration, on a box
where migrations do not run.
"""
from __future__ import annotations
import json
from typing import Dict, Iterable, List, Optional, Tuple
from . import effort
from .database import get_conn

def clamp_active_ms(value) -> Optional[int]:
    """Sanitise a client-supplied duration. None for anything unusable.

    Rejects rather than clips at the top end. A clip would turn "the tab was
    open all weekend" into a confident four-hour measurement sitting at the top
    of every 'hardest frames' list; None says the one true thing, which is that
    this row has no usable timing.
    """
    ...

def signature(blob: Dict) -> str:
    """What this frame ASSERTS, as one comparable token.

    Autopilot is "the same answer over and over", so the signature has to be the
    answer and nothing else — not the box coordinates, which differ by a pixel
    every time and would make every frame unique, hiding the very runs being
    looked for.
    """
    ...

def _mean_confidence(blob: Dict) -> Optional[float]:
    ...

def load_events(annotator: Optional[str]=None, limit: int=20000) -> List[effort.Event]:
    """Every save, oldest first, as effort.Event.

    Ordered by date because every function downstream is about sequence, and
    sorting 20k rows in Python after SQLite already has an index on nothing in
    particular is work for no reason.

    `json_data` is parsed here rather than in `effort.py` so that module stays
    free of this app's blob schema; a row whose blob will not parse still
    contributes its timing, because when it happened is independent of what it
    said.
    """
    ...

def disputed_frames(limit: int=5000) -> List[Tuple[str, int]]:
    """(video_id, frame_number) pairs the queue's agreement layer could not settle.

    Read from `work_item_agreement` when it is there and empty otherwise. It is
    deliberately the ONLY source: this repo has four agreement engines keyed on
    different identities, and quietly picking a second one here would make
    `effort` the place their numbers got mixed. A caller with a better list
    passes it to `effort.classify_items` directly.
    """
    ...

def coverage() -> Dict:
    """How much of the corpus has real timing — the first thing to check.

    Every effort figure is quotable only alongside this. A median computed on
    4% of rows is not a corpus statistic, and shipping the fraction beside the
    number is what keeps somebody from treating it as one.
    """
    ...
