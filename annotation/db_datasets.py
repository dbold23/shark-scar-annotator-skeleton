"""Dataset specs + dispatched work items (Stream B, plan 10).

Owns the SQL for the FED annotator queue. Ranking logic lives in the pure
``gap_analysis`` module; this file measures the corpus, materialises work items,
and hands out leases.

Two invariants worth stating up front, because both are unrecoverable if broken:

  * **Split by video, never by frame.** Enforced in ``gap_analysis.assign_split``
    and applied once at item-creation time. Frames from one video are
    near-duplicates; a frame-level split leaks test into train.
  * **Work is leased, not assigned.** A lease expires and the item returns to the
    pool, so nobody can reserve five items and strand them for a semester.

Follows the ``db_mlops`` conventions: thread-local connection from ``database``,
its own tables, never touches ``database.py`` core or the consensus algorithm.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from annotation.database import get_conn, _column_exists
from annotation import gap_analysis as gap
from annotation.models import ScarType
DEFAULT_LEASE_HOURS = 2

def has_claim_on_video(annotator: str, video_id: str) -> bool:
    """Has this person been handed (or finished) fed-queue work on this clip?

    The assignment gates on /complete, /status and /annotations/video knew only
    `assignments`; a fed-queue lease creates none, so FINISH VIDEO 403'd on every
    queue clip and a re-served clip loaded with no saved frames. Absent table or
    any error => False, so a deployment with the queue off behaves exactly as before.
    """
    ...

def init_dataset_tables() -> None:
    """Idempotently bring the dataset/queue schema up to date.

    Three steps, in this order, because each depends on the last:
      1. CREATE TABLE IF NOT EXISTS  — creates anything missing outright.
      2. guarded ALTER               — adds columns to tables that already existed
                                       before the migration that introduced them.
      3. dependent CREATE INDEX      — safe only once step 2 has run.

    Step 2 is the one this used to be missing. `CREATE TABLE IF NOT EXISTS` no-ops
    on an existing table, so a DB migrated to v25 but not v41 kept a 21-column
    `work_items` with no `is_practice` forever, and step 3 then raised
    `OperationalError: no such column` out of the first line of every public
    function here. Mirrors init_annotation_columns()/init_track_tables() in
    annotation/database.py, which already solve this for their own tables.
    """
    ...

def _now() -> str:
    ...

def _loads(raw: Any, default: Any) -> Any:
    ...

def _spec_dict(row) -> Dict[str, Any]:
    ...

def quarantined_practice_keys() -> set:
    """``(video_id, frame_number, annotator)`` triples that must NOT count as corpus.

    The practice gate promises that a labeler's first frames are "held out of the
    corpus until a reviewer decides" — but the annotation itself goes through the
    ordinary save path and lands in ``annotations`` before the queue is even told.
    The only thing that can honour the promise afterwards is a filter here, so every
    corpus measurement in this module applies it.

    Membership means "practice work whose reviewer has not said `include`" —
    unreviewed and explicitly discarded alike. Annotator is folded to lower case
    because ``work_items.completed_by`` and ``annotations.annotator`` are written by
    different call paths from the same JWT.
    """
    ...

def _is_quarantined(quarantined: set, video_id, frame_number, annotator) -> bool:
    ...

def keypoint_visible_counts() -> Dict[str, int]:
    """How many annotations have actually PLACED each of the 16 keypoints.

    Streams the cursor rather than fetchall — the annotation blobs are the largest
    rows in the DB and this runs on every queue refill.

    Quarantined practice work is excluded: counting it would let three
    misunderstood frames lower a keypoint's deficit and de-prioritise exactly the
    point the corpus is weakest on.
    """
    ...

def scar_class_counts() -> Dict[str, int]:
    """Instance count per scar_type across the corpus.

    Quarantined practice work is excluded — see ``quarantined_practice_keys``.
    """
    ...

def normalize_scar_type(raw: Any) -> str:
    """Fold a Forms label back to its enum name.

    The historical import kept the whole dropdown text, so the same class appears as
    both ``GEAR`` and ``GEAR (FISHING GEAR OR ROPE MARKS)``. Six of the eighteen
    distinct values in consensus_cache are that shape. Left alone they rank as
    separate classes, and the rare-class targeting this feeds would treat a
    well-covered type as untouched.

    TWO separators, because the two sources disagree: the raw Forms export writes
    ``SCRATCH _RAKING CLAW MARKS...`` with an underscore, while the value that
    reached consensus_cache uses parentheses. Handling only one silently leaves
    3,049 raw SCRATCH rows sitting under their own long label.
    """
    ...

def encounter_scar_types(*, reliable_only: bool=False) -> Dict[str, set]:
    """encounter_id -> the scar types humans have RECORDED there, from text alone.

    Mined from ``consensus_cache.details_json``, which stores one entry per agreed
    scar with its type, zone, side and colour. Measured 2026-08-16: 403 encounters,
    ~3,700 instances, against 61 boxes in the whole bbox corpus. GRAB, GEAR and
    COOKIE each have zero boxes and 54-150 encounters naming them.

    This is what makes rare-class targeting possible with no detector. A detector
    could only propose classes it was trained on, which by definition excludes the
    ones with no examples; a human already wrote these down. Read-only, and never a
    label: it says "somebody saw a GEAR scar in this encounter", which is a reason
    to queue the clip, not a box.

    ``reliable_only`` keeps entries the consensus marked reliable, trading recall
    for precision when the queue is long enough to be choosy.
    """
    ...

def encounters_needing(deficit: Dict[str, float], *, min_deficit: float=0.5, reliable_only: bool=False) -> Dict[str, float]:
    """encounter_id -> how badly its recorded scar types are under-represented.

    The score is the LARGEST deficit among the types recorded there, not the sum: an
    encounter naming one class with no examples is worth more than one naming three
    well-covered classes, and summing would invert that.
    """
    ...

def encounter_negatives() -> List[str]:
    """Encounters a human scored and found NO scars on.

    159 of them, measured 2026-08-16. These are free hard negatives, and positive-only
    labelling structurally cannot produce them: an annotator asked to box scars
    generates no record of a shark that had none. A detector trained only on frames
    containing scars learns "shark implies scar" and fires on clean skin.

    Cheap to use and worth more than another positive of a common class.
    """
    ...

def missing_class_diagnosis(targets: Optional[Dict[str, int]]=None) -> Dict[str, Dict]:
    """Split "we have no examples" into its two very different causes.

    A class with no boxes is either ABSENT from the footage, or PRESENT and simply
    never boxed. Only the second is fixable by annotating, and treating them alike
    wastes a semester chasing something nobody ever filmed.

    Measured: COPEPODS is named in 0 encounters and has 0 boxes; GEAR is named in 84
    encounters and has 0 boxes. Same "zero examples" defect, opposite responses.
    """
    ...

def viewpoint_counts() -> Dict[int, int]:
    """How many existing pose annotations fall in each aspect-ratio bin.

    Read from the stored body_bbox rather than from any model, so it describes the
    corpus as labelled rather than as predicted. Cheap: only rows already known to
    carry keypoints are parsed.
    """
    ...

def corpus_snapshot(task_type: str) -> Dict[str, Any]:
    """Current state of the corpus for a task type — the 'have' side of the deficit.

    Includes the derived weak-point list so the admin gap dashboard and the
    ``gap_reason`` strings agree on what 'under-represented' means.
    """
    ...

def scar_class_targets(spec: Dict[str, Any], counts: Optional[Dict[str, int]]=None) -> Dict[str, int]:
    """The per-class target this spec is measured against.

    An UNCONFIGURED spec must still produce a real target list. There is no UI, route,
    config key or script anywhere that sets ``class_targets`` or ``classes`` — the only
    spec-creation surface sends ``{}`` or ``{target_per_keypoint: N}`` — so before this
    fallback existed every bbox/segment spec the product can create computed an empty
    deficit. An empty deficit is not "nothing to do": ``scar_candidate_score`` reads a
    missing class as rarity 0.0 and ``class_gap_reason`` reads it as "tops up X", so a
    class with ZERO examples was ranked last and described to the labeler as already
    covered. Confidently wrong, and the exact inversion of the invariant in plan 10 §4
    ("a class with no examples must outrank a merely uncertain instance of an
    already-common class").

    Falling back to the declared scar universe is the scar-side analogue of the pose
    branch's ``per_point = max(1, target_n)``: the schema already names the classes, so
    no configuration is needed to know that GRAB exists and has none.
    """
    ...

def compute_deficit(spec: Dict[str, Any]) -> Dict[str, float]:
    """Normalized per-class shortfall for a spec, in [0, 1]."""
    ...

def create_spec(name: str, task_type: str, *, target_n: int=0, requirements: Optional[Dict]=None, split: Optional[Dict]=None, overlap_fraction: float=0.1, gold_fraction: float=0.05, notes: str='', created_by: str='') -> Dict[str, Any]:
    ...

def get_spec(spec_id: int) -> Optional[Dict[str, Any]]:
    ...

def get_spec_by_name(name: str) -> Optional[Dict[str, Any]]:
    ...

def list_specs(status: Optional[str]=None, task_type: Optional[str]=None) -> List[Dict[str, Any]]:
    ...

def set_spec_status(spec_id: int, status: str) -> Dict[str, Any]:
    ...

def generate_work_items(spec_id: int, candidates: Sequence[Dict[str, Any]], *, dedup_window: int=0) -> Dict[str, Any]:
    """Rank candidates and materialise them as queued work items.

    ``candidates`` are dicts with at least ``video_id``; optionally
    ``frame_number``, ``track_id``, ``site``, ``predicted_points`` (pose) or
    ``predicted_class`` / ``uncertainty`` (scars). Already-queued (video, frame)
    pairs for this spec are skipped, so this is safe to re-run as the corpus grows.
    """
    ...

def count_items(spec_id: int, state: Optional[str]=None) -> int:
    ...

def release_expired_leases(now: Optional[str]=None) -> int:
    """Return timed-out leases to the pool. Idempotent; called before every lease."""
    ...

def in_bootstrap_regime(spec_id: int) -> bool:
    """Is this spec still in the cold-start regime?

    Dispatch has to ask, because the ORDER the items were ranked in is regime-
    dependent: ``gap.rank_candidates`` returns round-robin SPREAD during bootstrap and
    score order afterwards. Only the score is persisted (``work_items.priority``), so
    ordering dispatch by priority throws the spread away and serves the cohort the
    biggest/most obvious frames first — which is precisely how the pilot ended up
    63.1 % vs 2.7 % on keypoint coverage. During bootstrap the insert order IS the
    ranking, so ``id ASC`` restores it.

    A spec with no ``bootstrap_n`` is never in this regime, so its dispatch order is
    byte-identical to before.
    """
    ...

def _claim(spec_id: int, annotator: str, want: int, lease_hours: int, *, practice: bool=False) -> int:
    """Claim up to ``want`` queued items for ``annotator``. Returns how many.

    ``practice`` additionally stamps the claimed rows as a practice run, so their
    annotations can be quarantined until a reviewer rules on them.

    A single UPDATE whose subquery runs inside the write transaction, so concurrent
    annotators serialise on SQLite's writer lock rather than racing for the same
    rows.

    Two separate guards keep overlap meaningful — overlap exists so that TWO
    DIFFERENT people label one unit, and one person labelling it twice measures no
    agreement at all:

      * ``GROUP BY video_id, frame_number, track_id`` — at most one row per unit
        per claim. Needed because the subquery sees the PRE-UPDATE state, so without
        it both sibling rows of an overlap pair are eligible in the same statement
        and land in the same annotator's queue. ``track_id`` belongs in the key
        because a 'verify' item has no frame: without it every track of one video is
        one group, and one finished track locks the labeler out of all the others.
      * ``NOT EXISTS`` — never hand over a unit this annotator already holds, has
        completed, or has SKIPPED. Covers the across-call case the GROUP BY cannot
        see. Same three-part key, for the same reason: ``NULL IS NULL`` is true, so a
        frameless unit would otherwise match every other frameless unit in the video.

        ``skipped`` belongs in that list for the same reason ``done`` does. A skip
        is this person's answer about this unit ("blurry", "no animal"); handing
        them the overlap sibling puts ONE labeler on both rows of a pair that
        exists precisely so two DIFFERENT people label it, which measures no
        agreement at all — and quietly spends the pair. Measured on a 15-student
        run before the fix: a unit skipped as blurry came straight back to the
        same person, who then annotated it.

        The guard is deliberately NOT scoped to one spec, and that is the part
        worth explaining. An annotation's primary key is
        ``make_annotation_id(video_id, frame_number, annotator)`` — the MISSION is
        not in it — and ``save_annotation`` is INSERT OR REPLACE. So one person
        handed frame 48 by the pose mission and again by the segment mission
        writes BOTH answers to one row, and the second silently overwrites the
        first: two finished work items, one surviving annotation, and the earlier
        mission's data gone with nothing to show it ever existed. Until the
        annotation key carries the task, the queue must not hand one person two
        items that collapse onto the same key.

    Ordering follows the regime — see ``in_bootstrap_regime``.
    """
    ...

def lease_items(spec_id: int, annotator: str, n: int=5, *, lease_hours: int=DEFAULT_LEASE_HOURS) -> List[Dict[str, Any]]:
    """Top up ``annotator``'s queue for one spec to ``n`` and return the held queue."""
    ...

def count_held(spec_id: int, annotator: str) -> int:
    ...

def _table_exists(conn, name: str) -> bool:
    ...

def _videos_table_exists(conn) -> bool:
    ...

def held_items(spec_id: int, annotator: str) -> List[Dict[str, Any]]:
    """Items this annotator currently holds, enriched with what the UI needs to
    open them (name, encounter, media type) so the client needs no second call.

    Presentation order matches dispatch order, including the bootstrap spread —
    serving the spread and then re-sorting it by priority for display would put the
    cohort back on the same few clips.
    """
    ...

def complete_item(item_id: int, annotator: str, *, annotation_id: Optional[int]=None, time_on_task_sec: Optional[float]=None) -> bool:
    """Mark a leased item done. Returns False if the caller doesn't hold the lease —
    a stale client must not be able to complete work reassigned to someone else."""
    ...

def _maybe_compare_siblings(row, item_id: int) -> None:
    """Second person on this unit has just finished — compare the two answers.

    Placed AFTER the completion transaction and swallowing every exception, for
    the same reason ``settle_gold_item`` is called from outside this function: an
    agreement bug must never be able to cost somebody the annotation they just
    saved. A failure here degrades to "not compared yet", which the next refresh
    picks up.

    Scoped to the ONE unit that just changed, and skipped outright unless the row
    was dispatched for overlap — an ordinary single-rater item has no sibling to
    compare against, so the common path is one integer test and a return. The whole
    thing is inert while ``mlops.datasets.agreement.enabled`` is false, which is
    the default.
    """
    ...

def skip_item(item_id: int, annotator: str, reason: str='other') -> bool:
    """Skip with a RECORDED reason (blurry / dark / occluded / no_animal / other).

    Skips are kept, not deleted: 'this frame was unusable' is training signal for a
    quality filter, and silently dropping it throws that away.
    """
    ...

def _record_practice_annotation(spec_id: int, annotator: str, video_id: Any, frame_number: Any, work_item_id: Optional[int], annotation_id: Any) -> None:
    """Remember that this annotation came out of a practice lease.

    Written at completion rather than derived from ``work_items`` later, because
    rejecting a run recycles those rows (is_practice and completed_by cleared) and the
    provenance would be gone by the time anybody asked. Re-submitting the same frame
    resets the verdict to 'pending' — a redo has not been reviewed either.
    """
    ...

def practice_annotations(spec_id: Optional[int]=None, annotator: Optional[str]=None, decision: Optional[str]=None) -> List[Dict[str, Any]]:
    """Annotations produced by practice leases, with the reviewer's verdict.

    The identifying triple is ``(video_id, frame_number, annotator)`` — the same key
    ``database.make_annotation_id`` builds ``annotations.id`` from — so a consumer
    outside this module (export, Sheets sync, a cleanup script) can honour a
    'discard' without needing the work_items row, which by then may have been
    recycled. Corpus measurement in THIS module already honours it.
    """
    ...

def _practice_row(conn, spec_id: int, annotator: str) -> Optional[Dict[str, Any]]:
    ...

def get_practice(spec_id: int, annotator: str, *, n_required: int=3, create: bool=True) -> Optional[Dict[str, Any]]:
    """This labeler's practice record for one mission, creating it on first contact."""
    ...

def practice_blocks(spec_id: int, annotator: str, *, n_required: int=3) -> bool:
    """May this labeler NOT be given ordinary work on this mission?

    True for every state except ``approved``. Enforced here, in the lease path,
    rather than in the UI: a gate a client can skip is not a gate. ``n_required``
    of 0 disables practice for the mission entirely.
    """
    ...

def record_practice_submission(spec_id: int, annotator: str, *, n_required: int=3) -> Dict[str, Any]:
    """Count one finished practice item; flip to awaiting_review at the target.

    Never moves a record backwards out of review or approval — a late completion
    from an expired lease must not reopen a run somebody has already judged.
    """
    ...

def review_practice(spec_id: int, annotator: str, *, approve: bool, feedback: str='', decision: str='discard', reviewed_by: str='') -> Optional[Dict[str, Any]]:
    """Reviewer verdict.

    ``approve`` governs the PERSON (may they continue); ``decision`` governs the
    DATA (include|discard their practice annotations). Deliberately separate: a
    labeler can be cleared to work while their practice frames are still thrown
    away, and a rejected run can still contain usable labels.

    ``decision`` is APPLIED, not merely recorded. It used to be stored and read by
    nothing: an admin who approved a labeler with "Keep their work" unchecked — the
    shipped default — got a 200 confirming a discard that never happened, while the
    frames stayed in the corpus and kept feeding the gap analysis that decides what
    the cohort labels next. Only rows still awaiting a verdict are stamped, so a
    later run cannot retroactively reverse an earlier reviewer's call.

    NOT approving sends the labeler back to ``practicing`` with the feedback
    attached, rather than to a terminal rejected state: the point of the gate is to
    correct someone before they work at volume, and a dead end leaves them with zero
    items and no route forward.
    """
    ...

def list_practice(state: Optional[str]=None) -> List[Dict[str, Any]]:
    """Practice records, newest first — the admin review queue."""
    ...

def count_practice_outstanding(spec_id: int, annotator: str) -> int:
    """Practice items this labeler is already holding but has not finished.

    The lease path must subtract these, not just the global held count: a second
    call to lease_across_specs sizes its claim on `n - held`, which happily tops a
    3-item practice run up to the full queue size. Measured: a labeler who reloaded
    once ended up holding 5 practice items for a 3-item gate, and the reviewer was
    shown all 5.
    """
    ...

def practice_items(spec_id: int, annotator: str) -> List[Dict[str, Any]]:
    """The practice items this labeler completed — what the reviewer looks at."""
    ...

def _claim_practice(conn_unused, spec_id: int, annotator: str, want: int, lease_hours: int) -> int:
    """Mark the top-ranked queued items as practice and lease them.

    Practice runs on the SAME ranked pool as real work, not on an easy subset:
    practising on unrepresentative frames teaches the wrong thing. What differs is
    that the resulting annotations are quarantined until reviewed.
    """
    ...

def claim_gold_items(spec_id: int, annotator: str, want: int, lease_hours: int, *, task_type: str, practice: bool) -> int:
    """Lease ``want`` gold frames this labeler has never been marked on."""
    ...

def settle_gold_item(item_id: int, annotator: str, *, annotation_id: Optional[str]=None, pass_score: float=0.7, alpha: float=0.1, iou_threshold: float=0.4, n_required: int=3) -> Optional[Dict[str, Any]]:
    """Mark a finished gold-backed item and, for a walkthrough, settle the run.

    Returns the labeler-facing result (score + per-part detail), or None when the
    item was not gold-backed. (See ``_lease_gold_practice`` for the sizing rules.) Called after ``complete_item`` has already recorded
    the completion — marking is a separate step so a scoring bug can never cost
    somebody the annotation they just saved.
    """
    ...

def _annotation_payload(annotation_id: Optional[str], item: Dict[str, Any], annotator: str) -> Dict[str, Any]:
    """The labeler's saved annotation for this frame.

    Looked up by id when the client sent one, else by (video, frame, annotator) —
    the save is what the marking has to be based on, never the client's own claim
    about what it drew, which would let a modified page mark itself.
    """
    ...

def _settle_walkthrough(spec_id: int, annotator: str, *, pass_score: float, n_required: int) -> Dict[str, Any]:
    """Decide the run once every question has been answered.

    Pass → approved on the spot; nobody waits on a human to click. Fail → straight
    back to practising, with the next run drawn from gold they have NOT seen, so
    the retry is a fresh set of questions rather than a second look at the answers
    they were just shown.
    """
    ...

def _run_feedback(verdict: Dict[str, Any], approved: bool) -> str:
    ...

def _lease_gold_practice(spec: Dict[str, Any], annotator: str, rec: Optional[Dict[str, Any]], *, want: int, outstanding: int, room: int, lease_hours: int) -> Tuple[int, bool]:
    """Serve the walkthrough from the gold pool, and never leave anybody stranded.

    The pool is finite and shrinks per labeler — every frame they are marked on is
    spent for good. So the run is sized against what is actually left:

      * nothing left and nothing in flight → clear them. A gate with no questions
        cannot be a gate, and blocking somebody because the lab has not authored
        enough exemplars turns a config gap into a person with no work. The admin
        sees the short pool on their own dashboard.
      * fewer left than the run asks for → shrink the run to fit, so it can still
        be completed and settled instead of hanging at "2 of 3" forever.
    """
    ...

def _work_done_count(spec_id: int, annotator: str) -> int:
    """Ordinary items this labeler has finished on this mission.

    Gold-backed rows are excluded, so a check never counts itself towards the next
    one — otherwise the interval quietly shortens every time somebody is checked.
    """
    ...

def maybe_claim_skill_check(spec: Dict[str, Any], annotator: str, *, every: int, lease_hours: int) -> int:
    """Slot one gold frame into an approved labeler's queue every ``every`` items.

    Announced, not hidden: the card says "Skill check", because the alternative is
    a lab that secretly marks its students' ordinary work, and being measured
    without being told is a thing you do to subjects, not colleagues.

    Counts from the last check rather than from a running total, so a labeler who
    is behind does not get several checks in a row the moment they catch up.
    """
    ...

def _set_practice_required(spec_id: int, annotator: str, n_required: int) -> None:
    ...

def lease_across_specs(annotator: str, n: int=5, *, lease_hours: int=DEFAULT_LEASE_HOURS, practice_n: int=0, gold: bool=False, skill_check_every: int=0) -> List[Dict[str, Any]]:
    """Fill an annotator's queue to ``n`` from every ACTIVE spec.

    A mission the labeler has not been cleared on serves PRACTICE items instead,
    and once those are submitted it serves nothing at all until a reviewer rules —
    the hard stop. A spec can opt out with ``requirements.practice_n: 0``.

    ``practice_n`` defaults to 0 — NO gate — so this library function behaves exactly
    as it did before v41 for every caller that does not ask for one. The product
    default (3) is supplied by the route from ``mlops.datasets.practice_n``, which is
    already inside an opted-in feature. Defaulting the gate on here instead would
    impose it on every existing caller as a side effect of adding the parameter.

    ``gold`` switches the walkthrough from corpus frames awaiting a human reviewer
    to frames the lab has already answered, which are marked on submission. Same
    default-off reasoning: it changes what a practice item IS.

    Specs are drained in creation order, so a lab running "finish pose_v5 first,
    then scar_seg_v2" gets that behaviour by activating them in that order. Only
    ``active`` specs dispatch — draft specs are still being designed and frozen ones
    are closed, and neither should reach an annotator.

    ``requirements.drain_first`` (truthy) moves a spec ahead of every other in that
    order — ties still by id, so the creation-order contract holds among equals.
    ``requirements.annotators`` (a list of emails) restricts a spec to those people,
    compared through ``norm_annotator`` on both sides; absent or empty, the spec is
    open to everyone and dispatch is byte-identical to before, because production
    specs were created without either key and must not change behaviour on upgrade.
    Both keys govern CLAIMING only: items a labeler already holds in a spec are still
    returned even after they are struck from its list.
    """
    ...

def get_item(item_id: int) -> Optional[Dict[str, Any]]:
    ...

def mission_completion(spec_id: int) -> Dict[str, Any]:
    """What a mission has actually delivered, for a number shown to labelers.

    Deliberately NOT ``spec_progress()['done']``, whose bare ``COUNT(*) WHERE
    state='done'`` is wrong three ways the moment a student can see it:

      * it counts PRACTICE rows. On this catalog the only 'done' row anywhere is a
        practice item from a test account, and spec_progress reports it as real
        progress on a frozen mission.
      * it counts GOLD skill-check rows, which ``_work_done_count`` already excludes
        for the check cadence, so the two "how much is done" counters in this file
        disagree with each other.
      * it double-counts OVERLAP. ``generate_work_items`` materialises
        ``overlap_fraction`` as N sibling rows for one (video_id, frame_number), so
        two people finishing the same frame reads as two frames done.

    `done` means an annotation was handed in, NOT that anybody accepted it: nothing
    reviews an ordinary completed item. Copy built on this must say "done", never
    "verified" or "checked".

    `measurable` is the honesty flag. A mission with no target or nothing queued has
    no number worth drawing, and a bar at zero percent with nothing behind it reads
    as broken software rather than as work not yet started.
    """
    ...

def mission_share(spec_id: int, annotator: str) -> int:
    """One person's own finished frames on a mission.

    LOWER() on both sides, matching ``_work_done_count``. The cooperative goal's
    existing my_contribution compares an email exactly, which silently zeroes
    somebody whose casing differs between the JWT and the stored row.
    """
    ...

def spec_progress(spec_id: int) -> Dict[str, Any]:
    """Counts by state and by split — what the admin gap dashboard renders."""
    ...

def _agreement_defaults() -> Dict[str, Any]:
    """Thresholds default to scar_consensus's own, never to a second copy of them.

    Those numbers are inherited from Stream F and have NO shark evidence behind
    them (see that module's docstring); re-typing them here would create a second
    place to re-tune when somebody finally does the measurement, and the two would
    disagree without anything failing.
    """
    ...

def _resolve_agreement_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    ...

def agreement_config(cfg: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    """Resolved ``mlops.datasets.agreement`` knobs. OFF unless both flags are set.

    ``cfg`` is the WHOLE config dict when the caller already has one (app.py hands
    its routes theirs). With no argument this reads config.yaml itself and caches
    the answer — the same choice ``database.scar_consensus_thresholds()`` made, and
    for the same reason: this module is also driven by scripts and tests that never
    build the Flask app, and the route layer that would otherwise thread it down
    lives in another file. A missing or malformed config degrades to the defaults
    (i.e. OFF) rather than raising inside a save.
    """
    ...

def _unit_key(video_id: Any, frame_number: Any, track_id: Any) -> str:
    """Canonical, injective text key for one work unit.

    JSON rather than ``a:b:c`` because the parts are user-ish data: a video id
    containing the separator would alias two different units onto one key, and the
    only symptom would be one unit's consensus silently overwriting another's.
    """
    ...

def overlap_units(spec_id: int, *, min_raters: int=2) -> List[Dict[str, Any]]:
    """Finished OVERLAP units that actually collected two or more DIFFERENT people.

    The grouping key is ``(video_id, frame_number, track_id)`` — the same triple
    ``generate_work_items`` dedupes on and ``_claim`` groups by. It has to be the
    same or the two disagree about what a unit is: a 'verify' item carries a track
    and no frame, so keying on (video, frame) alone collapses every track of one
    video onto (video, NULL).

    Identity is folded through ``annotation.identity.norm_annotator`` BEFORE the
    raters are counted, and a rater who somehow holds two rows of one unit
    contributes once. The lease guard should make that impossible, but if it ever
    fails the failure must not read as agreement: one person appearing twice is one
    person corroborating themselves, which is the easiest way there is to inflate
    every number below.

    Excluded, with reasons:
      * ``overlap_target <= 1`` — the unit was never dispatched for comparison.
      * practice rows, both by the ``is_practice`` flag and by
        ``quarantined_practice_keys()``. The flag alone is not enough: rejecting a
        run RECYCLES the row and clears the flag, so the durable provenance is the
        quarantine table (which every other corpus measurement here already uses).
      * gold-backed rows. Those are per-labeler copies of an answer key and are
        already marked against it by ``settle_gold_item``; comparing two labelers'
        copies of the same question measures the question, not the cohort.
    """
    ...

def overlap_progress(spec_id: int) -> Dict[str, Any]:
    """What the overlap actually bought, counted in UNITS rather than rows.

    This is the first thing in the codebase to read ``overlap_target`` for anything.
    ``mission_completion`` deliberately collapses a pair to one so a progress bar
    is not inflated; that leaves nobody able to say how much of the redundancy the
    cohort has actually delivered. `paired` is the number of units that reached two
    or more DIFFERENT annotators — the only units on which an agreement figure can
    exist at all.

    Ungated: it counts rows that are already there and changes nothing.
    """
    ...

def _asked_about_scars(data: Dict[str, Any]) -> bool:
    """Was this labeler asked the scar question at all?

    Same rule (and the same three literals) as
    ``database.compute_encounter_consensus``: a pose/keypoint assignment never
    shows the scar form and stores ``scars_visible=""``. That is "not asked", not
    "reported no scars", and counting it as an absence vote fabricates a
    disagreement against somebody who correctly did the task they were given.
    """
    ...

def sides_from_model(data: Dict[str, Any]) -> bool:
    """True when this rater's ``sides_visible`` is a machine answer they accepted.

    The SIDES SEEN control offers a precomputed suggestion with an Accept button
    (``annotation/routes_side_hints.py``), and Accept writes the model's answer
    into the same ``$.sides_visible`` key a hand-picked one goes to. ``accepted``
    on ``$.sides_visible_hint`` is the only thing that tells them apart.
    """
    ...

def sides_seen(data: Dict[str, Any]) -> set:
    """Which flanks this rater says they could see, for ``eligible_raters``.

    ``sides_visible`` is an encounter/frame-level COVERAGE statement — "I could see
    the left side" — and that is exactly the question eligibility asks. It is NOT
    the flank a scar sits on, and must never be used as one: measured end to end,
    ``sides_visible`` agrees with the true per-frame flank 58.2% of the time
    against 97.2% for the pose-derived hint, barely above the 54.5% always-Left
    baseline. Hence nothing below ever copies it onto a scar.

    AN ACCEPTED SUGGESTION IS NOT A HUMAN COVERAGE CLAIM, and this is where that
    matters. ``eligible_raters`` uses this set to decide whose absence votes count
    on which flank: a "Left" narrows that rater's pool, a "Both" widens it
    everywhere. Letting a model answer do the narrowing would make the model a
    silent voter in a human consensus, and nothing downstream could tell. So an
    accepted suggestion returns the empty set — "this rater made no coverage
    claim", which is the widest, most conservative pool and exactly the behaviour
    every row written before the suggestion existed already gets. It is dropped,
    not down-weighted: there is no weight that makes a machine answer partly a
    human one.

    THE ONE DEFINITION. ``app._encounter_scar_inputs`` calls this too. Two copies
    of the rule would drift, and the drift would show up as one consensus surface
    counting an accepted suggestion and another not.
    """
    ...

def _unit_scar_inputs(unit: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve every rater's saved annotation into the shape compute_consensus takes.

    The annotation is looked up through ``_annotation_payload``, which is already
    the module's rule for "what did this person actually save" — by id when the
    client sent one, else by (video, frame, annotator). The save is the evidence;
    the client's own claim about what it drew is not.
    """
    ...

def _cluster_payload(c: Any) -> Dict[str, Any]:
    ...

def _agreement_payload(unit: Dict[str, Any], res: Any, inputs: Dict[str, Any]) -> Dict[str, Any]:
    ...

def _store_agreement(payload: Dict[str, Any], params: Dict[str, Any]) -> None:
    ...

def refresh_unit_agreement(spec_id: int, *, cfg: Optional[Dict[str, Any]]=None, unit_keys: Optional[Sequence[str]]=None, zone_cuts: Optional[Sequence[float]]=None) -> Dict[str, Any]:
    """Compare the cohort's answers on every finished overlap unit, and store them.

    The join this file was missing: group ``done`` work_items by their unit, keep
    the ones two DIFFERENT people finished, resolve each row's annotation, and hand
    the per-annotator scar lists to ``scar_consensus.compute_consensus``.

    Skips are counted and reported rather than silently dropped, because each one
    means something different and an operator has to be able to tell them apart:

      ``no_annotation``  the rows are done but no annotation resolves — a 'verify'
                         unit (its answer lives in track_verifications, not in
                         `annotations`) or a completion whose save never landed.
      ``not_asked``      nobody on this unit was shown the scar form. A pose
                         mission is the normal case; scoring it against the scar
                         consensus would report a failure on a question nobody was
                         asked.
      ``too_few_raters`` fewer than ``min_raters`` raters made a scar claim.
    """
    ...

def _default_zone_cuts() -> Sequence[float]:
    """The body-axis cuts, from the ONE place that defines them.

    Imported here rather than at module scope so ``db_datasets`` keeps importing on
    a box without numpy, and copied nowhere: the forward map (point -> zone) and
    the inverse (zone -> arc span) must walk the same polyline or they disagree
    about where a zone is.
    """
    ...

def redact_agreement_for(unit: Dict[str, Any], me: str) -> Dict[str, Any]:
    """Strip peer identities from one stored comparison, for a labeler.

    Same rule and same reasoning as ``signal_consensus.redact_for``, written
    against THIS payload rather than reusing that function: its shape assumptions
    differ (no ``proposals``, no ``voter_pool``, and two identity-bearing fields it
    has never heard of), so reusing it would leave ``raters`` and ``absent_raters``
    published — precisely the "the same identities leaked through four other
    fields" failure its own docstring describes.

    A labeler needs to know HOW MANY people marked a scar and whether the group
    agreed. They must not learn WHO. Naming peers turns the panel into a social
    signal: you stop labeling what you see and start labeling what the person you
    rate highly saw, which is the anchoring the whole overlap design exists to
    MEASURE rather than induce.

    A withheld collection is returned as ``None``, never as a shorter list. A
    truncated list is a valid-looking value, so ``len(raters)`` would silently mean
    "everyone" for an admin and "just me" for a labeler — the composition that
    rendered a unanimous 3-of-3 signal event as "3/1". Ask "how many" with
    ``n_raters``/``n_voters``; ask "is this mine" with ``mine``.
    """
    ...

def _agreement_row(row) -> Dict[str, Any]:
    ...

def unit_agreement(spec_id: int, *, viewer: Optional[str]=None, is_admin: bool=False, unit_key: Optional[str]=None, cfg: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    """Read the stored comparisons for one mission. No recomputation.

    Disagreement first: units carrying a ``disputed`` scar sort to the top, because
    those are the only rows anybody needs to look at. Non-admin readers get the
    redacted projection — see ``redact_agreement_for``.
    """
    ...
