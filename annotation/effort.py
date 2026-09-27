"""How long the work takes, and what that is evidence OF.

Pure computation — no DB, no Flask, no config — the same split as
``label_quality.py``, ``scar_consensus.py`` and ``signal_consensus.py``.
``db_effort.py`` reads the rows; this module decides what they mean.

WHY THIS EXISTS, AND WHAT IT IS NOT
-----------------------------------
Timing a labeler is only worth doing if the number changes a decision. Three
decisions it genuinely changes, all of them about the CORPUS or the CURRICULUM,
none of them about ranking people:

1. **What a semester costs.** The quota is 150 scars. Whether that is four hours
   or forty is currently unknown, so it has never been possible to tell a
   student what they signed up for, or to size a cohort against a deadline.
   Published rates for comparable work: a tight, high-quality bounding box runs
   ~42 s (~26 s when annotators are pushed for speed), a yes/no question ~1.6 s,
   a single point ~0.9 s [Papadopoulos et al., extreme clicking]. Zooniverse
   volunteers average roughly 50 classifications an hour. Our task is a bbox
   PLUS a four-field classification, so it should land above the bbox figure —
   and if it lands below it, that is worth knowing.

2. **Which frames deserve a second rater.** Response time is the standard proxy
   for cognitive effort, and slow items are disproportionately the ambiguous
   ones. Crossed with the agreement this repo already computes, it separates two
   populations that look identical in a disagreement report and need opposite
   responses: **slow + disputed** is a genuinely hard frame (send it to a third
   rater, or make it an answer key), **fast + disputed** is a frame somebody
   rushed (coach, do not enshrine). Today both are just "disputed".

3. **When somebody has stopped looking.** The documented symptom of annotation
   fatigue is *autopilot* — the same label applied repeatedly without
   deliberation, which shows up as long uninterrupted runs of one signature in
   timestamp order. That needs no timing at all; it is computable on data this
   catalog has held since March. This app has a "Repeat for next box" control,
   which is a genuine speed-up and also the easiest possible way to produce a
   run, so the run length is worth watching precisely BECAUSE we shipped it.

And the thing this is deliberately NOT:

**Time never weights a quality score.** Not consensus, not `proficiency_weight`,
not `qscore`. It is a flag that says "a human should look at this", nothing more.
The repo already made this decision once, about self-reported confidence: it is
"CONSUMED but never WEIGHTS anything", because a number that raises your standing
is a number you learn to produce. Speed is worse — it is trivially gameable in
BOTH directions, and paying for either one buys the behaviour rather than the
work. A fast labeler who agrees with everyone is not a problem to be solved.

WHAT THE TIMESTAMPS CAN AND CANNOT SEE
--------------------------------------
Two sources, and they are not interchangeable.

``annotation_date`` exists on every row back to March, so gaps between
consecutive saves reconstruct sessions for free. But a gap is bounded by two
saves, which means:

  * the **last item of every session has no successor** and contributes nothing;
  * the **first item is invisible** — all the time before the first save (open
    the clip, find the animal, decide) is outside every gap;
  * a long pause is unattributable. Twenty minutes of scrubbing and one save is
    indistinguishable from twenty minutes at lunch, so `IDLE_GAP_S` discards
    both.

Measured on this catalog: 375 saves yield 320 usable gaps, so ~15% of items are
already invisible before any of the above bites, and every figure derived this
way is a FLOOR. `estimate_from_gaps` says so in its return value rather than
leaving the caller to assume otherwise.

``active_ms`` is the client's own measurement of attention on one frame — it
starts when the frame is shown, pauses when the tab is hidden or the labeler
goes idle, and survives the first item of a session. Where it exists it is
strictly better and the gap estimate is not used at all. It ships OFF
(``metrics.effort.record``), because recording how long a student takes is a
capability that must be chosen, not inherited from an absent config section.
"""
from __future__ import annotations
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
AUTOPILOT_RUN = 8
RUSH_FRACTION = 0.25

class Event(dict):
    """One save. A dict so it survives JSON round-trips without a schema.

    Keys: annotator, at (datetime), video_id, frame_number, signature (hashable),
    active_ms (int | None), n_scars (int), confidence (float | None).
    """
    __slots__ = ()

def make_event(annotator: str, at, video_id: str, frame_number, signature=None, active_ms=None, n_scars=0, confidence=None) -> Optional[Event]:
    """Build an Event, or None if it cannot be placed in time.

    A row with an unparseable date is DROPPED rather than defaulted to now():
    a synthetic timestamp does not merely lose one row, it invents a gap on
    either side of itself and corrupts the two neighbours as well.
    """
    ...

def _parse_dt(v) -> Optional[datetime]:
    ...

def _pos_int(v) -> Optional[int]:
    ...

def _norm(email) -> str:
    """One human, one labeler. Mirrors annotation.identity.norm_annotator, which
    is not imported here only because this module stays dependency-free."""
    ...

def _by_annotator(events: Iterable[Event]) -> Dict[str, List[Event]]:
    ...

def sessions(events: Iterable[Event], idle_gap_s: int=IDLE_GAP_S) -> List[Dict]:
    """Split each labeler's saves into sittings.

    A session is the unit almost every other question here is asked in: cost per
    hour, fatigue within a sitting, whether somebody is doing one long slog or
    twenty short visits. Returned sorted by start so a caller can page them.
    """
    ...

def _close_session(who: str, evs: List[Event]) -> Dict:
    ...

def estimate_from_gaps(events: Iterable[Event], idle_gap_s: int=IDLE_GAP_S) -> Dict:
    """Per-item seconds inferred from the interval between consecutive saves.

    Every number here is a FLOOR, and the return value carries the arithmetic
    that makes it one (`n_items`, `n_timed`, `blind_items`) so a caller cannot
    quote the median without also being able to see how much of the corpus it
    was computed on.
    """
    ...

def measured_effort(events: Iterable[Event]) -> Dict:
    """Per-item seconds from the client's own attention clock (`active_ms`).

    Reported separately from `estimate_from_gaps` and never blended with it.
    They answer the same question with different denominators, and averaging a
    measurement with an inference produces a number that is neither.
    """
    ...

def _pct(vals: Sequence[float], q: float) -> float:
    ...

def item_seconds(events: Iterable[Event], idle_gap_s: int=IDLE_GAP_S) -> Dict[Tuple, float]:
    """Best available seconds per (video_id, frame_number, annotator).

    `active_ms` wins wherever it exists; otherwise the forward gap, when that
    gap is inside the session. Items with neither are ABSENT from the mapping
    rather than present with a zero — a zero would sort straight to the top of
    the "rushed" list and put the least-known items in front of a human as the
    most suspicious ones.
    """
    ...

def learning_curve(events: Iterable[Event], bucket: int=25, idle_gap_s: int=IDLE_GAP_S) -> Dict:
    """Seconds per item against how many items that person has done.

    The practical question is "when is somebody trained?", which today is
    answered by a fixed quota and a hunch. A curve that has flattened is a
    labeler who has stopped getting faster; that is the moment their work is
    worth as much as it is going to get, and the moment the practice gate is
    doing nothing for them.

    Buckets are per-annotator ordinal position, NOT calendar time: two students
    who start a month apart belong on the same axis.
    """
    ...

def autopilot_runs(events: Iterable[Event], min_run: int=AUTOPILOT_RUN, idle_gap_s: int=IDLE_GAP_S) -> List[Dict]:
    """Longest stretch of consecutive saves carrying an identical signature.

    Computed WITHIN a session: a run that spans a two-day break is two
    unremarkable stretches of similar work, not evidence of anybody coasting.

    A run is not proof of anything. Twelve frames of one animal with one scar
    SHOULD look identical, and this app's "Repeat for next box" exists to make
    exactly that cheap. What the number is good for is the tail — the run of
    forty across four different videos, which is not a property of the footage.
    """
    ...

def fatigue_drift(events: Iterable[Event], idle_gap_s: int=IDLE_GAP_S, halves: bool=True) -> Dict:
    """Does a sitting get faster as it goes on, and by how much?

    Accelerating late in a session is the measurable trace of autopilot: the
    same task taking steadily less attention. Reported as a ratio of the second
    half's median to the first half's, per annotator, over sessions long enough
    to have halves.

    A ratio below 1 is NOT an accusation — people genuinely warm up, and the
    first items of a sitting include re-orienting to the clip. It is a question:
    is this a warm-up, or is it the fortieth frame in a row.
    """
    ...

def classify_items(events: Iterable[Event], disputed: Iterable[Tuple]=(), idle_gap_s: int=IDLE_GAP_S) -> Dict:
    """Cross time with disagreement, which is the one thing neither can do alone.

    `disputed` is any iterable of (video_id, frame_number) the agreement layer
    could not settle — `work_item_agreement`, the encounter engine's
    `disputed_scars`, whatever the caller already has. This module does not
    compute agreement and must not: there are four different agreement engines
    in this repo and picking one here would quietly make it the definition.

    The split, and why it is worth making:

      slow + disputed   a genuinely hard frame. Buy another rater, or make it an
                        answer key — an exemplar is most valuable exactly where
                        people diverge.
      fast + disputed   somebody hurried. Coaching, not corpus. Enshrining this
                        as "hard" teaches the queue to spend raters on the wrong
                        frames.
      slow + agreed     fine, and expensive. If a whole zone lands here the task
                        design is costing more than it returns.
      fast + agreed     the working case.

    "Slow" and "fast" are per-annotator quantiles, never a global threshold: a
    careful labeler's median is someone else's p90, and a fixed cutoff would sort
    the corpus by who happened to label it.
    """
    ...

def report(events: Iterable[Event], disputed: Iterable[Tuple]=(), idle_gap_s: int=IDLE_GAP_S) -> Dict:
    """Everything above, over one set of events."""
    ...
