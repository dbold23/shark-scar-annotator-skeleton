"""Stream F — signal annotation core (acoustic waterfall, RF waterfall, biologging).

Pure computation: clock arithmetic, STFT lattices, decoders, tile rendering. No Flask, no
SQLite, no config — those live in ``annotation/db_signals.py`` and
``annotation/routes_signals.py``. Keeping this package I/O-free (beyond reading the media
files it is handed) is what lets the coordinate contract be tested exhaustively without a
database or an app context.

Mirrors the layout of the existing ``segmentation/`` package: heavy/optional work in its
own top-level package, thin blueprint + db module inside ``annotation/``.
"""
from signals.clock import SourceClock, clip_interval, drift_ppm_from_anchors, utc_of
from signals.spectro import SpectroGrid, stft_db
__all__ = ['SourceClock', 'SpectroGrid', 'clip_interval', 'drift_ppm_from_anchors', 'stft_db', 'utc_of']
