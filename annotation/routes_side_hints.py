"""Flank suggestion for the SIDES SEEN control — ``GET /api/encounters/<code>/side-hint``.

Answers "which flanks did we see at all" so the annotator's SIDES SEEN control can
offer an answer to click instead of asking a human to scrub and count. "Both" is a
legal value here and nowhere else, and the answer is stored under the historical
`$.sides_visible` key.

THE CLAIM IS ABOUT ONE CLIP — ``?video_id=`` IS WHAT THE FORM SENDS
--------------------------------------------------------------------
The labeler has ONE clip open. A suggestion about the other eleven is one they
cannot check, so pressing Accept on it is a rubber stamp — exactly the anchoring
the click-to-accept design exists to prevent. With `video_id` given the response
carries a `clip` block computed from that clip's own stored census
(`encounter_side.clip_side`) and `grain: "clip"`; the encounter-level fields stay
where they were and become CONTEXT. Without it the response is byte-identical to
before, and `grain` reads `"encounter"`.

Storage was already at this grain: `sides_visible` lives on the per-clip
annotation blob, and `encounter_pass_clips` exists precisely because sides differ
across clips of one encounter (22 of 112 pairs). The encounter-wide answer is the
UNION of per-clip answers — additive, computed later, never asserted at the form.

Nothing is recomputed to serve it. Every stored row already carries the per-clip
census in `details_json`, POST-gate, written by the same walk that produced the
encounter answer.

FOUR RULES THIS ENDPOINT DOES NOT BREAK
----------------------------------------
* **A suggestion is never a default.** The response is read and rendered beside the
  control; nothing here pre-selects anything. The client offers an explicit Accept,
  so the stored human answer is always something a person chose. `auto_*` stays
  separate from `human_*`, exactly as the track path already does it.
* **It never runs inference and never touches media.** The answer comes from
  `encounter_side_hints`, written offline by
  `scripts/precompute_encounter_sides.py`. Walking an encounter's clips is minutes
  of CPU; this route has a budget of milliseconds because it fires on every video
  open. No row means no suggestion, never a fallback walk.
* **A fraction of encounters get no suggestion, on purpose.** See
  `hint_blinding.is_blinded_encounter`. The check runs BEFORE the lookup, so a
  blinded response cannot vary with whether a row happens to exist — otherwise
  response timing and shape would leak arm membership.
* **Below the coverage floor the model does not get to answer.** A side computed
  from a handful of decided frames out of thousands is a number, not a finding. The
  route returns `side: null` with `withheld_reason`, and WITHHOLDS the vote counts
  and the per-clip breakdown with it — `n_left` against `n_right` reads the
  suppressed side straight off, so a floor enforced on one field is not a floor.
  `withheld_reason` also keeps "the floor withheld a decision" distinct from "the
  model declined", which are different facts about different things and must not
  render as one sentence.
* **The clip block is judged by the CLIP's own coverage, and survives the
  encounter's floor.** They are different claims about different amounts of
  footage: an encounter that is 3% readable across twelve clips can contain one
  clip that is 60% readable, and refusing to answer about the clip in front of the
  labeler because the other eleven were unreadable withholds the only claim they
  could have checked. The clip block redacts on its own terms — `n_left`,
  `n_right` and `longest_run_*` all read the suppressed side straight off, so all
  four are nulled together.

Config-gated by `pose.encounter_side.enabled` (default OFF). When off the route
returns `{"enabled": false}` WITHOUT touching the database, and the annotator UI is
byte-identical to today.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
DEFAULT_MIN_COVERAGE = 0.1

def create_blueprint(cfg, require_login, rate_limit=None):
    ...

def _census_matches(entry, video_id, video_name=None) -> bool:
    """Is this census entry the clip the labeler is looking at?

    By id first; then by the alias ids the precompute records for `videos` rows
    that share a file (it walks each file once and keeps the first id); then by
    file name, for rows stored before aliases existed. Name matching is on the
    basename only and never crosses encounters -- `clips` is already one row's.
    """
    ...

def _clip_grain(clips, video_id, min_coverage, config, video_name=None):
    """The `grain` / `clip` half of the response, for one requested clip.

    Separate from the route body because it is pure and is the part with the
    silent failure modes: a clip that is not in the row must be reported as such
    rather than as an abstention (the model was never shown it), and a clip whose
    own coverage is below the floor must have its votes AND its run lengths
    withheld, because either reads the suppressed side straight off.
    """
    ...
