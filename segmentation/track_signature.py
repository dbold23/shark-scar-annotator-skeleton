"""Per-track embedding signature — the LIVE propagation hook (Stream A, Phase A1).

When a track is propagated, the worker (app.py) calls `extract_signature(best_frame, scar_bbox)`
and persists the result via `db.update_track_signature(...)`. Historically this was a stub
(`ENABLED = False`, always `None`). Phase A1 wires it to the real extractors in
`segmentation/reid_embed.py`, gated entirely by the `reid:` config.

`configure(reid_embeddings_cfg)` is called once at blueprint registration
(annotation/routes_reid.py, only when `reid.enabled`). It sets module globals the live path
reads. With re-ID disabled, `configure()` never runs, `ENABLED` stays False, and
`extract_signature()` returns None — i.e. **nothing changes in prod until the lab opts in**.

The returned signature is a self-describing JSON blob (carries its own `model` tag and dim), so
embeddings produced by different models/versions are never silently compared (the column-level
`signature_model` tag added in migration v11 is the queryable mirror of this).

Body / fins are the PRIMARY signal; the scar crop is stored only as secondary corroboration —
see segmentation/reid_embed.build_signature and plans/01-research-models-reid.md §5.
"""
from __future__ import annotations
import json
import logging
from typing import Optional, Tuple
import numpy as np

def configure(emb_cfg: Optional[dict]) -> None:
    """Apply the `reid.embeddings` config section and flip ENABLED accordingly.

    Safe to call repeatedly. Never raises — a bad config just leaves the live path disabled.
    """
    ...

def active_config() -> dict:
    """Current embedding config (copy). Used by the backfill to mirror the live settings."""
    ...

def extract_signature(frame_bgr: np.ndarray, scar_bbox: Tuple[int, int, int, int]) -> Optional[str]:
    """Compute the per-track signature for the best frame + scar bbox on the LIVE path.

    Args:
        frame_bgr: Full BGR frame (uint8 H×W×3) — the track's best frame.
        scar_bbox: (x, y, w, h) in pixel coords on this frame.

    Returns:
        JSON-encoded self-describing payload {v, model, dim, region, vec, scar_vec?}, or None if
        disabled / extractor unavailable / crop invalid. Persist with
        `db.update_track_signature(track_id, signature_json, model, dim)`.
    """
    ...
