"""Stream F — export projections over `signal_labels`.

Read-only, exactly like `annotation/dwc_adapter.py`: storage is one model, published
formats are projections of it. Nothing here writes to the database.

**No new format is invented.** Every export below is a format one of the lab's existing
pipelines already reads, so labels produced here drop into those pipelines with zero
changes on their side:

| Function | Format | Consumer |
|---|---|---|
| :func:`raven_selection_table` | Raven Pro selection table (TSV) | OpenSoundscape ``BoxedAnnotations.from_raven_files``; `hydromoth_pipeline.detection` asks for exactly this ("tune against ground truth (Raven-annotated subset)") |
| :func:`boris_events_csv` | BORIS aggregated-events CSV | ``anchor.behavior.labels.load_boris_export`` → ``align_to_accel`` → ``labels_to_windows`` |
| :func:`rf_training_csv` | flat TF-box CSV | darwin-relay's labeled-ambiguity set (`CAPABILITIES.md` §4.4) |
| :func:`labels_json` | full provenance JSON | the source of truth the three above project from |

The one thing every projection must get right is **which clock its times are on**.
Labels are stored on the deployment clock; Raven wants times relative to the *sound
file*, and BORIS wants times relative to the *video*. Both conversions go through
:class:`signals.clock.SourceClock` rather than ad-hoc arithmetic, because an off-by-one-
source error here produces a file that ingests cleanly and is wrong.
"""
from __future__ import annotations
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from signals.clock import SourceClock, utc_of
__all__ = ['RAVEN_COLUMNS', 'BORIS_COLUMNS', 'RF_COLUMNS', 'source_clock', 'raven_selection_table', 'boris_events_csv', 'boris_sidecar', 'rf_training_csv', 'relay_eval_labels', 'labels_json', 'video_offset_s']

def source_clock(source: Dict[str, Any]) -> SourceClock:
    """Build a :class:`SourceClock` from a ``signal_sources`` row."""
    ...

def video_offset_s(video_source: Dict[str, Any], sensor_source: Dict[str, Any]) -> float:
    """``video_start − sensor_start`` in seconds — anchor's ``video_offset_s`` exactly.

    anchor-track aligns video-relative labels onto the accelerometer axis with one
    scalar. In this stream both sources are pinned to the deployment clock, so that
    scalar is just the difference of their offsets. Computing it here (rather than asking
    a human to recall it) removes the single most error-prone step of the old workflow.
    """
    ...

def _sorted(labels: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deterministic ordering so two exports of unchanged data are byte-identical."""
    ...

def _write_rows(columns: Sequence[str], rows: Iterable[Sequence[Any]], *, delimiter: str=',') -> str:
    ...

def _fmt(v: Optional[float], places: int=6) -> str:
    """Fixed-precision float, blank for None.

    Fixed rather than repr: Raven and BORIS readers are tolerant, but a column that
    silently switches to scientific notation for small values has broken a diff-based
    review more than once.
    """
    ...

def raven_selection_table(labels: Iterable[Dict[str, Any]], source: Dict[str, Any], *, view: str='Spectrogram 1', channel: int=1) -> str:
    """Project box labels on one audio source to a Raven Pro selection table (TSV).

    Times are converted from the deployment clock to **file-relative** seconds, which is
    what Raven means by "Begin Time (s)" and what OpenSoundscape assumes when it pairs a
    table with an audio file. Selection numbers are 1-based and contiguous, as Raven
    writes them.

    Only ``kind='box'`` labels are emitted: an interval has no frequency extent, and
    inventing one (say, 0 Hz to Nyquist) would assert a bandwidth the labeler never drew.
    """
    ...

def boris_events_csv(labels: Iterable[Dict[str, Any]], video_source: Dict[str, Any]) -> str:
    """Project interval/point labels to a BORIS aggregated-events CSV.

    Times are **video-relative**, matching BORIS's own export and therefore
    ``anchor.behavior.labels.load_boris_export`` without any adapter. Point events are
    written with equal start and stop, which that loader already normalises (it fills a
    blank stop from the start).

    Box labels are skipped — a waterfall selection is not a behaviour bout, and letting
    one leak in here would poison the behaviour classifier's training set with
    time-only-meaningful rows.
    """
    ...

def boris_sidecar(deployment: Dict[str, Any], video_source: Dict[str, Any], sensor_source: Optional[Dict[str, Any]]=None, *, n_labels: int=0) -> str:
    """The alignment sidecar that ships next to a BORIS CSV.

    Carries the one number `anchor labels import` needs and cannot derive from the CSV:
    ``video_offset_s``. Also records the deployment clock origin and both source offsets
    so the alignment can be audited later instead of taken on faith.
    """
    ...

def rf_training_csv(labels: Iterable[Dict[str, Any]], source: Dict[str, Any], deployment: Dict[str, Any]) -> str:
    """Project RF box labels to the flat training CSV darwin-relay's AI layer wants.

    Emits both the raw time–frequency box and the derived quantities the station's own
    event schema speaks in (``frequency_khz`` mirrors
    ``storage/local_store.push_detection``), so a labeled window can be compared directly
    against what the matched filter reported for the same moment.

    Absolute UTC is included because an RF training set spanning several captures is only
    joinable on wall-clock time.
    """
    ...

def relay_eval_labels(deployment: Dict[str, Any], rf_sources: Sequence[Dict[str, Any]], labels_by_source: Dict[int, Iterable[Dict[str, Any]]]) -> str:
    """Project RF labels into RELAY's `real_eval_labels.json` shape.

    Round-trips into `benchmark_real.py` / `benchmark_real2.py`, whose loader reads
    exactly five things: ``captures[].file``, ``captures[].tag_hz`` and each
    ``pulses[].t`` / ``pulses[].sigma``. Those are emitted in exactly that shape; the rest
    of the file is provenance for humans.

    Three honesty rules, because this file becomes somebody's ground truth:

    * **``sigma`` is only present when it was actually measured.** RELAY's sigma is a
      coherent matched-filter statistic MAD-normalised on a decimated baseband; a human's
      box on our incoherent magnitude spectrogram cannot produce a comparable number
      (measured: 13.3 dB above floor here for a pulse RELAY scored at 17.4 sigma). A label
      without a recorded ``sigma_method`` is emitted with ``sigma: null``, never a
      plausible-looking value.
    * **Every pulse carries ``origin``.** A matched filter's detection and a human's
      observation must not be averaged into one undifferentiated ground truth — a model
      scored against its own detections reports inflated agreement.
    * **``role`` is copied from the source's frozen meta**, where the importer recorded
      that it came from the filename — the same rule RELAY's own label_real.py uses.
      A ``negative`` capture with pulses in it is reported, not silently dropped.

    ALL RF sources are emitted, not just the first: the format's whole shape assumes one
    experiment spanning several captures, and exporting one would look complete while
    scoring against a fraction of the truth.
    """
    ...

def labels_json(deployment: Dict[str, Any], sources: Sequence[Dict[str, Any]], labels: Iterable[Dict[str, Any]]) -> str:
    """Everything, with provenance — the source of truth the other exports project from.

    Includes each label's absolute UTC span alongside its deployment-clock span, so the
    file is self-describing even if it is read years later without this codebase.
    """
    ...

def _parse_utc(value: Any) -> Optional[datetime]:
    """Best-effort ISO-8601 → aware UTC datetime. None if unparseable.

    Returns None rather than guessing a timezone: a UTC column that is silently the
    annotator's local time is worse than an empty one.
    """
    ...

def _iso(t0_utc: Optional[datetime], t_s: float) -> str:
    ...
