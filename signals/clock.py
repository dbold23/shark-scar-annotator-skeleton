"""Stream F — the deployment clock.

**Every label in this stream is stored as seconds on the deployment clock.** Nothing is
stored as a frame number. That is not a style preference: this repo already lost a day to
a client-side `fps` guess (30 fps hardcoded against a 59.94 fps video) putting the scar
tracker on the wrong frame, and `static/js/video_player.js` still derives frames from an
*estimated* fps. Seconds are the only quantity every source agrees on.

The model is deliberately the same one `anchor-track` uses
(`anchor.behavior.labels.align_to_accel`): a single scalar offset per source. If the two
systems model time the same way, they agree by construction instead of by conversion.

    deployment t0 ──┬── video   starts at t0 + 12.5 s   (t0_offset_s = +12.5)
                    ├── audio   starts at t0 −  3.0 s   (t0_offset_s = -3.0)
                    └── accel   starts at t0            (t0_offset_s =  0.0)

Optional linear clock drift handles the case the HydroMoth pipeline flagged as easy to
get wrong: an RTC that drifts ~2 s/day is minutes over a multi-month mooring, and GPS
sync cannot run submerged (`telemetry/Audio/src/hydromoth_pipeline/timestamps.py`). Drift
is modelled linearly between two anchor points, exactly as that module does.

Pure stdlib — no numpy, no I/O. Everything here is a total function so it can be tested
exhaustively.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Tuple
__all__ = ['SourceClock', 'drift_ppm_from_anchors', 'clip_interval', 'clip_intervals', 'utc_of']

@dataclass(frozen=True)
class SourceClock:
    """Maps one source's own timeline onto the deployment timeline.

    Args:
        t0_offset_s: source start minus deployment t0, in seconds. Positive when the
            source started *after* the deployment origin. May be negative.
        drift_ppm: parts-per-million the source clock runs fast. Positive means the
            device clock advances faster than true time, so a device-reported elapsed
            time of ``t`` corresponds to a true elapsed time of ``t / (1 + ppm/1e6)``.
        duration_s: the source's own duration, if known. Used for clipping.
    """
    t0_offset_s: float = 0.0
    drift_ppm: float = 0.0
    duration_s: Optional[float] = None

    def to_deployment(self, t_source_s: float) -> float:
        """Convert a time on this source's own clock to the deployment clock."""
        ...

    def to_source(self, t_deployment_s: float) -> float:
        """Convert a deployment-clock time back to this source's own clock.

        Exact inverse of :meth:`to_deployment` for every finite input, which is what
        makes a label round-trip through the UI without creeping.
        """
        ...

    def _detrend(self, t: float) -> float:
        """Device-reported elapsed seconds → true elapsed seconds."""
        ...

    def _retrend(self, t: float) -> float:
        """True elapsed seconds → device-reported elapsed seconds."""
        ...

    def span_on_deployment(self) -> Optional[Tuple[float, float]]:
        """The (start, end) this source covers on the deployment clock, if known."""
        ...

    def covers(self, t_deployment_s: float) -> bool:
        ...

def drift_ppm_from_anchors(device_elapsed_s: float, true_elapsed_s: float) -> float:
    """Linear drift rate from two paired clock readings (deploy and recovery).

    ``device_elapsed_s`` is what the device's own clock thinks elapsed between the two
    anchors; ``true_elapsed_s`` is what actually elapsed. A device that reports 86500 s
    over a true 86400 s day is running fast by ~1157 ppm.

    Raises ValueError on a non-positive true interval — a zero-length anchor pair cannot
    constrain a rate, and silently returning 0.0 would hide a bad calibration.
    """
    ...

def clip_interval(start_s: float, end_s: float, duration_s: Optional[float]) -> Optional[Tuple[float, float]]:
    """Clip one interval to ``[0, duration_s]``; None if it falls entirely outside.

    Mirrors the semantics of ``anchor.behavior.labels.align_to_accel``: intervals wholly
    outside the record are dropped, intervals straddling an edge are clipped to it. Kept
    behaviourally identical on purpose so a label exported from here and re-imported
    there survives the trip unchanged.
    """
    ...

def clip_intervals(intervals: Iterable[Tuple[float, float]], duration_s: Optional[float]) -> list[Tuple[float, float]]:
    """Vectorless :func:`clip_interval` over an iterable, dropping what falls outside."""
    ...

def utc_of(t0_utc: datetime, t_deployment_s: float) -> datetime:
    """Absolute UTC timestamp of a deployment-clock offset.

    Requires a timezone-aware ``t0_utc``. A naive datetime here is how an archive ends up
    silently shifted by the annotator's local offset, so it is refused rather than
    guessed — the same rule `hydromoth_pipeline.timestamps` applies.
    """
    ...
