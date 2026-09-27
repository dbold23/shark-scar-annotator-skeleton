"""Stream F — waterfall tile rendering.

Tiles are rendered **server-side** with the source's frozen grid and dB range. That is a
deliberate choice over a browser Web Audio FFT: with 10+ labelers, two people must see
the same pixels for the same source, and a box's meaning must not depend on whichever FFT
size a client happened to pick. The render parameters live on the source row, so a tile
regenerated next semester is byte-identical to the one somebody annotated today.

Brightness/contrast stays client-side (a CSS filter on the tile) — that is a viewing
preference and must never change the stored coordinates.

Palette PNGs (mode ``P``, 256 colours) rather than RGB: ~3× smaller over the wire for
identical appearance, which matters when scrubbing a long mooring pulls dozens of tiles.
Pillow is already a dependency; nothing new is added.
"""
from __future__ import annotations
import io
from typing import Dict, Tuple
import numpy as np
from PIL import Image
__all__ = ['COLORMAPS', 'TILE_FRAMES', 'render_tile_png', 'quantize_db', 'n_tiles_for']
TILE_FRAMES = 512

def _interp_palette(anchors: list[tuple[float, float, float]]) -> bytes:
    """Linearly interpolate anchor RGB triplets to a flat 256×3 palette."""
    ...

def _gray_palette(reverse: bool=False) -> bytes:
    ...

def n_tiles_for(n_frames: int, tile_frames: int=TILE_FRAMES) -> int:
    """Tile count covering ``n_frames`` columns."""
    ...

def quantize_db(db: np.ndarray, db_lo: float, db_hi: float) -> np.ndarray:
    """Map a dB matrix onto 0–255, clipped to ``[db_lo, db_hi]``.

    A degenerate range collapses to a flat mid-grey rather than dividing by zero — a flat
    tile is a legible "nothing here", a traceback is not.
    """
    ...

def render_tile_png(db: np.ndarray, db_lo: float, db_hi: float, *, colormap: str=DEFAULT_COLORMAP, pad_to_width: int | None=None) -> bytes:
    """Render a ``[n_bins, n_frames]`` dB matrix to a palette PNG.

    Row 0 of the output image is the **highest** frequency — the waterfall convention
    that `SpectroGrid.row_to_bin` assumes. The flip happens exactly here, once, so no
    caller has to remember it.

    ``pad_to_width`` right-pads a short final tile with the floor colour so every tile in
    a source has identical pixel width; the client can then position tiles by index
    without a special case for the last one.
    """
    ...

def tile_frame_range(tile_index: int, n_frames: int, tile_frames: int=TILE_FRAMES) -> Tuple[int, int]:
    """Half-open frame range ``[first, last)`` covered by ``tile_index``."""
    ...
