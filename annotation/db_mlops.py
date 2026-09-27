"""Stream B (MLOps) database helpers — real triage-queue sampling strategies.

The triage queue's ``queue_sampling`` setting names three active-learning
strategies (``most_uncertain`` / ``diverse`` / ``balanced``), but the core
implementation in ``annotation/database.py`` only ever spreads pseudo-randomly
for ``diverse``/``balanced``. This module implements the three strategies for
real, doing the sampling in Python over the same candidate pool.

Design constraints (Stream B ownership contract):
  * ``annotation/database.py`` is NOT modified. We only *read* its connection
    accessor (``get_conn``) and a few pure row helpers
    (``_row_to_track_dict`` / ``_q_gold`` / ``_interleave_gold``) so the API
    response stays byte-identical to the existing route and gold-injection
    behaviour is preserved exactly.
  * Activation is config-gated. ``app.py`` calls into here only when
    ``mlops.sampling.enabled`` is true; otherwise the unchanged
    ``database.get_unverified_tracks()`` path runs (default OFF → prod
    behaviour unchanged).

No embeddings are required: track signatures (``signature_json``) are not yet
populated (Stream A), so ``diverse`` spreads over categorical fields with a
frame-stride fallback. When signatures land, ``diverse`` can swap to k-center
greedy over the embedding with no change to this module's public API.
"""
from __future__ import annotations
import json
import random
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from annotation.database import get_conn, init_track_tables, multi_rater_scope, _row_to_track_dict, _q_gold, _interleave_gold
from annotation import drift_metrics

def _candidate_pool(annotator_email: Optional[str], video_id: Optional[str], target_raters: int=1) -> List[Any]:
    """Fetch the full set of eligible (proposed, propagated) tracks so we can
    sample in Python. The pool is naturally bounded (unverified tracks for one
    annotator/video), so a whole-pool fetch is cheap.

    Who is eligible comes from ``database.multi_rater_scope`` — the SAME rule
    ``get_unverified_tracks`` applies. This sampler used to hardcode
    ``seed_annotator = ?``, so turning on ``mlops.sampling`` silently reverted a
    multi-rater cohort to own-seeds-only: same route, same config, two different
    queues depending on which sampler was selected.
    """
    ...

def count_unverified_pool(annotator_email: Optional[str]=None, video_id: Optional[str]=None, target_raters: int=1) -> int:
    """Size of the eligible (proposed, propagated) pool for an annotator/video —
    used by the AL task-feed to show 'N items remaining'. Cheap COUNT, no sampling."""
    ...

def _mean_conf(row: Any) -> float:
    """Mean of the *populated* auto-confidences. Missing values are skipped; an
    all-missing row scores 0.0 → treated as most uncertain (leads the queue).

    This is a slight improvement over the existing SUM ordering, which penalises
    rows that simply have fewer populated confidence fields.
    """
    ...

def _dedup_adjacent(rows: List[Any], window: int) -> List[Any]:
    """Drop near-duplicate frames (the platform's biggest active-learning
    redundancy risk): within a video keep a track only if its seed frame is at
    least ``window`` frames from an already-kept track. Order-preserving.
    """
    ...

def _diversity_key(row: Any) -> Any:
    """Categorical key for ``diverse`` spreading, with a fallback cascade so the
    strategy still differs from uncertain/random when auto fields are sparse:
    (auto_zone, auto_side) → coarse (video, frame-stride) bucket.
    """
    ...

def _balance_key(row: Any) -> Any:
    """Single class key for ``balanced`` representation (coarser than the
    diversity key): auto_zone → auto_side → unknown bucket.
    """
    ...

def _round_robin(rows: List[Any], keyfn) -> List[Any]:
    """Interleave rows across buckets keyed by ``keyfn`` — one per bucket per
    pass — so the head of the queue spreads across categories instead of
    clustering. Buckets and within-bucket order follow input order (stable).
    """
    ...

def sample_unverified_tracks(annotator_email: Optional[str]=None, video_id: Optional[str]=None, limit: int=50, strategy: str='most_uncertain', gold_inject_ratio: float=0.0, adjacent_frame_window: int=30, inject_low_trust: bool=False, low_trust_ratio: float=0.0, low_trust_max_quality: float=0.6, target_raters: int=1) -> List[Dict]:
    """Real triage-queue sampling. Drop-in replacement for
    ``database.get_unverified_tracks`` with identical args, return shape, the
    200 hard-cap, and gold-injection behaviour — only the strategy logic is real.

      * ``most_uncertain`` — ascending mean populated auto-confidence.
      * ``diverse``        — de-dup adjacent frames, then round-robin across
                             (auto_zone, auto_side) categories (frame-stride
                             fallback when those are null).
      * ``balanced``       — round-robin across a single class key so rare
                             classes are over-represented vs random; degrades to
                             ``diverse`` when there is <2 class signal.

    Phase B1 — ``inject_low_trust`` (default OFF, so existing callers are
    byte-identical) resurfaces already-verified tracks whose cached
    label-quality ``overall_trust`` is below ``low_trust_max_quality`` for a
    second opinion, interleaved like gold. Tracks this annotator already
    verified are excluded so they re-rate someone *else's* uncertain label.
    """
    ...

def _ensure_label_quality_tables():
    """Idempotent CREATE IF NOT EXISTS mirror of migration v22, so recompute works
    even before init_db has been re-run (same defensive pattern as
    ``database.init_track_tables``). v22 remains the source of truth at deploy."""
    ...

def _load_verifications(conn) -> List[Dict]:
    ...

def _load_weights(conn) -> Dict[str, float]:
    """annotator email → experience_weight × proficiency_weight (mirrors
    ``database._annotator_weight``; missing user → 1.0)."""
    ...

def _load_auto_hints(conn) -> Dict[int, Dict[str, Any]]:
    """track_id → pose/auto hint in the SAME categorical domains as the human
    fields, so it can be folded into CROWDLAB pred_probs as an independent
    pseudo-annotator for zone/side/color."""
    ...

def _load_gold_truth(conn) -> Dict[int, Dict[str, str]]:
    """Gold tracks' trusted labels (= canonical ``tracks.human_*``) used to validate
    each aggregation method against ground truth."""
    ...

def recompute_label_quality(*, method: str='auto', min_multi_rater: int=5, laplace_alpha: float=1.0, use_auto_hints: bool=True, run_gold_validation: bool=True) -> Dict[str, Any]:
    """Recompute the label-quality cache from ``track_verifications`` and write the
    v22 tables (full rebuild — caches never carry stale rows). Returns a summary
    dict including the gold-validation comparison. Cheap + idempotent."""
    ...

def get_track_label_quality(track_id: int) -> Optional[Dict]:
    ...

def get_annotator_quality() -> List[Dict]:
    """Per-annotator quality table, worst first."""
    ...

def low_trust_track_ids(max_quality: float=0.6, limit: int=50, exclude_annotator: Optional[str]=None) -> List[Dict]:
    """Lowest-trust verified tracks (for an admin re-verification view). Returns
    [{track_id, overall_trust, n_voters, ...}] ascending by trust."""
    ...

def get_last_label_quality_run() -> Optional[Dict]:
    ...

def _q_low_trust(annotator_email: Optional[str], video_id: Optional[str], max_quality: float, n: int):
    """Full track rows for low-trust *verified* tracks, for queue injection.
    Excludes tracks ``annotator_email`` already verified so they add a fresh
    opinion. Shape mirrors ``_q_gold`` so ``_interleave_gold`` + ``_row_to_track_dict``
    work unchanged."""
    ...

def feed_proficiency_weight(blend: float=0.5, *, dry_run: bool=True, clamp_lo: float=0.0, clamp_hi: float=1.5) -> Dict[str, Any]:
    """Blend cached per-annotator quality into ``users.proficiency_weight``
    (``new = (1-blend)*baseline + blend*quality``). dry_run (default) previews without
    writing. Apply calls the existing ``database.update_user_weights`` setter — the
    one sanctioned write path (it also invalidates the encounter consensus cache).

    The ``(1-blend)`` term is the STABLE baseline ``users.quiz_weight``, not
    ``proficiency_weight``, which is this function's own output. Reading the output back
    in made the update a recurrence, ``p(n+1) = (1-b)*p(n) + b*q``, so every re-run
    dragged the weight another step toward ``quality`` on no new evidence at all — at
    the default blend, four clicks of an admin button that looks read-only leave 6% of
    the original judgement. It is the same defect already fixed in
    ``database.update_composite_proficiency``, and fixed the same way: the baseline is
    captured once (from the current weight, for rows that predate ``quiz_weight``) and
    only an admin moves it afterwards, so re-running with unchanged inputs is idempotent.

    That is also why the write passes ``set_baseline=False``: the sanctioned setter
    normally treats a written weight as the admin's new baseline judgement, which would
    reintroduce the feedback loop through ``quiz_weight`` instead.
    """
    ...

def _column_exists(conn, table: str, column: str) -> bool:
    ...

def _ensure_golden_tables():
    """Idempotent CREATE IF NOT EXISTS mirror of migration v23 (same defensive
    pattern as the v22 cache), plus the guarded ALTERs for columns added since;
    v23 stays the source of truth at deploy."""
    ...

def _label_quality_cache_rows(conn) -> Optional[int]:
    """Row count of the v22 label-quality cache, or None if the table is absent.

    `recompute_label_quality` is CLI-only (scripts/orchestrator.py), so on a normal
    deployment this cache is EMPTY and every candidate's `trust` is NULL. That is a
    fact about the DB, not about the tracks, and it is the difference between "no
    track was good enough" and "no track was ever scored" — so it is read directly
    rather than inferred from an empty candidate list."""
    ...

def _golden_candidates(conn) -> List[Dict]:
    """Verified tracks eligible for the golden set, each with its eval frame, GT
    box, GT labels, GT confidence, and (when available) v22 trust/agreement as
    DIAGNOSTICS.

    Labels come from ``tracks.*`` — the same columns the training exporter reads.
    See the note at the `label_source` assignment below for why the eval set may
    not have its own opinion about ground truth."""
    ...

def _assign_tier(c: Dict, freq: Dict[str, int], rare_cut: int, high_trust: float, low_trust: float) -> str:
    """Heuristic difficulty tier (research target mix 60/30/10):
      adversarial — low trust, OR a rare scar type, OR genuine multi-rater
                    disagreement that was resolved (n≥2 & agreement<0.7);
      common      — high trust AND a frequent scar type;
      tricky      — everything in between. When trust is null (no v22 cache) the
                    tier is decided by class frequency alone."""
    ...

def build_golden_eval_set(name: str='golden_v1', *, target_size: int=150, tier_ratios: Sequence[float]=(0.6, 0.3, 0.1), high_trust: float=0.8, low_trust: float=0.5, min_trust: float=0.0, min_raters: int=3, seed: int=42, created_by: Optional[str]=None, notes: str='', dry_run: bool=False) -> Dict[str, Any]:
    """Curate + FREEZE a golden eval set from verified tracks. Each build is a new
    immutable version (``version = max(existing)+1``). Deterministic for a fixed
    seed. ``dry_run`` returns the composition preview without writing.

    Tiers target ``tier_ratios`` of ``target_size``; a thin tier is capped at its
    availability (coverage over raw size) and the shortfall is reported, never
    backfilled across tiers (keeps tier semantics honest).

    The result always carries ``reason`` / ``warnings`` / ``trust_coverage``: a set
    that came back empty or lopsided because nothing was ever *scored* must not be
    mistaken for one where nothing was good enough. See the trust block below."""
    ...

def list_golden_eval_sets() -> List[Dict]:
    ...

def get_golden_eval_set(set_id: Optional[int]=None, name: Optional[str]=None, version: Optional[int]=None) -> Optional[Dict]:
    """Resolve a set row by id, or by (name, version) — version omitted → latest."""
    ...

def get_golden_eval_items(set_id: int) -> List[Dict]:
    """Items of a frozen set, bbox JSON parsed back to a dict."""
    ...

def _ensure_orchestrator_tables():
    """Idempotent CREATE IF NOT EXISTS mirror of v20+v21 (same defensive pattern as
    the other mlops caches); v20/v21 stay the source of truth at deploy."""
    ...

def register_model(model_type: str, artifact_path: Optional[str], *, metrics: Optional[Dict]=None, primary_metric: Optional[float]=None, trained_from_run_id: Optional[int]=None, n_train_items: Optional[int]=None, golden_set: Optional[str]=None, notes: str='', status: str='registered') -> Dict:
    """Record a trained artifact + its golden-set eval. Never champion on insert —
    promotion is a separate, gated step. version auto-increments per model_type."""
    ...

def get_model(model_id: int) -> Optional[Dict]:
    ...

def list_models(model_type: Optional[str]=None) -> List[Dict]:
    ...

def get_champion(model_type: str) -> Optional[Dict]:
    ...

def promote_model(model_id: int) -> Dict:
    """Make model_id the champion of its type (registry only — the orchestrator
    handles the filesystem deploy pointer). The prior champion is RETIRED, not
    deleted, so rollback can restore it. Returns {promoted, previous_champion_id}."""
    ...

def rollback_champion(model_type: str) -> Dict:
    """One-step rollback: demote the current champion and restore the most-recently
    retired prior champion. Returns {rolled_back_to, demoted} or {error}."""
    ...

def create_run(model_type: str='detector', *, trigger_reason: str='manual', requested_by: Optional[str]=None, status: str='requested', notes: str='') -> Dict:
    ...

def update_run(run_id: int, **fields) -> None:
    """Advance a run's persisted state. dict-valued gate_json/metrics_json are
    JSON-encoded. updated_at is always bumped."""
    ...

def get_run(run_id: int) -> Optional[Dict]:
    ...

def latest_run(model_type: Optional[str]=None) -> Optional[Dict]:
    ...

def list_runs(limit: int=20, model_type: Optional[str]=None) -> List[Dict]:
    ...

def next_requested_run(model_type: Optional[str]=None) -> Optional[Dict]:
    """Oldest queued run (status='requested') — the cron orchestrator picks these up."""
    ...

def count_verified_tracks(since: Optional[str]=None) -> int:
    """Verified (human-confirmed) tracks, optionally since an ISO timestamp — the
    data-volume retrain trigger. Only HUMAN-verified tracks count (never train on
    auto-proposals → feedback collapse)."""
    ...

def has_open_run(model_type: Optional[str]=None) -> bool:
    """True if a run is already queued or in flight — used to avoid stacking duplicate
    drift-triggered retrain requests."""
    ...

def _ensure_drift_tables():
    """Idempotent CREATE IF NOT EXISTS mirror of migration v24 (same defensive pattern
    as the other mlops caches); v24 stays the source of truth at deploy."""
    ...

def _parse_snap(r) -> Optional[Dict]:
    ...

def set_drift_baseline(model_type: str, signal: str, ref: Any, *, n_ref: Optional[int]=None, label: Optional[str]=None, created_by: Optional[str]=None, notes: str='') -> Dict:
    """Freeze a reference for one signal, deactivating any prior active baseline (so
    exactly one is active per model_type+signal). ``ref`` is a JSON-able summary:
    label proportions / embedding centroid summary / {metric}. The natural moment to
    (re)baseline is right after a model is promoted — drift is measured from there."""
    ...

def get_active_baseline(model_type: str, signal: str) -> Optional[Dict]:
    ...

def record_drift_snapshot(model_type: str, signal: str, *, score: Optional[float], severity: str, n_current: Optional[int]=None, baseline_id: Optional[int]=None, warn_thr: Optional[float]=None, alarm_thr: Optional[float]=None, triggered: int=0, run_id: Optional[int]=None, detail: Optional[Dict]=None) -> Dict:
    ...

def mark_snapshot_triggered(snapshot_id: int, run_id: Optional[int]) -> None:
    ...

def latest_drift_snapshot(model_type: str, signal: str) -> Optional[Dict]:
    ...

def list_drift_snapshots(limit: int=50, model_type: Optional[str]=None, signal: Optional[str]=None) -> List[Dict]:
    ...

def latest_drift_alarm(model_type: str, *, since: Optional[str]=None) -> Optional[Dict]:
    """Most recent ALARM snapshot (optionally newer than ``since`` ISO ts) — the pull
    path the orchestrator's trigger check reads to turn drift into a retrain."""
    ...

def drift_status(model_type: str='detector') -> Dict:
    """Latest snapshot + active baseline per signal, plus an overall alarm flag — the
    read model behind the admin /drift endpoint and the mlops_admin panel."""
    ...

def _verified_window_rows(conn, cutoff_iso: Optional[str]):
    ...

def _vectors_from_rows(rows):
    """Parse tracks.signature_json → embeddings, grouped by the self-describing
    ``model`` tag; returns (dominant_model, vectors) for the DOMINANT model only so we
    never compare embeddings produced by different models/versions."""
    ...

def _registry_metrics(conn, model_type: str, golden_set: Optional[str]=None) -> List[Dict]:
    """Rows eligible to be a degradation REFERENCE.

    Two restrictions, both load-bearing:
      * same golden_set — metrics from different frozen eval sets are not
        comparable; that is the premise of the eval gate itself, which re-scores
        the incumbent rather than compare across versions.
      * promoted_at IS NOT NULL — a never-served challenger is not evidence the
        champion got worse. run_cycle deliberately registers a gate-PASSING
        challenger and stops when deploy is off, so without this the safe default
        configuration alarmed on its own success ("the champion degraded" for
        "a better model exists"). Retired rows STAY IN: a retired row is a
        previously served champion and is the only honest reference for "we got
        worse".
    """
    ...

def _build_label_reference(fields: Sequence[str]) -> Dict:
    """Frozen label reference = proportions per field over ALL verified tracks at
    set-time (broad, stable). Stored compactly in the baseline row."""
    ...

def _drift_label(rows, n_current, model_type, lc, min_current, set_if_missing, created_by) -> Dict:
    ...

def _drift_embedding(rows, model_type, ec, min_current, set_if_missing, created_by) -> Dict:
    ...

def _drift_performance(model_type, pc) -> Dict:
    ...

def compute_drift(monitor_cfg: Optional[Dict]=None, *, model_type: str='detector', set_baseline_if_missing: bool=True, created_by: str='monitor') -> Dict:
    """Score every enabled drift signal for ``model_type`` and persist one snapshot
    each (v24). Pure read + arithmetic + its-own-table writes — no model inference, no
    training, no deploy. First run per signal auto-freezes a baseline (severity
    'no_baseline') so the next cycle has a reference. Returns a summary; the alerting
    + retrain-queue decision is the caller's (scripts/monitor_drift.py)."""
    ...

def reset_drift_baselines(model_type: str='detector', monitor_cfg: Optional[Dict]=None, *, signals: Optional[Sequence[str]]=None, created_by: str='admin') -> Dict:
    """Re-freeze the reference window(s) from the CURRENT data — the right move right
    after a model is promoted (drift should be measured from the new normal). Drops the
    active baseline(s) then recomputes (label/embedding auto-refreeze; performance uses
    the live best). Returns the fresh snapshot summary."""
    ...
