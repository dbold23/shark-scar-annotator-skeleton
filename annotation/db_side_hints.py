"""Precomputed encounter-level flank coverage — the cache behind
``GET /api/encounters/<code>/side-hint``.

WHAT THIS ANSWERS, AND WHAT IT DOES NOT
---------------------------------------
Two different questions in this app both use the word "side", and conflating them
is the mistake this table exists to keep separate:

    per-SCAR side          "which flank is THIS mark on"   -> Left | Right
    per-ENCOUNTER coverage "which flanks did we SEE at all" -> Left | Right | Both

Only the second one can answer "Both", because "Both" is a statement about a
collection of frames, never about one frame. `frame_hints` (v43) stores the first
kind at frame grain and deliberately refuses to store an encounter-level claim;
this table is the other half, and it is keyed on `encounter_code` for exactly that
reason. A row here covers every clip of the encounter, which is the same grain the
372 historical `$.sides_visible` answers in `annotations.json_data` are stated at.

WHY IT IS PRECOMPUTED AND NEVER LIVE
-------------------------------------
Producing one row means walking every clip of an encounter with a landmark
detector — minutes of CPU, on the box that serves requests. The read path is a
suggestion rendered beside a radio group the moment a video opens, so it has a
budget of milliseconds and must never run inference. `scripts/precompute_encounter_sides.py`
is the only writer; the route is a lookup with no fallback. Read wide, write narrow,
the same split `db_frame_hints` uses.

WHY `model_version` IS IN THE UNIQUE KEY
-----------------------------------------
Same rule as `frame_hints`: a stored suggestion is a measurement against specific
weights. Re-running a NEW model inserts beside the old rows rather than overwriting
them, so the corpus keeps the record that makes the next model comparable. Re-running
the SAME version overwrites in place, because that is a correction rather than a
second opinion.

WHY THE PER-CLIP BREAKDOWN IS STORED
-------------------------------------
`details_json` carries one entry per clip: its counts and its longest same-side run.
An encounter answer of "Both" built from one clip that only ever showed Left and one
that only ever showed Right is a very different claim from one clip that flipped, and
an operator adjudicating a suggestion needs to see which. The aggregate columns cannot
express it and a second table would be one join for a blob nothing queries by field.

Those per-clip numbers come from `encounter_side.clip_census`, the same walk that
produced the answer, and they are POST-gate: they sum to the aggregate columns.
A breakdown computed by a second implementation is worse than no breakdown, because
it sits in the same row as the answer and quietly disagrees with it.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from annotation.database import get_conn

def init_side_hints_table() -> None:
    """Create the table + index, and add any column a later build introduced.

    Idempotent; safe on every app start. Migrations do not run in production, so
    this is the path by which both the table AND every subsequent column reach the
    live volume database.
    """
    ...

def upsert_side_hint(*, encounter_code: str, model_version: str, side: Optional[str]=None, reason: str='', n_left: int=0, n_right: int=0, n_undecided: int=0, n_unstable: int=0, n_frames: int=0, n_clips: int=0, n_attempted: int=0, n_unreadable: int=0, n_clips_total: int=0, n_clips_walked: int=0, n_stills: int=0, coverage: float=0.0, margin: float=0.0, config: Optional[Dict[str, Any]]=None, clips: Optional[Sequence[Dict[str, Any]]]=None, status: str=STATUS_COMPLETE) -> int:
    """Store one encounter's suggestion. Returns the row id.

    Raises ValueError on a `side` outside `VALID_SIDES`. The write path is a single
    offline script, so a typo there would otherwise reach the annotator as a
    confident suggestion in a vocabulary the form cannot select.
    """
    ...

def _row_to_dict(row) -> Dict[str, Any]:
    ...

def get_side_hint(encounter_code: str, model_version: Optional[str]=None) -> Optional[Dict[str, Any]]:
    """One encounter's suggestion, or None.

    With no `model_version` the NEWEST row wins — a fresh model should reach the
    annotator immediately. Pin the version to reproduce a measurement; leave it
    unset to get today's best answer.
    """
    ...

def list_side_hints(model_version: Optional[str]=None) -> List[Dict[str, Any]]:
    """Every stored suggestion, oldest encounter code first. Ops and tests."""
    ...

def delete_side_hints(encounter_code: str, model_version: Optional[str]=None) -> int:
    """Drop an encounter's rows. Returns rows removed.

    Only ever for a retraction — a model whose weights were wrong, say. Deleting to
    "refresh" is what `upsert_side_hint` is for, and it keeps the other versions.
    """
    ...

def coverage_stats(model_version: Optional[str]=None) -> Dict[str, Any]:
    """How much of the catalog actually carries a suggestion, and how many of those
    are abstentions.

    `n_decided` is the number that matters and it is NOT `n_rows`: an abstention is
    a stored row, and counting one as coverage is the same mistake as reading
    "the raters agreed" as "we found everything".
    """
    ...
DEFAULT_STALE_AFTER_HOURS = 48.0

def queued_encounter_codes(conn, statuses=QUEUE_STATUSES) -> List[str]:
    """Encounter codes a student can still be handed, from BOTH queues, ascending.

    Two queues exist. The legacy one is `assignments` (free choice, an admin
    hands out clips). Since Stream B the cohort actually works from `work_items`
    (the fed queue, `mlops.datasets.enabled`), and on the live catalog that is
    where the semester's 450 encounters are -- the assignments table holds 224
    older ones. Reading only `assignments` here made the admin readout say
    "39 of 224, 185 missing" on the day every one of the 450 fed-queue
    encounters had a row, and made the batch walk the wrong queue unless an
    operator seeded fake assignments into a snapshot first.

    THE ONE DEFINITION: `scripts/precompute_encounter_sides.py` selects its work
    through this function too, so the batch and the readout cannot disagree
    about what "the queue" is.

    `assignments` is joined through `videos` on `media_type='video'` because that
    is the column the assignment queue itself is built on -- NOT because it is a
    reliable statement about the media (176 of 828 rows on the 2026-09-01
    snapshot name a `.png`/`.jpg`; the precompute classifies by extension for
    exactly that reason). `work_items` needs no such filter: it IS the queue.
    A database without a `work_items` table (mlops never enabled, or an old
    snapshot) contributes nothing from it rather than failing.
    """
    ...

def queue_status(model_version: Optional[str]=None, stale_after_hours: float=DEFAULT_STALE_AFTER_HOURS) -> Dict[str, Any]:
    """How much of the assignment queue carries a suggestion, and whether the
    batch that fills it has stopped running.

    The same job the consensus freshness readout does, for the same reason: the
    annotator UI renders "no suggestion" identically whether the encounter was
    walked and the model declined, or nobody has run the precompute since the
    last twenty videos were assigned. Only an operator can tell those apart, and
    only if something says which.

    Read-only, and it NEVER walks anything -- the compute happens on the lab Mac
    (10 cores, MPS, 52 ms/frame) and the server that serves this route has 2
    cores and 1.9 GB of RAM. A status route that could trigger the work would put
    2.6 hours of inference on the box a student is waiting on.

    `model_version` unset resolves to the NEWEST version present in the table:
    that is the one the route serves by default, so it is the one whose coverage
    is worth reporting. A PARTIAL row does not count as computed -- it is an
    answer over some of the encounter's clips, and the batch is meant to come
    back for it.

    Neither does a row that read NOTHING. `missing` is "queued encounters with no
    usable suggestion", not "queued encounters with no row": a row over zero
    frames, zero clips and zero stills offers the annotator exactly what an absent
    row does, and counting it would let a walk that resolved no media report the
    queue as fully covered -- which is precisely the reading that made a mistyped
    `--media-index` invisible. The precompute now stores such a row `partial`, so
    this is the second of two independent guards on the same claim.
    """
    ...
