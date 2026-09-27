"""Per-frame scar hints (Stream D, plan 10 §5) — ``/api/scars/hint``.

Answers "where on the shark is this box, and what colour is it" for a scar the
annotator has just drawn, so the form can PRE-FILL zone / side / colour instead of
asking a human to type what the machine already computes.

Motivation (plans/10 §5): the annotator currently hand-enters six fields per scar,
and four of them — zone, side, colour, on-fin — are already derived and persisted
as ``auto_*`` on the track path. We compute them and then ask the human to type
them anyway. Pre-filling and asking for confirmation only when the model is
unsure takes the common case from six fields to two: draw the box, pick the type.

FOUR RULES THIS ENDPOINT DOES NOT BREAK
----------------------------------------
* **Hints never auto-commit.** The response is a suggestion with a confidence.
  The human remains ground truth, and ``auto_*`` stays separate from ``human_*``
  exactly as the track path already does it.
* **The client sends pixels, not a frame index.** The annotator's canvas already
  holds the decoded frame; asking the server to re-seek by frame number would
  reintroduce the fps mismatch class of bug (the client's assumed fps vs the
  file's real 59.94). Sending the frame sidesteps it entirely. ``video_id`` and
  ``frame_number`` are accepted ALONGSIDE the pixels, never instead of them —
  they are a cache key and a blind-arm key, and if they are wrong the worst case
  is a cache miss, not a hint computed on the wrong image.
* **A fraction of frames get no hint, on purpose.** See ``hint_blinding``.
* **The flank is ONE question per encounter, so it has ONE arm.** A labeler the
  encounter-level surface is withholding a flank from
  (``GET /api/encounters/<code>/side-hint``) must not have the same fact handed to
  them here, frame by frame, on the ~85% of that encounter's frames the per-frame
  arm happens to leave open — the radio would be auto-clicked "Left" all afternoon
  and the encounter-level control would be measuring an anchored human. So the
  ENCOUNTER arm dominates: when it withholds, this route serves no ``side`` for any
  frame of that encounter. Zone, on-fin and colour are unaffected; they are box
  facts and are not what the encounter question asks. The frame arm is left exactly
  as it was rather than being derived from the encounter one, because rederiving it
  would reshuffle every assignment already served and invalidate the frame
  experiment (see ``hint_blinding``'s note on the salt).

THE CACHE
---------
``frame_hints`` (migration v43) holds the per-frame skeleton and flank, precomputed
when the media was prepared. On a hit this route skips the ~90 ms YOLO call and
derives zone / on-fin from the stored keypoints in pure numpy. On a miss it falls
back to inference exactly as before, and does NOT write what it computed: the cache
is keyed on the TRUE cv2 frame index, which only the server-side walker knows. Read
wide, write narrow.

Config-gated by ``pose.frame_hints.enabled`` (default OFF). When off the route
returns ``{"enabled": false}`` and the form behaves exactly as it does today.
"""
from __future__ import annotations
import base64
import logging
from flask import Blueprint, jsonify, request
_MAX_FRAME_B64 = 10000000
_NEIGHBOUR_FRAMES = 90

def _empty_hint():
    ...

def create_blueprint(cfg, require_login, rate_limit=None):
    ...

def _apply_cached(out, cached, scar_xy, cfg) -> bool:
    """Fill zone / side / on-fin from a cached row. True if it fully served.

    An EXACT cached row carries this frame's skeleton, so zone and on-fin are a
    pure-numpy derivation away — no model, no 90 ms. A BORROWED neighbour row does
    not: the animal has moved between the sampled frame and this one, so its
    skeleton would put the zone boundary in the wrong place. A neighbour therefore
    contributes the flank and returns False, sending zone and on-fin to live
    inference where they belong.
    """
    ...

def _apply_live(out, frame, scar_xy, fw, fh) -> None:
    """The original path: run the model on this frame. NEVER raises."""
    ...
