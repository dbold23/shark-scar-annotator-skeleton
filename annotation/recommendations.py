"""Stream B (MLOps) — scar-TYPE recommendation for the track verify flow.

Surfaces a model's scar-type suggestion when an annotator verifies a proposed
track (the human is always ground truth — this is a hint, never an auto-commit).
Config-gated OFF and needs a trained model: when ``mlops.recommendations.enabled``
is false or no model/frame is available the endpoint reports ``suggestion: null``
and the verify flow is unchanged.

Two pluggable sources (both lazy, optional, CPU-fine):
  * ``detector``        — reuse a YOLO scar detector; the top box's class is the
                          type hint (in-repo, no sibling dependency).
  * ``scar_classifier`` — a YOLO-classify model's top-k probabilities.

The suggester is split so it is testable without a model or a video: ``suggest()``
takes an injected ``runner`` (image → ``[(type, prob), ...]``), and ``build_runner``
/ ``track_image`` are the best-effort adapters that wire the real model + frame.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

def _resolve_model_path(rc: Dict) -> Optional[Path]:
    ...

def availability(rc: Dict) -> Tuple[bool, str]:
    """Whether a recommendation can be produced, without paying import cost."""
    ...

def suggest(image: Any, rc: Dict, runner: Runner) -> Dict:
    """Shape a model's ranked output into a suggestion payload. Pure given a
    runner — this is the unit the route and tests both exercise."""
    ...

def build_runner(rc: Dict) -> Optional[Runner]:
    """Lazy-build a runner for the configured source, or None if unavailable.
    Never raises — a missing model/dep degrades to 'no suggestion'."""
    ...

def _resolve_video_path(video: Dict, rc: Dict) -> Optional[Path]:
    """Best-effort local video path: explicit video_path, else the download dir
    cache. Cloud-only fetch is out of scope here (return None → no suggestion)."""
    ...

def track_image(track: Dict, video: Dict, rc: Dict, pad_frac: float=0.2):
    """Best-effort: read the track's best frame and crop to its scar box (padded).
    Returns (image|None, reason). None in dev when the video isn't cached locally —
    the route then reports ``suggestion: null`` cleanly."""
    ...
