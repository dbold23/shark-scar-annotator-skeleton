"""LRU eviction for the tmp_videos disk cache.

Pure filesystem logic (no cv2 / Flask / DB imports) so it is fast to unit-test.
The app wraps this with config + a DB callback in app.py.

"Recently used" = file mtime, which the serve routes bump on each playback
(os.utime), so oldest-mtime-first is true LRU rather than mere download order.
"""
import shutil
import time
from pathlib import Path
from typing import Callable, List, Optional

def free_bytes(cache_dir) -> Optional[int]:
    """Free bytes on the filesystem holding `cache_dir`, or None if unknowable.

    Unlike the size total inside `evict_lru`, this DOES see the bytes of
    in-flight `.download` partials, because the filesystem does.
    """
    ...

def has_free_space(cache_dir, min_free_bytes: float) -> bool:
    """True if the volume still has at least `min_free_bytes` free.

    Cheap enough (one statvfs) to call from inside a download's chunk loop.
    `evict_lru` enforces the floor at exactly one instant — before the first
    byte is written — and nothing re-checks it while an unbounded number of
    concurrent downloads write through it. Once every completed file has been
    evicted there is nothing left to free, so the writes run past the floor to
    ENOSPC on a volume that also holds catalog.db. A writer must therefore
    re-check as it goes and abort its own partial rather than fill the disk.
    """
    ...

def evict_lru(cache_dir, max_bytes: float, min_free_bytes: float, keep_name: Optional[str]=None, partial_suffix: str='.download', partial_max_age_sec: float=3600, on_evict: Optional[Callable[[Path], None]]=None) -> List[Path]:
    """Evict least-recently-used files from `cache_dir` until the cache is within
    both limits: total size <= max_bytes AND free disk >= min_free_bytes.

    - Only files DIRECTLY in cache_dir are considered; subdirectories (e.g.
      pose_frames/) are never touched.
    - `keep_name` (the file about to be used) is never evicted.
    - Stale `<partial_suffix>` files older than `partial_max_age_sec` (abandoned
      partial downloads) are removed regardless of the size check.
    - `on_evict(path)` is called after each deletion (e.g. to clear a DB path).
    - Deleting a file that is mid-stream is safe on POSIX: the open fd keeps
      serving the now-unlinked inode until the request finishes.

    Returns the list of evicted file paths (excludes cleaned partials).
    """
    ...
