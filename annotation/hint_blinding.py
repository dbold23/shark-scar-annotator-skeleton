"""The blind arm: a fixed slice of frames where the hint is computed and withheld.

WHY A FEATURE NEEDS A CONTROL BUILT INTO IT
-------------------------------------------
`POST /api/scars/hint` pre-fills the scar form with a machine answer. Once that
ships, the agreement between the machine and the human stops being a measurement of
the machine. A pre-filled field is an anchor: the human's job silently changes from
"decide" to "notice a mistake", and noticing is a strictly weaker act than deciding.
Agreement will rise whether or not accuracy rises, and the two are indistinguishable
in the resulting data.

So a fraction of frames arrive with no hint at all, and on those the human decides
unaided. The difference between the two arms is the only thing in the system that can
tell "the model is right" apart from "the labeler was anchored".

This cannot be added retroactively. Once a corpus is labeled with hints everywhere,
there is no unanchored comparison group in it, and no analysis recovers one.

THE FOUR PROPERTIES THE ASSIGNMENT NEEDS
-----------------------------------------
1. **Deterministic.** The same (annotator, video, frame) is always in the same arm.
   A coin flipped per request would let a labeler reload until a hint appeared, and
   would make the arm unreconstructable afterwards.
2. **Stored nowhere.** It is a pure function of the key plus a salt, so an analysis
   run years later recomputes it exactly. A stored flag can drift from what was
   actually served; a hash cannot.
3. **Uniform and uncorrelated.** SHA-256 over the key, not `hash()` (salted per
   process in Python 3) and not `frame_number % 7` (aliases against any sampling
   stride — a walk that samples every 7th frame would blind all of them or none).
4. **Per ANNOTATOR, not per frame.** This is the one that buys statistical power.
   Blinding a whole frame makes the arms two different sets of frames, so every
   comparison is confounded by which frames happened to be harder. Blinding per
   (annotator, frame) means the SAME frame is hinted for one rater and blind for
   another — a within-item design where frame difficulty cancels exactly. On
   single-rater frames it degrades gracefully to the per-frame behaviour.

WHY THE HINT IS STILL COMPUTED ON BLIND FRAMES
-----------------------------------------------
Suppression happens at SERVE time, never at compute time. `frame_hints` therefore
records what the model WOULD have said on a blind frame, which is exactly what makes
the comparison possible: without it the blind arm yields human answers with nothing
to compare them to, and the experiment measures nothing.

CHANGING THE SALT DESTROYS THE EXPERIMENT
------------------------------------------
It reshuffles every past assignment, so frames already labeled under one arm are
reattributed to the other. `DEFAULT_SALT` is a constant for that reason. Change it
only to start a deliberately new experiment, and record when you did.
"""
from __future__ import annotations
import hashlib
from typing import Any, Dict, Optional
DEFAULT_FRACTION = 0.15

def _unit_hash(*parts: Any, salt: str) -> float:
    """A stable float in [0, 1) from the key. NUL-joined so no two different keys
    can concatenate to the same string ("ab"+"c" vs "a"+"bc")."""
    ...

def is_blinded(annotator: Optional[str], video_id: Optional[str], frame_number: Optional[int], *, fraction: float=DEFAULT_FRACTION, salt: str=DEFAULT_SALT) -> bool:
    """True when this (annotator, frame) is in the blind arm.

    `fraction <= 0` disables the arm entirely; `>= 1` blinds everything. Both are
    legitimate settings — the first for a deployment that is not running the
    experiment, the second for a deliberate unaided-baseline collection round.

    Annotator identity is lower-cased before hashing. `signal_labels.annotator`
    keeps the JWT's casing while assignment tables lower-case theirs, and the same
    human under two spellings would land in two different arms — the same
    one-human-two-raters failure `signal_consensus.norm_annotator` exists to stop.
    """
    ...

def is_blinded_encounter(annotator: Optional[str], encounter_code: Optional[str], *, fraction: float=DEFAULT_FRACTION, salt: str=DEFAULT_SALT) -> bool:
    """True when this (annotator, ENCOUNTER) is in the blind arm.

    The encounter-level flank suggestion (`GET /api/encounters/<code>/side-hint`)
    needs its own key, because the frame-level one cannot express it: an
    encounter-level fact that is withheld on frame 2 has already been read on
    frame 1, and a labeler who has seen the suggestion once is anchored for the
    whole encounter no matter what later frames return. Blinding must therefore be
    decided at the grain the fact is stated at.

    Same salt, same fraction, same SHA-256 machinery as `is_blinded`, so the two
    surfaces are ONE experiment with one arm size — but the key is namespaced
    (`"encounter:<code>"`) so an encounter code can never collide with a video id
    and inherit the frame arm's assignment for that annotator.
    """
    ...

def blind_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Read the arm's settings out of the `pose.frame_hints` config block.

    `blind_fraction` defaults to DEFAULT_FRACTION rather than to 0, which is a
    deliberate departure from "an unconfigured feature is OFF" (plans/12). That rule
    exists so no CAPABILITY reaches a student unchosen, and it is still honoured:
    `pose.frame_hints.enabled` defaults false, so nothing here runs until someone
    turns hints on. What defaults on is the CONTROL attached to that capability —
    and the asymmetry is the reason. Defaulting the control off costs an
    unrecoverable experiment the first time somebody enables hints without reading
    this file; defaulting it on costs 15% of hints on a feature that already
    abstains on 46% of frames.
    """
    ...

def arm_of(annotator, video_id, frame_number, **kw) -> str:
    """'blind' | 'hinted' — the label an analysis should group by."""
    ...
