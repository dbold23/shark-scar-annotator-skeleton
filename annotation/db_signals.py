"""Stream F — signal annotation storage (deployments, sources, vocabularies, labels).

Per the integration contract (`plans/00-SHARED-CONTEXT.md` §3.2) this is a per-stream DB
module: it reuses `get_conn()` from `annotation/database.py` and never edits that
monolith or the consensus algorithm. Tables are created by
`scripts/migrate_schema_v60.py`; `init_signals_tables()` mirrors that DDL so the module
also works on a fresh checkout or in tests before the formal migration has run.

Two invariants this module enforces, because nothing downstream can recover from them
being wrong:

1. **Times are seconds on the deployment clock.** Callers hand in whatever their pane
   uses; conversion happens at the edge (`annotation/routes_signals.py`), and what lands
   here is already deployment-relative.
2. **A geometry is validated before it is stored.** A box without a frequency extent, or
   an interval that ends before it starts, is rejected rather than normalised into
   something plausible — a silently "fixed" annotation is indistinguishable from a real
   one once it reaches an archive.
"""
from __future__ import annotations
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from annotation.database import get_conn, _column_exists
from annotation.signal_consensus import ALL_SOURCES
from .identity import norm_annotator as _norm_annotator
_MAX_RETRY = 3

def init_signals_tables() -> None:
    """Idempotently ensure the Stream F tables exist and are current.

    Creates anything missing (mirrors v60), then brings a pre-existing v60 table
    up to the v61/v62 column set with a guarded ALTER. Both halves are needed:
    migrations do not auto-run in production, and CREATE TABLE IF NOT EXISTS
    cannot add a column to a table that already exists."""
    ...

def _retry_write(fn):
    """Run a write closure, retrying on 'database is locked' (mirrors core CRUD)."""
    ...

def _now() -> str:
    """Timezone-aware UTC timestamp.

    Diverges from the naive `datetime.utcnow()` used elsewhere in the codebase (and
    deprecated since 3.12) on purpose: this stream's entire premise is that times are
    unambiguous, and a bookkeeping column that silently reads as local time is exactly
    the ambiguity it exists to remove.
    """
    ...

def _row(r: Optional[sqlite3.Row]) -> Optional[dict]:
    ...

def _rows(rs: Iterable[sqlite3.Row]) -> List[dict]:
    ...

def create_deployment(*, code: str, t0_utc: str, site: Optional[str]=None, animal_id: Optional[str]=None, notes: str='', created_by: Optional[str]=None) -> Optional[dict]:
    """Create a deployment. Returns the stored row, or None if the code is taken."""
    ...

def get_deployment(deployment_id: int) -> Optional[dict]:
    ...

def get_deployment_by_code(code: str) -> Optional[dict]:
    ...

def list_deployments(*, annotator: Optional[str]=None) -> List[dict]:
    """All live deployments, or only those assigned to ``annotator``."""
    ...

def add_source(*, deployment_id: int, kind: str, uri: Optional[str]=None, drive_id: Optional[str]=None, label: Optional[str]=None, t0_offset_s: float=0.0, offset_source: str='declared', drift_ppm: float=0.0, duration_s: Optional[float]=None, meta: Optional[Dict[str, Any]]=None) -> Optional[dict]:
    """Attach a media/data file to a deployment.

    ``meta`` is the frozen render lattice from ``signals.sources.SourceSpec.to_meta()``
    for waterfall kinds. It is stored verbatim and never regenerated.
    """
    ...

def _source_row_to_dict(r: sqlite3.Row) -> dict:
    ...

def get_source(source_id: int) -> Optional[dict]:
    ...

def list_sources(deployment_id: int) -> List[dict]:
    ...

def update_source_offset(source_id: int, *, t0_offset_s: float, offset_source: str='manual', drift_ppm: Optional[float]=None, changed_by: Optional[str]=None) -> bool:
    """Re-align one source, carrying its existing labels with it.

    This is the knob a labeler turns when audio and video drift apart — and moving it
    **must** move the labels. A label is drawn on a source's own pixels; its
    deployment-clock time is a derived value that was frozen at insert
    (``routes_signals.signals_create_label`` converts ``time_basis='source'`` once, on
    the way in). Leaving those frozen while the mapping underneath them changes would
    silently displace every existing label on this source by the offset delta — the same
    class of bug as the 30-vs-59.94 fps frame mismatch, and just as invisible: the
    annotation still loads, still exports, and is simply wrong.

    Each label is therefore projected back to source time through the OLD clock and
    forward again through the NEW one. Going via source time (rather than adding a
    delta) is what makes this exact when ``drift_ppm`` changes too, since drift makes
    the correction time-dependent rather than a constant shift.

    Two consequences of that bulk rewrite are handled here rather than left to the
    caller, because nothing downstream can detect either one:

    * **The previous alignment is recorded** in ``signal_source_offset_history``. The
      re-projection is exactly invertible, so the old ``(t0_offset_s, drift_ppm)`` pair
      is the whole undo — but only if it was written down before being overwritten.
    * **Any consensus computed over the moved labels is invalidated.** A stored
      ``signal_consensus_cache`` row and the ``consensus_state`` stamps on labels
      describe clusters built from the OLD geometry: which marks overlapped, and
      therefore who corroborated whom, is a function of times that just changed. Left
      in place, the review panel keeps reporting κ and "confirmed" for an arrangement
      of labels that no longer exists. The cache row is dropped and the stamps cleared
      for every deployment whose labels moved — the same whole-deployment scope
      ``save_consensus`` uses when it restamps, since a cluster is a joint object and a
      surviving stamp on an unmoved label would still name a cluster that has changed.
      Badge counters read those stamps, so they too go quiet until an admin recomputes;
      that is the honest state, not a regression.

    ``signal_consensus_cache`` stays separate from the scar ``consensus_cache`` (which
    ``update_user_weights`` deletes wholesale); only this deployment's row is touched.
    """
    ...

def list_source_offset_history(source_id: int, *, limit: int=100) -> List[dict]:
    """Every accepted re-alignment of one source, newest first.

    This is the undo log for a mis-alignment: re-applying a row's
    ``old_t0_offset_s``/``old_drift_ppm`` through ``update_source_offset`` puts the
    labels back exactly where they were drawn.
    """
    ...

def add_channel(*, source_id: int, name: str, unit: Optional[str]=None, sample_rate_hz: Optional[float]=None, v_min: Optional[float]=None, v_max: Optional[float]=None, pyramid_path: Optional[str]=None, sort_order: int=0) -> Optional[dict]:
    ...

def list_channels(source_id: int) -> List[dict]:
    ...

def get_channel(channel_id: int) -> Optional[dict]:
    """One channel joined to the ids the pyramid route needs for its auth check.

    The route is reached by channel id but must authorise against the *deployment*, so
    resolving both in one statement keeps that hot path to a single query.
    """
    ...

def delete_channels(source_id: int) -> int:
    """Hard-delete a source's channels — used only by a --replace reimport.

    Channels are derived artifacts, not annotations: they can be rebuilt from the CSV at
    any time, so unlike labels there is nothing to preserve by soft-deleting them.
    """
    ...

def update_source_meta(source_id: int, *, meta: Dict[str, Any], duration_s: Optional[float]=None) -> bool:
    """Freeze a sensor source's lattice + provenance onto its row.

    `duration_s` matters more than it looks: the dock computes its whole time axis from
    the union of source spans, so a sensor source left at NULL contributes nothing and
    the timeline silently collapses to a 60-second default.
    """
    ...
STALE_IMPORT_S = 90

def set_source_import_status(source_id: int, *, status: str, progress_pct: Optional[float]=None, message: Optional[str]=None) -> bool:
    """Record import progress. Safe to call from a detached process.

    Status lives in the DB rather than a module global because prod runs 4 Gunicorn
    workers: a poll almost never lands on the process that started the job.
    """
    ...

def clear_source_import_status(source_id: int) -> bool:
    """Reset before starting a fresh import so a previous run's stamps cannot linger."""
    ...

def sweep_stale_imports(stale_after_s: int=STALE_IMPORT_S) -> int:
    """Mark imports whose heartbeat has stopped as failed. Returns how many.

    Keyed on the HEARTBEAT, never on the start time. `_register_signals()` runs at module
    scope, so this executes on every Gunicorn worker respawn; a start-time sweep would
    fail a healthy long import and let a second one start against the same pyramid path.
    """
    ...

def get_import_status(source_id: int) -> Optional[dict]:
    """Status for a poll, with `channels_ready` as the durable ground truth.

    Status columns drive the progress bar; the existence of channel rows is what actually
    proves the import finished. If the two disagree, believe the channels — that is the
    same trick the video download endpoint uses with its on-disk file.
    """
    ...

def ensure_vocabulary(*, name: str, kind: str, version: str='1', seeded_from: Optional[str]=None, terms: Optional[List[Dict[str, Any]]]=None) -> Optional[dict]:
    """Create-or-fetch a vocabulary and upsert its terms.

    Idempotent so it can run on every boot from config. Terms already present are
    updated in place (display/colour/hotkey/band), and terms that disappear from config
    are **retired, not deleted** — a label written against a removed code must keep
    resolving, or last semester's data becomes unreadable.
    """
    ...

def list_vocabularies(kind: Optional[str]=None) -> List[dict]:
    ...

def list_terms(vocab_id: int, *, include_retired: bool=False) -> List[dict]:
    ...

def get_term(vocab_id: int, code: str) -> Optional[dict]:
    ...

class LabelValidationError(ValueError):
    """Raised when a label's geometry cannot be stored as given."""

def validate_geometry(kind: str, t_start_s: float, t_end_s: float, f_lo_hz: Optional[float], f_hi_hz: Optional[float]) -> tuple:
    """Normalise and check one label geometry.

    Swapped drag directions are normalised (dragging right-to-left is a real thing a
    labeler does), but a *degenerate* or *missing* extent is an error, not something to
    paper over.
    """
    ...

def _label_deployment(conn: sqlite3.Connection, label_id: int) -> Optional[int]:
    """The deployment a label belongs to, live or soft-deleted.

    Deliberately no `deleted_at IS NULL` filter: `delete_label` needs this AFTER it has
    stamped the row, and a delete is the mutation most likely to change a consensus —
    it can dissolve a cluster and take a corroboration with it.
    """
    ...

def _mark_consensus_stale(conn: sqlite3.Connection, deployment_id: Optional[int]) -> None:
    """Record that this deployment's cached consensus describes an older set of labels.

    A stored run is a statement about the labels that existed when it was computed:
    which marks overlapped, therefore who corroborated whom, therefore κ. Add a label,
    move one, retype its code or delete it and that statement is about a corpus that no
    longer exists — but the cache keeps serving it and the review panel presents it as
    current. The defect is not a wrong number; it is an *unlabelled* one.

    Four deliberate non-behaviours:

    * **It does not recompute.** A refresh is a whole-deployment clustering sweep;
      running it on every label write is precisely the cost this cache exists to avoid,
      and it would put that sweep inside a labeler's save. The panel already never
      auto-computes (`static/js/signals_review.js` header, rule 4) — what it lacked was
      a way for the cache to say "out of date", not a way to fix itself.
    * **It does not clear `consensus_state`.** `update_source_offset` does, because
      there the stored clusters were built from times that were rewritten underneath
      them. Here the old clustering is still a true record of the old labels, and those
      stamps are what `badge_counts` reads on every stats load — blanking them on one
      edit would silently zero every labeler's corroboration badges until an admin
      happened to refresh.
    * **It does not ask which field changed.** A whitelist of "harmless" edits (notes,
      subject) would have to stay exactly right forever, and its failure direction is
      the silent one: an omitted field leaves a stale cache reading as fresh, i.e. this
      bug again. An over-eager prompt to recompute costs an admin one click.
    * **It does not create a row.** A deployment with no cached run is untouched
      (`rowcount` 0) — nothing stored, nothing to be stale — which is what keeps every
      existing caller byte-identical until somebody has actually computed a consensus.

    `stale_since` is COALESCEd so it keeps the FIRST divergence: the honest reading of a
    cached figure is "true up to here", and overwriting it with each new edit would make
    a κ that has been wrong for a week look like it drifted a second ago.
    """
    ...

def create_label(*, deployment_id: int, kind: str, t_start_s: float, t_end_s: float, code: str, annotator: Optional[str]=None, source_id: Optional[int]=None, f_lo_hz: Optional[float]=None, f_hi_hz: Optional[float]=None, channel: Optional[str]=None, vocab_id: Optional[int]=None, modifier: str='', subject: str='', confidence: Optional[int]=None, notes: str='', label_origin: str='human', origin_detail: Optional[str]=None, sigma: Optional[float]=None, sigma_method: Optional[str]=None, is_gold: bool=False) -> dict:
    """Insert one label. Raises LabelValidationError on bad geometry or unknown code.

    `label_origin` defaults to 'human' because that is what the annotator UI produces;
    anything importing a detector's output must pass 'machine' explicitly. A sigma may
    only be stored together with the `sigma_method` that produced it — see v62.
    """
    ...

def list_labels(deployment_id: int, *, source_id: Optional[int]=None, annotator: Optional[str]=None, kind: Optional[str]=None, t_from_s: Optional[float]=None, t_to_s: Optional[float]=None) -> List[dict]:
    """Live labels for a deployment, optionally windowed and filtered.

    The time filter is an **overlap** test, not containment: a label straddling the
    window edge is still visible in that window, which is what a labeler expects when
    scrolling.
    """
    ...

def get_label(label_id: int) -> Optional[dict]:
    ...

def update_label(label_id: int, *, annotator: Optional[str]=None, geometry: Optional[Dict[str, Any]]=None, **fields: Any) -> Optional[dict]:
    """Update a label's attributes and/or geometry.

    When ``annotator`` is given the update is scoped to that owner, so one labeler can
    never silently overwrite another's work — with 10+ people on the same deployment
    that is a correctness property, not a nicety.
    """
    ...

def delete_label(label_id: int, *, annotator: Optional[str]=None) -> bool:
    """Soft-delete. Nothing in this stream hard-deletes an annotation."""
    ...

def count_labels(*, annotator: Optional[str]=None, deployment_id: Optional[int]=None) -> int:
    """Live label count — feeds the annotator progress strip."""
    ...

def assign_deployment(*, deployment_id: int, annotator_email: str, assigned_by: Optional[str]=None, priority: int=0, due_date: Optional[str]=None, notes: str='') -> Optional[dict]:
    """Assign (or re-assign) a deployment to an annotator. Idempotent per pair."""
    ...

def list_assignments(*, deployment_id: Optional[int]=None, annotator_email: Optional[str]=None) -> List[dict]:
    ...

def set_assignment_status(deployment_id: int, annotator_email: str, status: str) -> bool:
    ...

def reviewed_sources(deployment_id: int) -> Dict[str, set]:
    """Who demonstrably reviewed what, for the consensus denominator.

    A completed assignment covers the whole deployment (recorded as ``None``); otherwise
    an annotator is credited only with the sources they actually put a label on. This is
    the honest floor: partial review *within* a source is not recorded anywhere, so an
    annotator who checked the first minute of an hour-long file still reads as having
    reviewed all of it. Closing that needs an explicit review-span record — see the
    deferred-gaps note in `plans/12-stream-f-signals.md`.
    """
    ...

def save_consensus(deployment_id: int, result: Dict[str, Any], *, params: Optional[Dict[str, Any]]=None) -> None:
    """Persist one consensus run and stamp `consensus_state` onto each label.

    `consensus_state` is deliberately NOT reachable through `update_label`'s
    `_UPDATABLE` allow-list: the PATCH route is an annotator-facing endpoint, and a
    labeler who could set the consensus state of their own label could mark their own
    work confirmed.

    Storing a run clears the staleness marks `_mark_consensus_stale` left, because the
    row IS the run. One window stays open and is not worth closing here: a label written
    *between* the caller reading the labels and this save is cleared along with the rest,
    so the figure reads fresh while being one label behind. Closing it needs the caller
    to hand over the instant it read (nothing in this module knows it), and the next
    label write re-marks the deployment anyway — whereas the alternative of inferring it
    from `n_labels` would break every caller that saves a run computed over a label set
    it did not read from this table.
    """
    ...

def get_consensus(deployment_id: int) -> Optional[dict]:
    """The last stored consensus run for a deployment, details rehydrated.

    Carries the staleness `_mark_consensus_stale` recorded: `stale` (has any label been
    created, edited or deleted since `computed_at`), `stale_since` (when it first went
    behind) and `stale_writes` (how many label writes since). A caller that ignores all
    three gets exactly the previous behaviour — this reports, it does not withhold. A κ
    computed an hour and two labels ago is still the best answer available; it is simply
    not current, and the reader is the only place that can say so out loud.

    `stale_since` is read with `.get`, so a database whose cache table predates the
    columns degrades to "not stale" rather than raising on every page load; the guarded
    ALTER in `init_signals_tables` heals it on the next start.
    """
    ...

def set_label_gold(label_id: int, is_gold: bool) -> bool:
    """Mark (or unmark) one label as a blind calibration item."""
    ...

def list_gold_labels(deployment_id: int, *, source_id: Optional[int]=None) -> List[dict]:
    """Gold items for a deployment."""
    ...

def replenish_assignments(annotator_email: str, *, threshold: int=3, assigned_by: str='auto') -> List[dict]:
    """Top an annotator's signal queue back up to ``threshold`` open deployments.

    Mirrors `database.auto_replenish` for videos, with one deliberate difference in how
    candidates are ranked: **fewest raters first**. A deployment that two people have
    labeled is one rater short of a confirmable consensus, so sending the next labeler
    there converts existing work into agreed data. Sending them to an untouched
    deployment instead produces a third pile of single-voter labels and no consensus at
    all — the failure mode a 10+ labeler cohort falls into by default, because every
    queue that ranks by "newest" or "least done" pushes people apart rather than together.

    Deployments the annotator has already been assigned are excluded, so nobody is ever
    asked to corroborate themselves.
    """
    ...

def badge_counts(email: str) -> Dict[str, int]:
    """Cheap per-user signal counters for badge evaluation.

    Called on every annotator stats load, so everything here must be an indexed count —
    never a consensus sweep. That is affordable only because `save_consensus` stamps
    `consensus_state` back onto each label: "how much of my work did somebody else
    corroborate" is a single indexed query rather than a re-clustering of the deployment.

    Returns zeros (never raises) when the Stream F tables are absent, which is the
    normal state of any database where `signals.enabled` has never been true. Badge
    evaluation runs for every user on every load; it must not depend on this feature
    existing.
    """
    ...

def has_signal_work(email: str) -> bool:
    """Whether this person has any signal assignment or label.

    Drives badge visibility. Deliberately data-driven rather than config-driven: it needs
    no knowledge of `signals.enabled`, and where the feature is off nobody has signal
    work, so the badges hide themselves. Offering a labeler a goal they have no way to
    reach is the same defect as a tutorial step pointing at an element that is not there.
    """
    ...
