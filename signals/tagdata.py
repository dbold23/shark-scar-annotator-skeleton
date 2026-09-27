"""Stream F — biologging tag CSV readers (CATS, AXY-5, AXY-Depth).

Streaming and stdlib-only: `csv` + `numpy`, no pandas (the prod image has none). Every
rule below was measured against the lab's real files, not inferred from a vendor spec —
the comments name what was measured, because each one is a way the data lies.

**The timestamp column cannot be trusted.** That is the headline. On the Leopard Shark
AXY-5 export the printed timestamp is a *sawtooth*:

    printed(i) = t0 + 60*floor(i/60) + 2*(i mod 60)

which reproduces 56,185 of that file's 56,186 one-second runs. It is correct once a
minute, runs at 2x real time in between, then snaps back 58 s. Believing it mis-times
every interior sample by up to 59 s and overstates the record by 24 s. A behaviour label
placed against that axis is simply in the wrong place, and nothing downstream can tell.
So :func:`reconstruct_time` derives time from *row cadence* and uses the printed column
only as a coarse anchor — and refuses rather than guesses when the two disagree
irreconcilably.

**Records are not contiguous.** The one CATS chunk on disk holds 149,851 rows in three
50 Hz segments separated by gaps of 149,269 s and 8,134 s: 2,997 s of data inside a
160,400 s span. `t = i / rate` is wrong by up to 43 hours here. Readers therefore emit
*segments*, and the pyramid lattice is gap-aware.

Formats handled (they differ in every way they can):

| | delimiter | date | accel cols | units | sub-second | quirks |
|---|---|---|---|---|---|---|
| `cats` | `,` | `DD.MM.YYYY` | `Accelerometer X/Y/Z` | m/s² | real, per-sample | latin-1 header, leading spaces in 3 headers, slow channels step-held onto the 20 ms grid |
| `axy5` | `;` | `YYYY/MM/DD HH:MM:SS.fff` | `accX/Y/Z` | g | **sawtooth or real — varies by file** | 1 Hz sparse sub-carrier for mag/temp, ~1/120 Hz battery |
| `axy_depth` | `,` | `DD/MM/YYYY` | `X/Y/Z` | g | none (separate time col) | **ragged: 98% of rows have 7 fields, not 8** |

Canonical output channel names match `anchor.ingest.io.normalize_schema` exactly —
`accX/accY/accZ` (in g), `magX/Y/Z`, `gyroX/Y/Z`, `Depth`, `TempC`, `Battery`, `Speed` —
so a channel labelled here means the same thing it means in anchor-track.
"""
from __future__ import annotations
import csv
import io
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple
import numpy as np
__all__ = ['TagSchema', 'ChannelSpec', 'Segment', 'TagReader', 'sniff_schema', 'open_tag_csv', 'GRAVITY', 'CANONICAL_ORDER']
GRAVITY = 9.80665
GAP_FACTOR = 50.0

@dataclass(frozen=True)
class ChannelSpec:
    """One output channel: where it comes from and what it means."""
    name: str
    header: str
    unit: str
    scale: float = 1.0
    display_only: bool = False

@dataclass(frozen=True)
class TagSchema:
    name: str
    delimiter: str
    encoding: str
    date_fmt: str
    time_fmt: str
    date_header: Optional[str]
    time_header: str
    channels: Tuple[ChannelSpec, ...]

@dataclass
class Segment:
    """A contiguous run of samples. Gaps between segments are real dead time."""
    start_row: int
    n_rows: int
    t_start_s: float
    dt_s: float

    @property
    def t_end_s(self) -> float:
        ...

def _norm(h: str) -> str:
    """Normalise a header cell for matching: strip, collapse spaces, casefold."""
    ...

def _find(headers: Sequence[str], *candidates: str) -> Optional[int]:
    """Index of the first header equal to, then containing, any candidate."""
    ...

def sniff_schema(path: str | Path) -> str:
    """Identify the vendor schema from the header line alone.

    Sniffed, never declared, because a file's schema does not follow its branding:
    anchor's own config notes that an "APT/CATS clamp tag" deployment exported in AXY-5
    schema. Trusting the tag model would pick the wrong reader.
    """
    ...

@dataclass
class TimeModel:
    """How row index maps to seconds, and why we believe it."""
    mode: str
    rate_hz: float
    reason: str
    t0_utc: Optional[datetime] = None
    max_residual_s: float = 0.0

def _snap(dt: float, rel_tol: float=1e-06) -> float:
    """Snap a regressed sample interval to the clean value it is, within a relative tol.

    A dt regressed over a segment comes out as 0.019999999995486635 or 0.04000000000002
    rather than 0.02 / 0.04. Physically that is nothing — nanoseconds over the whole
    record — but it is NOT harmless downstream: the pyramid derives bin indices from
    `seg.dt_s / lattice.dt_s`, and a ratio of 0.99999999977 instead of exactly 1 makes
    floor() collide roughly 3% of rows into a neighbouring bin, leaving the trace
    stippled with one-pixel holes.

    The tolerance is RELATIVE (absolute 1e-12 never fires on these values, which is how
    the stippling survived the first import). At 1e-6 only sub-20 ns differences snap, so
    a genuinely different rate is never rounded into a neighbouring one.
    """
    ...

def _parse_dt(schema: TagSchema, date_s: str, time_s: str) -> Optional[datetime]:
    ...

def detect_sawtooth(labels: np.ndarray) -> Tuple[bool, str]:
    """Is this printed-timestamp series the AXY-5 sawtooth?

    Signature measured on the Leopard file: run-to-run deltas are overwhelmingly +2.0 s
    with a regular -58.0 s snap-back, i.e. the label advances at 2x real time and resets
    every minute. Any negative delta in a series that is otherwise increasing is enough
    to disqualify the column as a time source — a real record's labels never go
    backwards (the sole exception, the AXY-Depth power-off terminator, is dropped before
    this runs).
    """
    ...

class TagReader:
    """Streaming reader over one tag CSV.

    Two passes by design, and the cost is justified: pass 1 establishes the time model
    (true rate, segments, t0) because the printed column cannot be trusted to give it;
    pass 2 streams values into whatever consumer wants them. Neither pass holds more
    than one chunk in memory, so a 934 MB / 13.9M-row AXY-Depth file works in a few
    hundred MB.
    """

    def __init__(self, path: str | Path, schema_name: Optional[str]=None):
        ...

    def _read_header(self) -> None:
        ...

    def _rows(self) -> Iterator[List[str]]:
        """Yield data rows, dropping the synthetic power-off terminator.

        Every AXY export ends with an all-zero accel row carrying 'Power off command
        received.'; in AXY-Depth its timestamp also regresses 0.98 s. It is a shutdown
        marker, not a measurement, and it corrupts both kinematics and monotonicity
        checks if kept.
        """
        ...

    def _cell(self, row: List[str], idx: Optional[int]) -> str:
        ...

    def build_time_model(self, progress: Optional[Callable[[int], None]]=None) -> TimeModel:
        """Establish true sample rate, segments and t0 — the load-bearing pass."""
        ...

    def _segments_from_labels(self, lab: np.ndarray, rows: np.ndarray, n_rows: int, t0_utc: Optional[datetime]) -> TimeModel:
        """Split into contiguous segments on real gaps, deriving dt within each.

        The one CATS chunk on disk is three 50 Hz runs separated by 149,269 s and
        8,134 s. Treating it as one stream puts 50 minutes of data on a 44-hour axis.
        """
        ...

    def iter_chunks(self, chunk_rows: int=200000, progress: Optional[Callable[[int], None]]=None) -> Iterator[Tuple[int, Dict[str, np.ndarray]]]:
        """Yield ``(start_row, {channel: float64 array with NaN for blanks})``.

        NaN, never 0.0, for a blank cell. The AXY sparse columns (mag/temp on the first
        row of each 25-row second, battery every ~120 s) are a genuine lower-rate
        sub-carrier, not missing data — filling them with zero would draw a magnetometer
        lane that spikes to zero 24 times a second.
        """
        ...

    def row_times_s(self, start_row: int, count: int) -> np.ndarray:
        """Seconds-from-first-sample for a row range, honouring segment gaps."""
        ...

    @property
    def duration_s(self) -> float:
        ...

def open_tag_csv(path: str | Path, schema_name: Optional[str]=None) -> TagReader:
    """Convenience constructor."""
    ...

def rolling_static(x: np.ndarray, win: int) -> np.ndarray:
    """Centred moving-average estimate of the static (gravity) component.

    A moving average, NOT the Butterworth `anchor.kinematics.core.lowpass_filter` uses —
    scipy is not available in this image. The two do not produce identical numbers, which
    is exactly why anything derived from this is marked display-only and excluded from
    every export: a lane that helps a labeler find bouts must never be mistaken for
    anchor's ODBA.
    """
    ...

def odba_display(ax: np.ndarray, ay: np.ndarray, az: np.ndarray, rate_hz: float) -> np.ndarray:
    """Overall Dynamic Body Acceleration, for the dock only.

    Wilson et al. (2006): ODBA = |x_dyn| + |y_dyn| + |z_dyn|, where dynamic = raw minus
    the static component. Window is 2 s, a middle-of-the-road stand-in for the
    species-specific `lowpass_cutoff_hz` anchor carries per species (0.5 Hz for white
    shark). Because that cutoff is a science parameter we do not have here, this value is
    an activity *indicator* for finding bouts, not a measurement to report.
    """
    ...
