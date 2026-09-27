"""Marking one annotation against the gold standard for that frame.

Pure: no Flask, no SQL, no config reads — the same split ``signal_consensus.py``
and ``label_quality.py`` use, so the rules can be tested on hand-built fixtures
instead of a database.

The headline numbers come from ``eval_metrics`` (``pck`` for keypoints,
``bbox_iou`` for boxes) rather than a second implementation, so a walkthrough is
marked with the same arithmetic the model evaluations use. What this module adds
is the part those functions deliberately do not return: **per-part detail**. A
labeler told "0.62" has learned nothing; a labeler told "your dorsal_fin_tip is
40 px low and you missed the scar on the left flank" has learned the task.

Three rules worth stating, because each is a way to be quietly unfair:

  * **Unscorable is not zero.** A gold answer with no visible keypoints, or no
    usable scale, returns ``score=None``. Scoring it 0.0 would fail somebody for
    the admin's omission.
  * **A gold keypoint the admin left out is not a question.** ``v=0`` in the
    answer key drops out of the denominator entirely.
  * **A scar counts as found only if it is BOTH in the right place and named
    correctly.** Right label on the wrong animal part is not a pass, and a
    perfectly-placed box called the wrong thing is not either.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Tuple
from annotation.eval_metrics import bbox_iou, pck
from annotation.models import SHARK_KEYPOINT_SEQUENCE
DEFAULT_PCK_ALPHA = 0.1
DEFAULT_IOU_THRESHOLD = 0.4

def _box(bb: Any) -> Optional[Dict[str, float]]:
    """Normalise a bbox to what ``bbox_iou`` expects.

    Stored boxes use ``{x, y, width, height}`` (canvas.js builds them that way and
    every annotation in the corpus agrees). ``{w, h}`` is accepted too, because
    ``bbox_iou`` silently returns 0.0 for keys it does not recognise — a mismatch
    would read as "the labeler got everything wrong" rather than as an error.
    """
    ...

def _kpt_tuples(keypoints: Any, *, drop_invisible: bool=False) -> List[Optional[Tuple[float, float, int]]]:
    """``[{name,x,y,v}]`` → the positional ``(x, y, v)`` list ``pck`` indexes into.

    Ordered by ``SHARK_KEYPOINT_SEQUENCE``, so a labeler who placed points in a
    different order is not compared against the wrong joints. A name the schema
    does not know is ignored rather than appended — appending would shift every
    later index by one.

    ``drop_invisible`` is for the LABELER's side: a point they marked as outside
    the frame carries stale coordinates, and passing those through would let
    "I can't see it" land within tolerance by luck.
    """
    ...

def _scale(answer: Dict[str, Any]) -> Optional[float]:
    """The distance PCK's tolerance is a fraction of, from the GOLD answer only.

    **The animal's SHORT axis, not its diagonal.** A shark is long and thin, so a
    diagonal is essentially its length, and a tolerance set as a fraction of length
    is meaningless for the points that matter: measured on real 4K frames here, the
    keypoint spread is 3236 x 1432, giving a diagonal of 3539 px and a PCK@0.1
    tolerance of 354 px — a quarter of the whole animal's height, which passes an
    annotation that is visibly wrong. The short side gives 143 px on the same frame.
    This is the same argument ``gap_analysis.animal_short_side_px`` makes about
    placeability, applied to marking.

    From the GOLD answer only: normalising by the labeler's own box would make a
    tighter box a harsher grader and a sloppy one lenient, when the tolerance has to
    be the same question for everybody.

    Falls back to the spread of the gold keypoints when the answer key has no body
    box — the common case, not an edge case: ``body_bbox`` is optional in the
    annotator, and every complete skeleton measured in this corpus was stored
    without one. Without the fallback ``pck`` sees ``norm=0``, and 0 makes every
    keypoint wrong.
    """
    ...

def score_pose(gold: Dict[str, Any], attempt: Dict[str, Any], *, alpha: float=DEFAULT_PCK_ALPHA) -> Dict[str, Any]:
    """PCK@alpha over the 16-point skeleton, plus which points went wrong.

    Tolerance is ``alpha`` x the animal's SHORT axis — see ``_scale``."""
    ...

def _match_scars(gold_scars: Sequence[Dict[str, Any]], attempt_scars: Sequence[Dict[str, Any]], iou_threshold: float) -> List[Tuple[int, int, float]]:
    """Greedy best-IoU pairing, each box used once.

    Greedy rather than optimal assignment: scars on one frame are far apart
    relative to their size, so the two agree in practice, and greedy is the
    behaviour a labeler can reason about ("your box was matched to the nearest
    gold box").
    """
    ...

def _norm_field(value: Any) -> str:
    ...

def score_scars(gold: Dict[str, Any], attempt: Dict[str, Any], *, iou_threshold: float=DEFAULT_IOU_THRESHOLD, required_fields: Sequence[str]=DEFAULT_REQUIRED_FIELDS) -> Dict[str, Any]:
    """F1 over scars that are both located and named correctly.

    One number covering both halves of the task, rather than a weighted blend of
    "found things" and "named things": blending lets somebody who boxed every scar
    and labelled them all wrong still score half marks, when what they have
    demonstrated is that they cannot do the task.
    """
    ...

def score(task_type: str, gold_answer: Dict[str, Any], attempt: Dict[str, Any], *, pass_score: float=0.7, alpha: float=DEFAULT_PCK_ALPHA, iou_threshold: float=DEFAULT_IOU_THRESHOLD) -> Dict[str, Any]:
    """Mark one attempt. ``passed`` is None when the frame could not be scored —
    never False, so a broken answer key cannot fail anybody."""
    ...

def summarise(results: Sequence[Dict[str, Any]], *, pass_score: float=0.7) -> Dict[str, Any]:
    """Roll a walkthrough's attempts into the one verdict that gates the mission.

    Unscorable attempts are dropped from the mean rather than counted as zero,
    and a run with nothing scorable returns ``passed=None`` — the caller decides
    what to do with a gate it cannot judge, which is never "fail the labeler".
    """
    ...
