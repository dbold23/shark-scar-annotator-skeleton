"""Stream F — the time–frequency grid, and the STFT that fills it.

This module is the **coordinate contract** for every waterfall label. A box drawn on a
rendered tile has to come back as the (time, frequency) rectangle the labeler actually
saw — otherwise the export ingests into OpenSoundscape or PAMGuard without complaint and
publishes wrong numbers forever. That silent-misalignment failure is exactly the class of
bug the Darwin Core work caught late (core column indexes shifted by one against their
term URIs), so the grid is made explicit, frozen onto the source row, and asserted by a
synthetic round-trip test rather than eyeballed.

Two conventions, both published in the API manifest so the browser does the pixel→(t,f)
arithmetic itself and the server never has to reverse-engineer a pixel:

* **Frame i is stamped at its centre**, ``t_i = (i*hop + n_fft/2) / sr`` seconds on the
  source's own clock. Centre-stamping is what Raven, librosa and PAMGuard all report; the
  alternative (left edge) biases every annotation half a window early.
* **Bin k is a frequency, not a band.** Real input gives ``f_k = k*sr/n_fft`` for
  ``k = 0 … n_fft/2``. Complex IQ input is fft-shifted and gives
  ``f_k = centre + (k − n_fft/2)*sr/n_fft`` for ``k = 0 … n_fft−1``, which is what puts a
  VHF tag pulse on a real MHz axis instead of a baseband one.

numpy only — no scipy, no librosa. The production image has neither
(`Dockerfile` installs `libgl1 libglib2.0-0` and nothing else), and this stream is not
worth a dependency.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
__all__ = ['SpectroGrid', 'hann_periodic', 'stft_db', 'samples_needed_for_frames']
_EPS = 1e-12

@dataclass(frozen=True)
class SpectroGrid:
    """The frozen time–frequency lattice of one source.

    Persisted verbatim onto ``signal_sources.meta_json`` at ingest. It must never be
    recomputed from defaults at read time: change ``n_fft`` after boxes exist and every
    stored label silently refers to a lattice that no longer exists.
    """
    sample_rate_hz: float
    n_fft: int
    hop: int
    n_frames: int
    complex_input: bool = False
    center_freq_hz: float = 0.0

    def __post_init__(self) -> None:
        ...

    @property
    def n_bins(self) -> int:
        """Rows in the spectrogram: one-sided for real audio, two-sided for IQ."""
        ...

    @property
    def duration_s(self) -> float:
        """Seconds spanned by the framed region (last frame centre + half a window)."""
        ...

    @property
    def hz_per_bin(self) -> float:
        ...

    @property
    def seconds_per_frame(self) -> float:
        ...

    def frame_time_s(self, frame: float) -> float:
        """Centre time of ``frame`` in seconds on the source's own clock."""
        ...

    def time_to_frame(self, t_s: float) -> float:
        """Inverse of :meth:`frame_time_s`. Returns a float — do not round early."""
        ...

    def bin_freq_hz(self, k: float) -> float:
        """Centre frequency of bin ``k``.

        Real input is baseband one-sided. Complex input is fft-shifted, so bin
        ``n_fft/2`` sits exactly on the tuned centre frequency.
        """
        ...

    def freq_to_bin(self, f_hz: float) -> float:
        """Inverse of :meth:`bin_freq_hz`. Returns a float — do not round early."""
        ...

    @property
    def freq_range_hz(self) -> Tuple[float, float]:
        ...

    def row_to_bin(self, row: float) -> float:
        ...

    def bin_to_row(self, k: float) -> float:
        ...

    def to_manifest(self) -> dict:
        """The exact numbers the browser needs to map a pixel to (t, f) itself."""
        ...

    @classmethod
    def from_manifest(cls, d: dict) -> 'SpectroGrid':
        ...

    @classmethod
    def for_samples(cls, n_samples: int, sample_rate_hz: float, n_fft: int, hop: int, *, complex_input: bool=False, center_freq_hz: float=0.0) -> 'SpectroGrid':
        """Build the grid a given sample count supports (no zero-padding, no partial frames)."""
        ...

def hann_periodic(n: int) -> np.ndarray:
    """Periodic (DFT-even) Hann window.

    ``np.hanning`` is the *symmetric* variant, which is correct for filter design and
    subtly wrong for spectral analysis — it leaks slightly and is not what Raven or
    librosa use. One line, worth getting right.
    """
    ...

def samples_needed_for_frames(grid: SpectroGrid, first_frame: int, n_frames: int) -> Tuple[int, int]:
    """Half-open sample range ``[start, stop)`` backing a frame window.

    Lets a caller read one tile's worth of a multi-hour file instead of the whole thing —
    the difference between a mooring that opens instantly and one that OOMs a worker.
    """
    ...

def stft_db(samples: np.ndarray, grid: SpectroGrid, *, n_frames: Optional[int]=None, ref_db: float=0.0) -> np.ndarray:
    """Power spectrogram in dB for ``samples``, laid out ``[n_bins, n_frames]``.

    ``samples`` must start exactly at the first frame's first sample (use
    :func:`samples_needed_for_frames` to slice). Real input takes ``rfft``; complex IQ
    input takes a full ``fft`` plus ``fftshift`` so the tuned centre lands mid-axis.

    Returns dB relative to unit amplitude, offset by ``ref_db`` (a calibration hook —
    HydroMoth units are not factory-calibrated underwater, so absolute SPL stays the
    caller's problem, exactly as `hydromoth_pipeline` insists).
    """
    ...
DC_GUARD_BINS = 6

def auto_db_range(db: np.ndarray, lo_pct: float=30.0, range_db: float=70.0, cap_pct: float=99.99, *, exclude_center_bins: int=0) -> Tuple[float, float]:
    """Display range anchored to the noise floor, with a fixed dynamic range above it.

    The floor is a low percentile (robust: a mooring's ambient varies by tens of dB
    between a calm night and a passing vessel, and SDR gain settings move it wholesale),
    and the ceiling sits a fixed span above it, capped by the data's own near-maximum.

    Anchoring the *floor* rather than the ceiling is the load-bearing choice. A high
    percentile ceiling collapses as soon as the interesting events are sparse: a one-
    second tone in a ten-minute recording is ~0.4% of the pixels, so a 99.5th-percentile
    ceiling lands far below it and everything even mildly above ambient blows out to
    white. Floor-anchoring keeps ambient dark and lets genuinely loud events saturate,
    which is what a labeler needs to see.

    ``lo_pct`` defaults to the 30th percentile rather than something like the 5th because
    ambient occupies most of a mooring's pixels: measured on a test recording, moving the
    floor from p5 to p30 dropped the mean ambient pixel from 44 to 16 while a dolphin-
    style whistle's 95th-percentile pixel only fell from 140 to 121 — a darker background
    *and* better separation. Below roughly p30 the whole image washes out to mid-purple
    and faint structure gets harder, not easier, to see.

    The values chosen here are frozen onto the source row, so the render a box was drawn
    on stays reproducible regardless of what this function does in a later release.
    """
    ...
