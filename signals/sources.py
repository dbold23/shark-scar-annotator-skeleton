"""Stream F — the source facade: probe once at ingest, render tiles forever after.

Splits cleanly in two, and the split is the whole point:

* :func:`probe_audio_source` / :func:`probe_rf_source` run **once, at ingest**. They read
  the header, choose an FFT lattice, sample the file to pick a display range, and freeze
  all of it into a dict that gets stored on ``signal_sources.meta_json``.
* :func:`render_tile` runs on **every tile request** and reads those frozen numbers back.
  It never re-derives anything.

That asymmetry is what keeps annotations valid. If the tile route recomputed a "sensible
default" n_fft, then bumping a default in a later release would silently move every
stored box relative to the pixels somebody drew it on — the annotation would still load,
still export, and be wrong. Freezing the lattice makes that impossible by construction.
"""
from __future__ import annotations
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np
from signals import decode
from signals.spectro import DC_GUARD_BINS, SpectroGrid, auto_db_range, samples_needed_for_frames, stft_db
from signals.tiles import DEFAULT_COLORMAP, TILE_FRAMES, n_tiles_for, render_tile_png, tile_frame_range
__all__ = ['SourceSpec', 'probe_audio_source', 'probe_rf_source', 'render_tile', 'DEFAULT_AUDIO_NFFT', 'DEFAULT_AUDIO_OVERLAP']
DEFAULT_AUDIO_NFFT = 1024
DEFAULT_AUDIO_OVERLAP = 0.5
DEFAULT_RF_NFFT = 4096
DEFAULT_RF_OVERLAP = 0.5
MAX_RF_HZ_PER_BIN = 1000.0
MAX_NFFT = 8192
_RANGE_PROBE_CHUNKS = 8
_RANGE_PROBE_FRAMES = 64

@dataclass
class SourceSpec:
    """Everything needed to render a tile, and nothing that can drift."""
    kind: str
    path: str
    grid: SpectroGrid
    db_lo: float
    db_hi: float
    channel: int = 0

    @property
    def n_tiles(self) -> int:
        ...

    def to_meta(self) -> Dict[str, Any]:
        """Serialize for ``signal_sources.meta_json``."""
        ...

    @classmethod
    def from_meta(cls, meta: Dict[str, Any], path: str) -> 'SourceSpec':
        ...

def _hop_from_overlap(n_fft: int, overlap: float) -> int:
    ...

def _estimate_db_range(read_chunk, grid: SpectroGrid, *, exclude_center_bins: int=0) -> tuple[float, float]:
    """Percentile display range from chunks spread across the whole record."""
    ...

def probe_audio_source(path: str | Path, *, n_fft: int=DEFAULT_AUDIO_NFFT, overlap: float=DEFAULT_AUDIO_OVERLAP, channel: int=0, colormap: str=DEFAULT_COLORMAP, tile_frames: int=TILE_FRAMES) -> SourceSpec:
    """Read a WAV header, freeze its lattice, and pick a display range."""
    ...

def probe_rf_source(path: str | Path, *, sample_rate_hz: float, center_freq_hz: float, iq_format: str='cs16', n_fft: int=DEFAULT_RF_NFFT, overlap: float=DEFAULT_RF_OVERLAP, colormap: str=DEFAULT_COLORMAP, tile_frames: int=TILE_FRAMES) -> SourceSpec:
    """Freeze the lattice for a raw IQ capture.

    ``sample_rate_hz``/``center_freq_hz``/``iq_format`` cannot be inferred — raw IQ has no
    header — so they are required arguments rather than defaulted. A wrong centre would
    put every labelled pulse on the wrong tag frequency and nothing downstream would
    notice.
    """
    ...

def render_tile(spec: SourceSpec, tile_index: int) -> bytes:
    """Render one waterfall tile as PNG bytes using only the frozen spec."""
    ...
