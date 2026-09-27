"""Stream F — gap-aware min/max channel pyramids.

The property this module exists to guarantee:

> The ink drawn in pixel column *x* of a sensor lane spans exactly ``[min, max]`` of the
> true samples whose times fall in the half-open interval that column covers — at every
> zoom level, with no interpolation and no dropped sample.

Everything else is a consequence. The pyramid is a ladder of min/max envelopes: level 0
bins raw samples onto a fixed lattice, and each level above is a 4x **exact** reduction
of the level below (``min`` of mins, ``max`` of maxes). Because reduction is exact, a
one-sample transient — a strike, which is precisely what a behaviour labeler is hunting —
survives to the coarsest level instead of being averaged into the background.

Two design points worth stating because their opposites are the obvious choice:

**Bins are edge-stamped and half-open**, ``[t0 + k*dt, t0 + (k+1)*dt)`` — deliberately
unlike ``SpectroGrid``, which centre-stamps STFT frames. A spectrogram frame *is* centred
on its window; a min/max bin is an interval, and centre-stamping one would be a half-bin
lie about when a transient happened.

**One lattice per source, shared by every channel**, never per channel. AXY-5 populates
mag/temp on the first row of each 25-row second and battery every ~120 s; CATS step-holds
depth and light onto its 20 ms grid. If each channel had its own lattice, one x-pixel
would land on a different bin index per lane and the lanes would silently de-align — the
one error a labeler comparing accel against depth would never spot.

Gaps are first-class. The one CATS chunk on disk is three 50 Hz runs separated by 41 h
and 2.3 h; binning it on a naive uniform lattice would allocate 8 million empty bins to
hold 150k samples. Instead each :class:`Segment` gets its own contiguous bin range and
the lattice records where they sit, so dead time costs nothing and is drawn as a gap
rather than as a flat line at zero.

numpy + stdlib only.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple
import numpy as np
__all__ = ['Lattice', 'LatticeSegment', 'PyramidWriter', 'read_tile', 'NODATA', 'TILE_BINS', 'LEVEL_RATIO', 'robust_range', 'choose_level']
TILE_BINS = 4096
LEVEL_RATIO = 4

@dataclass(frozen=True)
class LatticeSegment:
    """One contiguous run of bins, and the deployment-clock time it starts at."""
    bin_start: int
    n_bins: int
    t_start_s: float

    @property
    def bin_end(self) -> int:
        ...

@dataclass(frozen=True)
class Lattice:
    """The frozen binning of one sensor source. Stored on `signal_sources.meta_json`.

    Frozen for the same reason `SpectroGrid` is: a labeler's interval was drawn against
    *these* bins. Re-derive them later with a different `dt_s` and every stored label
    silently refers to a lattice that no longer exists.
    """
    dt_s: float
    n_bins: int
    tile_bins: int
    segments: Tuple[LatticeSegment, ...]
    levels: Tuple[int, ...]

    @classmethod
    def from_segments(cls, segs: Sequence[Tuple[float, float, int]], dt_s: float, tile_bins: int=TILE_BINS) -> 'Lattice':
        """Build from ``(t_start_s, dt_within_s, n_rows)`` per source segment."""
        ...

    def bin_to_time_s(self, bin_index: float) -> float:
        """Left-edge source-clock time of a level-0 bin."""
        ...

    def time_to_bin(self, t_s: float) -> Optional[float]:
        """Level-0 bin containing ``t_s``. None when the time lies inside a gap."""
        ...

    def n_bins_at(self, level: int) -> int:
        ...

    def n_tiles_at(self, level: int) -> int:
        ...

    def dt_at(self, level: int) -> float:
        ...

    @property
    def span_s(self) -> float:
        ...

    def to_manifest(self) -> dict:
        ...

    @classmethod
    def from_manifest(cls, d: dict) -> 'Lattice':
        ...

    def hash(self) -> str:
        """Short stable digest of the lattice.

        Goes in the tile URL PATH, not just an ETag. That is what makes a re-import safe:
        a browser holding an old manifest requests the old hash, gets a 404, and refetches
        the manifest — instead of decoding new bytes against an old lattice and drawing a
        trace that is wrong in both value and time with no error anywhere.
        """
        ...

def robust_range(values: np.ndarray, lo_pct: float=0.5, hi_pct: float=99.5) -> Tuple[float, float]:
    """Display range from percentiles, never exact extremes.

    Measured: magnetometer exact extremes run 20-100x the robust range on every channel
    in the corpus (Leopard magZ exact min -28,065 vs p0.1 -576; BatRay magY exact max
    25,836 vs p99.9 256). Scaling a lane to the exact min/max renders it as a flat line
    with one spike — technically faithful and completely unreadable.
    """
    ...

def choose_level(lattice: Lattice, span_s: float, px: int) -> int:
    """Coarsest level still giving at least one bin per pixel.

    Targets 1-4 bins/pixel so a lane reads a bounded number of bytes whether the labeler
    is looking at one second or three days.
    """
    ...

@dataclass
class _Header:
    n_levels: int
    tile_bins: int
    level_bins: List[int]

    def offsets(self) -> List[int]:
        ...

    def total_bytes(self) -> int:
        ...

def _write_header(fh, lattice: Lattice) -> None:
    ...

def _read_header(fh) -> _Header:
    ...

class PyramidWriter:
    """Accumulates level-0 min/max for one channel, then writes the whole ladder.

    Level 0 is held in memory as two float32 arrays. That is the deliberate memory
    ceiling: at dt = 0.02 s a 3.2-day AXY-Depth record is 13.9M bins = 111 MB for both
    planes, which fits comfortably in a detached import process and keeps the writer a
    few dozen lines instead of an external merge sort.
    """

    def __init__(self, lattice: Lattice):
        ...

    def add(self, bins: np.ndarray, values: np.ndarray) -> None:
        """Fold a chunk of samples into their level-0 bins.

        ``np.minimum.at`` is an unbuffered scatter-reduce: repeated bin indices each
        apply, which is what makes the result exact rather than last-write-wins.
        """
        ...

    def finalize(self) -> Tuple[np.ndarray, np.ndarray]:
        ...

    def base_level_for(self, native_dt_s: float) -> int:
        """Coarsest level whose bins are still no wider than the channel's own sampling.

        A sparse channel must not pay for the dense lattice. Battery is sampled about
        every 120 s; on a 25 Hz record that is 469 real values spread over 1.4M bins, and
        storing it at level 0 costs 15 MB to hold 469 numbers.

        Because levels are exact powers of `LEVEL_RATIO` of the SHARED lattice, starting
        a channel at level L keeps it perfectly aligned with every other lane: its bin k
        covers shared bins [k*ratio^L, (k+1)*ratio^L). Alignment is preserved by
        construction, not by convention — which is the whole reason all channels share
        one lattice in the first place.
        """
        ...

    def write(self, path: str | Path, base_level: int=0) -> dict:
        """Write the ladder atomically, starting at ``base_level``.

        The file's level 0 is the shared lattice's ``base_level``; the client subtracts
        the offset (published in the manifest) when requesting a level.
        """
        ...

def _reduce(arr: np.ndarray, ratio: int, op) -> np.ndarray:
    """Exact ``ratio``-fold reduction, NaN-skipping, padding the tail with NaN.

    ``np.fmin``/``np.fmax`` (not ``minimum``/``maximum``) so a NaN in a group is ignored
    rather than poisoning the whole group to NaN — otherwise one empty bin would erase
    three real ones at every level above.
    """
    ...

def read_tile(path: str | Path, level: int, tile_index: int) -> bytes:
    """Raw bytes of one tile: ``tile_bins`` interleaved little-endian float32 min/max.

    A pure byte-range read — the server never interprets the payload, and the browser
    decodes it with ``new Float32Array(buf)`` and no dependency. Short final tiles are
    NaN-padded to a uniform width so the client can position by index alone.
    """
    ...
