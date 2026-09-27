"""Stream C (gamification) — read-mostly stats + blind-gold Q-score.

Phase C0: surface signals that already exist (quota, live counts, experience
tier) WITHOUT touching ``database.py`` core or the consensus algorithm.

Phase C1: compute a per-user **Q-score** (DiagnosUs-style) — trailing-window
accuracy on blind ``is_gold`` calibration tracks — and cache it in this stream's
own ``gamification_user_state`` table (migration v30). This module owns that
table; it never edits ``database.py``. It *reads* the existing
``track_verifications`` / ``tracks`` data and reuses the canonical annotator
weighting so the notion of "consensus" can't drift from the platform's.

**Q-score definition (leave-one-out, accuracy-on-gold, not volume):**
For each gold track the annotator verified, the "correct answer" is the
weighted-mode consensus of the *other* annotators' verifications (the scored
annotator is excluded, so a high-weight rater can't be graded against an answer
their own vote defined, and a gold track only that annotator ever verified is
skipped as ungradable). Per-item agreement is the fraction of comparable fields
(scar_type / zone / side / color) that match. The Q-score is the mean over the
most-recent ``window`` gradable gold checks. It is *coaching* feedback for the
lab — surfaced privately and encouragingly, never punitively, never ranked.

**Stream B contract (read-only):** Stream B may consume per-annotator label
quality via ``get_qscore(email)`` (returns the cached row) or by reading the
``gamification_user_state`` table directly. Neither stream rewrites the other's
logic; both read the same gold/verification tables.

Phase C2: mastery/progression. ``evaluate_achievements`` unlocks quality-weighted
**badges** (persisted in ``gamification_achievements``, migration v31; once earned
they stay earned — reinforcement, not punishment), ``update_streak`` maintains a
gentle daily-activity streak, and ``_impact_count`` surfaces how many catalog
sharks a user's work touched (reads Stream A's links; 0 until populated). All are
private, non-competitive, and config-gated.

Phase C4: citizen-science-ready hardening behind the ``gamification.profile:
lab|public`` seam. The trusted lab cohort (default ``profile: lab``) is COMPLETELY
UNAFFECTED — every C4 function short-circuits to "everyone trusted / pass-through"
and the lab ``/api/me/stats`` payload is byte-identical (C4 adds only NEW routes;
it does not touch ``get_user_stats``). Flip ``profile: public`` and the same code
applies the DiagnosUs trust spine to an untrusted crowd:
  * **Q-score GATING** — ``contributor_trust`` discards a contributor whose blind-
    gold reputation is below ``public.gate_min_qscore``.
  * **reputation-from-scratch** — public reputation is the gold Q-score ONLY (the
    lab experience/proficiency priors are ignored), so trust is earned, not granted.
  * **higher redundancy** — ``aggregate_gated_consensus`` requires
    ``public.min_redundancy`` *trusted* verifications before a track's answer counts.
  * **heavier onboarding** — ``onboarding_status`` gates counting on finishing all
    tutorials + a practice minimum.
  * **moderation hooks** — ``gamification_moderation`` (migration v33) lets an admin
    block/flag a contributor; the gate consults it.
All knobs live under ``gamification.public`` and default safe; the gate, the gated
aggregation and the gating summary are READ-ONLY (they never write to ``tracks`` /
``consensus_cache`` — ``database.compute_track_consensus`` remains the canonical
lab writer; this is a parallel public-profile view).
"""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from annotation.database import get_conn, get_user, get_progress_counts, _experience_tier, _annotator_weight, _column_exists
MAX_LEVEL = 10
STEP = 100
QSCORE_WINDOW = 20
QSCORE_AGREEMENT_THRESHOLD = 0.5
QSCORE_MIN_CHECKS = 3

def init_gamification_tables() -> None:
    """Create the gamification tables if absent, and apply additive columns.

    NOT migration-only. Migrations run at Docker build time against a throwaway
    layer, so a column that exists only in scripts/migrate_schema_vNN.py never
    reaches the production volume DB. Same reasoning as
    db_datasets.init_dataset_tables. (An earlier version of this docstring said
    ALTERs were migration v31's job. In production that is wrong, and it is how a
    table came to be missing there for months.)

    CREATE TABLE IF NOT EXISTS also no-ops on a table that already exists, so a DB
    migrated to v30 but not v31/v32 keeps the original column set and every read of
    a streak or opt-in column raises `no such column` -- hence the guarded ALTER.
    """
    ...

def _experience_level(annotation_count: int) -> int:
    """Map annotation_count to a 1..10 level (same 100-step ladder as the engine)."""
    ...

def _next_level_at(level: int) -> Optional[int]:
    """Annotation count needed to reach the next level, or None if maxed."""
    ...

def _norm(v) -> Optional[str]:
    """Normalize a controlled-vocab field for comparison (None/'' -> None)."""
    ...

def _weighted_mode_answer(conn, rows: List) -> Dict[str, Optional[str]]:
    """Weighted-mode consensus per field over the given verification rows.

    Mirrors ``database.compute_track_consensus.vote()`` (weight = experience ×
    proficiency × confidence/5; argmax per field with most-recent ``verified_at``
    as tie-break). Original casing is preserved in the returned value. Rows are
    expected to already EXCLUDE the annotator being scored.
    """
    ...

def _item_agreement(gold: Dict, mine: Dict) -> Optional[float]:
    """Fraction of comparable fields that match (None if nothing comparable).

    A field is comparable only when BOTH the gold answer and the annotator's
    answer supply it — so a null color on either side simply doesn't count
    against the annotator.
    """
    ...

def compute_qscore(email: str, *, window: int=QSCORE_WINDOW, threshold: float=QSCORE_AGREEMENT_THRESHOLD) -> Dict:
    """Compute (read-only) the trailing-window blind-gold Q-score for one user.

    Returns ``{qscore, n_checks, n_agreed, window}``. ``qscore`` is the mean
    per-item field-agreement over the most-recent ``window`` *gradable* gold
    checks (None if there are none); ``n_checks`` is how many were gradable;
    ``n_agreed`` is how many met ``threshold``. Does NOT write — see
    ``refresh_qscore``.
    """
    ...

def store_qscore(email: str, result: Dict, *, touch_active: bool=True) -> None:
    """Upsert a user's Q-score into gamification_user_state.

    ``touch_active`` updates ``last_active`` (true for a live stats load; false
    for an admin batch recompute so it doesn't fake activity).
    """
    ...

def get_qscore(email: str) -> Optional[Dict]:
    """Read the cached gamification state for one annotator (Stream B contract).

    Returns the stored row as a dict, or None if never computed. Read-only — does
    not recompute; call ``refresh_qscore`` for a fresh value.
    """
    ...

def refresh_qscore(email: str, *, window: int=QSCORE_WINDOW, threshold: float=QSCORE_AGREEMENT_THRESHOLD, touch_active: bool=True) -> Dict:
    """Compute the Q-score and cache it. Returns the compute result.

    Storage is best-effort: a failed cache write (e.g. read-only DB) must never
    break the stats read path, so it is swallowed.
    """
    ...

def recompute_all_qscores(*, window: int=QSCORE_WINDOW, threshold: float=QSCORE_AGREEMENT_THRESHOLD) -> int:
    """Recompute + cache the Q-score for every annotator who has verified a gold
    track. Returns the number of users recomputed. Admin/backfill path — does not
    touch ``last_active``.
    """
    ...

def _safe(fn, default):
    """Run fn(); on any error return default. C2 surfacing must never break the
    stats read path (matches C1's best-effort posture)."""
    ...

def level_name(level: int) -> str:
    """Name for an experience level; empty string if out of range."""
    ...

def _verified_track_count(conn, email: str) -> int:
    ...

def _impact_count(email: str) -> int:
    """Distinct catalog sharks linked to encounters this annotator worked on.

    Reads Stream A's ``encounter_priority.shark_catalog_id`` link; returns 0 today
    (catalog unpopulated) and lights up automatically once re-ID / manual linking
    lands. Read-only.
    """
    ...

def _tutorial_steps(user: Dict) -> int:
    """Count completed guided tutorials (0..3) from users.tutorial_states JSON.
    The legacy ``has_seen_tutorial`` flag counts as the 'overview' step.

    Deliberately only these three, even though ``db.TUTORIAL_NAMES`` is longer: they are
    the tours every labeler meets on every install. ``signals`` ships off by default and
    ``follow_scar`` needs a tracker, so counting either would make onboarding
    uncompletable — and the Tutorial Master badge unearnable — wherever that feature is
    not enabled. Add a name here only if it is unconditionally reachable.
    """
    ...

def update_streak(email: str) -> Dict:
    """Advance the daily-activity streak for one user and return {current, longest}.

    "Active" = the annotator app loaded /api/me/stats today. Consecutive days
    increment; a gap resets current to 1. ``longest`` is the personal best.
    Never punitive — a broken streak is silent. Upserts into gamification_user_state
    without touching the qscore columns.
    """
    ...

def _collect_signals(email: str, *, user: Dict, qscore_result: Optional[Dict], streak: Optional[Dict]) -> Dict:
    """Assemble the badge-evaluation signal bundle from already-fetched pieces."""
    ...

def _cached_qscore(email: str) -> Dict:
    """Read the cached Q-score as a {qscore, n_checks} bundle for badge evaluation.

    READ-ONLY: C2 never recomputes the Q-score — C1 (the calibration stats load)
    and the admin recompute own populating the v30 cache. Empty cache -> {None, 0}.
    """
    ...

def build_signals(email: str, *, qscore_cfg: Optional[Dict]=None) -> Dict:
    """Assemble the badge-evaluation signal bundle for a user.

    READ-ONLY on the Q-score: reads the v30 cache via get_qscore rather than
    recomputing (C1 / the admin recompute own populating it). Updates the
    C2-owned streak. ``qscore_cfg`` is accepted for signature stability but unused
    — the window/threshold are already baked into the cached value.
    """
    ...

def evaluate_achievements(email: str, signals: Dict, *, show_locked: bool=True) -> Dict:
    """Unlock newly-earned badges (persist) and return earned + next-up.

    A badge, once earned, STAYS earned (rows persist; never revoked if a signal
    later dips). ``next_up`` is the up-to-3 closest locked badges by progress.
    """
    ...

def get_achievements(email: str) -> List[Dict]:
    """Read a user's persisted earned badges (no recompute). For external/Stream
    reads; the annotator path uses evaluate_achievements which also unlocks."""
    ...
SKILL_MIN_CHECKS = 5
SKILL_TRUSTED_MIN = 0.85
SKILL_NOVICE_MAX = 0.6

def compute_skill(email: str, *, min_checks: int=SKILL_MIN_CHECKS, trusted_min: float=SKILL_TRUSTED_MIN, novice_max: float=SKILL_NOVICE_MAX) -> Dict:
    """Measured skill tier for one annotator (READ-ONLY).

    Basis preference: blind-gold Q-score (when >= ``min_checks`` gradable checks)
    -> proficiency_weight -> a conservative experience prior. ``is_expert``
    short-circuits to 'trusted'. A new user with only the experience prior can
    never reach 'trusted' on prior alone.
    """
    ...

def route_policy(tier: str) -> Dict:
    """Map a skill tier to a routing policy (copy, so callers can't mutate)."""
    ...

def get_next_task(email: str, *, is_admin: bool=False, video_id: Optional[str]=None, routing_cfg: Optional[Dict]=None) -> Dict:
    """Skill-routed next task: drives Stream B's AL sampler with skill-derived
    difficulty/redundancy. READ-ONLY (samples, never mutates). Degrades to
    disabled if routing is off or B's engine is unavailable.
    """
    ...

def get_active_team_goal(coop_cfg: Optional[Dict]=None) -> Optional[Dict]:
    """The active goal from the v32 table (most-recent active, within its period),
    or a config-defined default when the table has none (so enabling the feature
    works out of the box). Returns the goal dict or None."""
    ...

def team_goal_progress(goal: Dict, *, email: Optional[str]=None) -> Dict:
    """Collective progress (and optionally one user's contribution) toward a goal's
    metric within its period. READ-ONLY over track_verifications."""
    ...

def get_coop_opt_in(email: str) -> bool:
    ...

def set_coop_opt_in(email: str, opt_in: bool) -> bool:
    """Set a user's cooperative-goal opt-in (the social element is opt-in)."""
    ...

def create_team_goal(*, name: str, metric: str, target: int, period_days: Optional[int]=None, created_by: str='', activate: bool=True) -> Dict:
    """Admin: create (and optionally activate) a cooperative goal. Activating one
    deactivates any other active goal so there is a single current target."""
    ...

def get_team_goal_payload(email: str, *, coop_cfg: Optional[Dict]=None) -> Dict:
    """Annotator-facing cooperative-goal view: the active goal, collective progress,
    and this user's own opt-in + contribution. Cooperative — never a ranking."""
    ...
PUBLIC_GATE_MIN_QSCORE = 0.7
PUBLIC_GATE_MIN_CHECKS = 5
PUBLIC_MIN_REDUNDANCY = 3
ONBOARDING_MIN_TUTORIALS = 3
ONBOARDING_MIN_PRACTICE = 10

def resolve_profile(cfg: Optional[Dict]) -> str:
    """Normalize ``gamification.profile`` to 'lab' (default) or 'public'."""
    ...

def public_policy(cfg: Optional[Dict]) -> Dict:
    """Assemble the public-profile knobs from ``gamification.public`` config,
    falling back to the C4 defaults. Pure — reads config, touches no DB."""
    ...

def set_moderation(email: str, status: str, *, reason: Optional[str]=None, track_id: Optional[int]=None, created_by: str='') -> Optional[Dict]:
    """Record a moderation decision against a contributor (account-level when
    ``track_id`` is None). Append-only log; the most-recent account-level row is
    the live status. Returns the new row summary."""
    ...

def get_moderation(email: str) -> Optional[Dict]:
    """Most-recent ACCOUNT-LEVEL moderation row (track_id IS NULL) for a user, or
    None. Read-only."""
    ...

def is_blocked(email: str) -> bool:
    """True iff the contributor's live account-level status is 'blocked'."""
    ...

def list_moderation(status: Optional[str]=None) -> List[Dict]:
    """All moderation rows (optionally filtered by status), most-recent first."""
    ...

def contributor_reputation(email: str, *, from_scratch: bool=True, min_checks: int=PUBLIC_GATE_MIN_CHECKS) -> Dict:
    """A contributor's reputation in [0, ~1.5] with its basis (READ-ONLY).

    ``from_scratch`` (the public default): reputation is the cached blind-gold
    Q-score and ONLY that — until they have ``min_checks`` gradable gold checks
    they are 'unproven' (reputation 0.0), so trust is earned, never inherited
    from a lab experience/proficiency prior. ``from_scratch=False`` keeps the lab
    fallback (proficiency → conservative experience prior) for completeness.
    """
    ...

def onboarding_status(email: str, *, policy: Dict) -> Dict:
    """First-session onboarding completion for a contributor (READ-ONLY).

    Complete = all required guided tutorials done AND a practice-annotation
    minimum reached (the 'win the first session' lever for the public crowd —
    plans/03 §6 C4). When onboarding is disabled it is trivially complete.
    """
    ...

def contributor_trust(email: str, *, profile: str, cfg: Optional[Dict]=None) -> Dict:
    """Should this contributor's work COUNT? (READ-ONLY.)

    LAB profile: always trusted (the gate is inert — lab behaviour unchanged).
    PUBLIC profile: trusted only when NOT moderation-blocked, onboarding is
    complete, and reputation (gold Q-score, from scratch) meets
    ``public.gate_min_qscore``. ``reasons`` explains every gate that failed so the
    UI can coach ("finish onboarding", "earn calibration checks").
    """
    ...

def aggregate_gated_consensus(track_id: int, *, profile: str, cfg: Optional[Dict]=None) -> Dict:
    """The accepted answer for a track AFTER trust-gating its verifications
    (READ-ONLY — never writes ``tracks`` / ``consensus_cache``).

    PUBLIC: drop verifications from untrusted contributors (Q-score gate +
    moderation + onboarding), then require ``public.min_redundancy`` *trusted*
    votes before producing an answer (``sufficient`` false otherwise → the track
    does not count yet). LAB: every voter is trusted and redundancy is 1, so the
    weighted-mode answer matches ``database.compute_track_consensus`` over all
    voters (this is the read-only mirror; the canonical writer is untouched).
    Aggregation reuses ``_weighted_mode_answer`` so the weighting cannot drift.
    """
    ...

def gating_summary(*, profile: str, cfg: Optional[Dict]=None) -> Dict:
    """Admin "what happens if we go public" view: for every contributor who has
    verified a track, whether their work would COUNT under ``profile`` and why
    not. READ-ONLY."""
    ...

def get_trust_payload(email: str, *, cfg: Optional[Dict]=None) -> Dict:
    """Annotator-facing 'your standing' view. In LAB it's a trivial trusted note;
    in PUBLIC it surfaces reputation + onboarding progress so a new contributor
    knows what to finish before their work counts. Coaching, never punitive."""
    ...

def _agreement_band(rate: Optional[float]) -> Optional[str]:
    """Qualitative agreement feedback for an annotator — never a bare percentage.

    A number invites ranking against classmates; a band says the same useful thing
    ("you're in step with the group" / "worth a second look") without doing that.
    ``None`` means not enough data yet, which the client renders as encouragement.
    """
    ...

def get_user_stats(email: str, *, include_quality: bool=True, for_admin: bool=False, qscore_cfg: Optional[Dict]=None, achievements_cfg: Optional[Dict]=None, streaks_cfg: Optional[Dict]=None, impact_cfg: Optional[Dict]=None, routing_cfg: Optional[Dict]=None) -> dict:
    """Compose the annotator's own stats from existing reads.

    Returns ``progress`` (live counts + goals), ``experience`` (level/weight),
    optionally ``quality`` (consensus agreement + proficiency), a C1 ``calibration``
    block (blind-gold Q-score), and C2 ``achievements`` / ``streak`` / ``impact``
    blocks — each gated by its config subsection. The Q-score and streak are each
    computed at most ONCE per call and reused across the calibration + achievement
    paths. ``scar_goal`` is the user's ``semester_quota``; ``pose_goal`` is supplied
    by the route. Missing users degrade to safe defaults rather than raising.
    """
    ...
