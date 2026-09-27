"""Stream F — sample readers for audio (WAV) and SDR (raw IQ).

Both readers are **random-access by sample index**: a labeler scrubbing hour 6 of a
mooring must not pay for hours 0–5. Everything here reads exactly the byte range a tile
needs and nothing more.

Stdlib + numpy only, on purpose. The production image has no ffmpeg, no soundfile and no
librosa (`Dockerfile` installs `libgl1 libglib2.0-0`), and adding an audio stack to ship
one feature would bloat every deploy including the ones that never enable it. HydroMoth
writes plain PCM WAV off the SD card and SDR captures are raw interleaved IQ, so stdlib
``wave`` plus ``numpy.memmap`` covers the real inputs without a single new wheel.

FLAC is deliberately unsupported. `hydromoth_pipeline` converts to FLAC at
``data/01_ingested/``, but the raw WAV in ``data/00_raw/`` is the immutable archival copy
and the honest thing to annotate.
"""
from __future__ import annotations
import os
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
import numpy as np
__all__ = ['AudioInfo', 'IQInfo', 'probe_wav', 'read_wav_samples', 'probe_iq', 'read_iq_samples', 'measure_dc_offset', 'IQ_DTYPES']

@dataclass(frozen=True)
class AudioInfo:
    path: str
    sample_rate_hz: int
    n_channels: int
    n_frames: int
    sample_width_bytes: int

    @property
    def duration_s(self) -> float:
        ...

def probe_wav(path: str | Path) -> AudioInfo:
    """Header-only read: rate, channels, length. Does not touch the audio body."""
    ...

def _pcm_to_float(raw: bytes, width: int, n_channels: int, channel: int) -> np.ndarray:
    """Decode interleaved PCM to mono float64 in [-1, 1).

    Handles the three widths AudioMoth/HydroMoth firmware actually emits (16-bit is the
    normal case) plus 32-bit for completeness. 24-bit is unpacked by hand because numpy
    has no 24-bit dtype.
    """
    ...

def read_wav_samples(path: str | Path, start_frame: int, n_frames: int, *, channel: int=0, info: Optional[AudioInfo]=None) -> np.ndarray:
    """Mono float64 samples ``[start_frame, start_frame+n_frames)``.

    Out-of-range requests are clipped rather than raising: a tile at the tail of a file
    legitimately asks for frames past the end, and zero-padding there is better than a
    500 on the last tile of every recording.
    """
    ...
DC_PROBE_SAMPLES = 4000000

@dataclass(frozen=True)
class IQInfo:
    path: str
    sample_rate_hz: float
    center_freq_hz: float
    iq_format: str
    n_samples: int
    dc_i: Optional[float] = None
    dc_q: Optional[float] = None

    @property
    def duration_s(self) -> float:
        ...

def measure_dc_offset(path: str | Path, iq_format: str, n_samples: int) -> tuple[float, float]:
    """Mean raw I and Q over a bounded head sample — the receiver's actual DC.

    Bounded because a 491 MB capture must not be read twice at ingest; the offset is a
    hardware property of the receiver and gain setting, stable across a capture, so a few
    million samples estimate it to well under a count.
    """
    ...

def probe_iq(path: str | Path, sample_rate_hz: float, center_freq_hz: float, iq_format: str='cs16', *, measure_dc: bool=False) -> IQInfo:
    """Sample count from file size.

    Raw IQ carries no header, so rate/centre/format must be declared by whoever captured
    it. They are stored on the source row rather than guessed — a wrong centre frequency
    silently relabels every VHF pulse onto the wrong tag.
    """
    ...

def read_iq_samples(path: str | Path, start_sample: int, n_samples: int, *, info: IQInfo) -> np.ndarray:
    """Complex128 IQ samples ``[start_sample, start_sample+n_samples)``.

    Uses a byte-offset ``np.fromfile`` so an arbitrarily large capture costs only the
    slice being viewed.
    """
    ...
