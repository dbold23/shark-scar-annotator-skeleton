"""Decode the media a labeler is about to be given, before they ask for it.

The fed queue knows the next few items the moment it leases them. Decoding their
frames then — while somebody is still working the current card — is the difference
between an instant open and a seven-second stare at an empty canvas. The 4K HEVC
clips here take 7-15s to sample, and no amount of client-side cleverness hides
that: a fetch fired when the card renders competes with the labeler's own requests
and can only ever warm what is already on screen.

Design constraints, because this runs on a shared box:

  * ONE decode at a time per process. A thread pool would turn four gunicorn
    workers into eight concurrent ffmpeg decodes and make the app slower than not
    warming at all.
  * NEVER block a request. Submission is a queue push; a full queue drops the job
    rather than waiting, because a warm is an optimisation and the real fetch will
    do the work if it is missed.
  * IDEMPOTENT and CROSS-PROCESS. Each job checks its cache file first, and takes
    an atomic O_EXCL lock so sibling workers do not decode the same window. A
    stale lock (crashed worker) expires.
  * DAEMON thread, started lazily. Nothing runs in a process that never leases.

Deliberately generic: it takes a key and a callable, so callers own their own
cache-path logic and this module never learns about cv2, Flask or the schema.
"""
from __future__ import annotations
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Optional
MAX_PENDING = 64
LOCK_STALE_SECONDS = 600
_enabled = True

def configure(enabled: bool=True) -> None:
    """Off switch for tests and for anybody who wants the CPU back."""
    ...

def submit(key: str, job: Callable[[], None]) -> bool:
    """Queue one decode. Returns False if it was already queued or the queue is full."""
    ...

def _ensure_worker() -> None:
    ...

def _run() -> None:
    ...

def claim(lock_path: Path) -> bool:
    """Take a cross-process claim on one cache entry, or report somebody else has it.

    O_EXCL so the check and the take are one operation — two gunicorn workers
    leasing the same walkthrough frame at the same moment is the ordinary case
    here, not a rare race.
    """
    ...

def release(lock_path: Path) -> None:
    ...

def pending_count() -> int:
    ...
