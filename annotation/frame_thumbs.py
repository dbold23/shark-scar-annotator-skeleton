"""Small cached JPEGs of a single frame — what the fed queue card shows.

The queue hands a labeler one card at a time, and a filename plus a sentence of
gap-reason prose does not tell anybody what they are about to open. A thumbnail
does, in less space.

Two rules shape this module:

  * **It never fetches media.** Rendering a thumbnail is worth a disk read and a
    seek; it is not worth pulling 500 MB from Drive. If the video is not already
    in the local cache the caller gets ``None`` and the card falls back to a
    placeholder — and the download happens anyway the moment the labeler opens
    the item. Same stance as ``GET /api/tracks/<id>/preview``, which returns 409
    rather than fetching (``app.py``).
  * **The cache key is the frame, not the item.** Two work items on the same
    (video, frame) — an overlap pair, a re-queued candidate — are the same
    picture, and a per-item cache would render it twice and store it twice.

Pure enough to unit-test: no Flask, no DB, no config. cv2 and numpy are imported
inside the render call so importing this module stays cheap for callers that only
need a cache path.
"""
from __future__ import annotations
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write a cache file so a concurrent reader never sees it half-written.

    ``Path.write_bytes`` opens with 'wb', which TRUNCATES first. With four gunicorn
    workers that is a live hazard, not a theoretical one: ``send_file`` stats the
    file to set Content-Length, another worker re-renders the same frame and
    truncates it, and the response body comes up empty against a header promising
    2.8 KB. Measured on a 15-student run: 1-4 of every 600 thumbnail requests died
    with ``IncompleteRead(0 bytes read, 2783 more expected)`` — the labeler sees a
    broken card for no reason they could ever report usefully.

    ``os.replace`` is atomic on POSIX and a reader holding the old fd keeps reading
    the old inode, so both the "before" and "after" states are complete files and
    there is no "during". Same reasoning as ``auth._atomic_write_json``.
    """
    ...
THUMB_WIDTH = 320
JPEG_QUALITY = 72

def _safe_key(value: str) -> str:
    """A filesystem-safe directory name for an arbitrary video id.

    video_id reaches us from the DB, but it originates in a CSV import, so it is
    caller-supplied data and must never be pasted into a path unescaped.
    """
    ...

def cache_path(cache_root: Path, video_id: str, frame_number: Optional[int]) -> Path:
    """Where this frame's thumbnail lives. Frameless media (a still image
    assignment) caches under ``full.jpg``."""
    ...

def render(media_path: Path, frame_number: Optional[int], *, width: int=THUMB_WIDTH) -> Optional[bytes]:
    """Decode one frame and return it as a small JPEG. ``None`` on any failure.

    Failure is returned, not raised: a thumbnail is decoration. A corrupt file or
    a frame number past the end of a clip must degrade to a placeholder, never
    take the queue down.
    """
    ...

def write_jpeg(cache_root: Path, video_id: str, frame_number: Optional[int], jpeg_bytes: bytes) -> Optional[Path]:
    """Seed the cache from a JPEG we already hold, downscaling it first.

    Used when a gold answer is authored: the annotator client already captured
    that exact frame (``frame_image_b64``), so the answer key gets a thumbnail for
    free — and, unlike an ordinary queue item, gets one even when the clip is not
    on this box. The frame a labeler is about to be marked on is the last one that
    should show a grey placeholder.
    """
    ...

def ensure(cache_root: Path, video_id: str, frame_number: Optional[int], media_path: Optional[Path]) -> Optional[Path]:
    """Return the cached thumbnail path, rendering it first if need be.

    ``None`` means "no thumbnail is available right now" — either the media is not
    in the local cache or the frame could not be read. Both are ordinary states,
    not errors.
    """
    ...
