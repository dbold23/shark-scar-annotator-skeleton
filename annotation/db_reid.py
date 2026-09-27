"""Stream A (re-ID) — morphometrics persistence and queries.

Per the integration contract (plans/00-SHARED-CONTEXT.md §3.2) this is a per-stream DB
module: it reuses `get_conn()` from annotation/database.py and never edits the database.py
monolith. The `morphometrics` table is created by scripts/migrate_schema_v10.py; the
defensive `init_reid_tables()` here mirrors `init_track_tables` so the module also works
before the formal migration runs (e.g. in tests / fresh checkouts).

Morphometrics are the 10 standard inter-keypoint distances (annotation/models.py
MORPHOMETRIC_PAIRS) derived from the placed 16-point skeleton. Values are PIXELS only;
absolute-cm + pixel->cm scale are deferred to Phase A4 (no field scale reference yet).
"""
from __future__ import annotations
import json
import logging
import math
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from annotation.database import get_conn
from annotation.models import MORPHOMETRIC_PAIRS

def init_reid_tables() -> None:
    """Idempotently ensure the morphometrics table exists (defensive)."""
    ...

def _kp_index(keypoints) -> Dict[str, dict]:
    """Index placed keypoints by name. Accepts dicts or Keypoint-like objects.

    A keypoint is 'placed' (usable for a measurement) when it carries a position and
    visibility >= 1 (1=occluded-but-placed, 2=visible). v=0 means outside-frame/no
    position and is excluded.
    """
    ...

def compute_morphometrics(keypoints) -> List[dict]:
    """Compute the 10 standard morphometric distances (pixels) from placed keypoints.

    Returns a list of {measure, point_a, point_b, value_px, a_visibility, b_visibility}.
    A measure is emitted only when BOTH endpoint keypoints are placed.
    """
    ...

def store_morphometrics(annotation_id: str, video_id: Optional[str], frame_number: Optional[int], annotator: Optional[str], encounter_code: Optional[str], keypoints, *, source: str='annotation') -> int:
    """Recompute + persist morphometrics for one annotation. Idempotent.

    DELETE-then-INSERT so a re-save that REMOVED keypoints clears stale rows. Mirrors the
    3x 'database is locked' retry used by annotation/database.py write paths. Returns the
    number of measures written.
    """
    ...

def get_morphometrics(*, annotation_id: Optional[str]=None, encounter_code: Optional[str]=None) -> List[dict]:
    """Fetch morphometric rows by annotation_id or encounter_code."""
    ...

def backfill_morphometrics(progress_cb=None, limit: Optional[int]=None) -> dict:
    """Compute + persist morphometrics for all existing annotations. Idempotent & resumable.

    progress_cb(done, total, annotation_id) is called after each annotation if provided.
    Returns {processed, with_morphometrics, skipped}.
    """
    ...

def _has_signature_tag_columns(conn) -> bool:
    """True if the v11 signature tag columns exist (cached). Lets us degrade on a pre-v11 DB."""
    ...

def update_track_signature(track_id: int, signature_json: Optional[str], model: Optional[str]=None, dim: Optional[int]=None) -> bool:
    """Persist a track's signature + its model/dim tag. Idempotent; 3x lock-retry.

    Writes the v11 tag columns when present, else falls back to writing signature_json only
    (pre-v11 DB). This is the tagged counterpart to database.update_track_signature (which
    writes signature_json alone); the live propagation path may use either.
    """
    ...

def signature_status() -> dict:
    """Coverage of signatures over eligible verified tracks (acceptance + status route).

    Returns {eligible, with_signature, with_model_tag, coverage, by_model}.
    """
    ...

def backfill_track_signatures(emb_cfg: dict, *, force: bool=False, limit: Optional[int]=None, progress_cb=None, download_missing: bool=False, downloader=None) -> dict:
    """Compute + persist signatures for all eligible verified tracks. Idempotent & resumable.

    Idempotent: a track already tagged with the SAME model is skipped unless `force`. Resumable:
    interrupt and re-run — only the missing/other-model tracks recompute. The extractor is loaded
    ONCE up front; if its deps/weights are unavailable the whole job fails fast with a clean error
    (reid_embed.ExtractorUnavailable) rather than half-filling the table.

    `emb_cfg` is the `reid.embeddings` config section. Returns run counters + final coverage.
    """
    ...

def _has_permanence_column(conn) -> bool:
    ...

def set_track_permanence(track_id: int, value: Optional[str]) -> dict:
    """Set a track's permanence flag. Idempotent; 3x lock-retry.

    `value` is normalized to one of 'permanent'|'transient'|'unknown'. Empty/None or the
    literal 'unknown' is stored as NULL (NULL ⇒ unknown by convention). Returns
    {ok, track_id, permanence} or {ok: False, error, ...}.
    """
    ...

def get_track_permanence(track_id: int) -> Optional[str]:
    """Return a track's permanence ('permanent'|'transient'|'unknown'), or None if no track."""
    ...

def _has_table(conn, name: str) -> bool:
    ...

def init_reid_external_tables() -> None:
    """Idempotently ensure the v13 reid catalogue/sightings/evidence/audit tables exist."""
    ...

def _uf_groups(edges) -> Dict[str, List[str]]:
    """Union-find over (a, b, ...) edges → {root: [members]} (b may be None for a singleton)."""
    ...

def list_reid_individuals(status: Optional[str]=None) -> List[dict]:
    """Group reid_match_audit edges into proposed/accepted individuals (read-only)."""
    ...

def _mint_catalog_row(conn, display_name: str, now: str) -> Optional[int]:
    """Upsert a shark_catalog row BY NAME, minting a stable organism_id (dwc:organismID).

    `database.create_shark` is the canonical minting site; this path cannot call it (it opens its
    own connection and raises on an existing name), so it mints the same way. Without the mint the
    row's organism_id stays NULL until the next process start backfills it — and every Darwin Core
    archive taken in between publishes the individual with organismName but no organismID, which is
    exactly the identity claim the re-ID stream exists to publish. Also backfills a pre-existing
    NULL, so re-deciding an individual heals it rather than leaving it identity-less.
    """
    ...

def decide_reid_individual(group_key: str, status: str, *, catalog_id: Optional[int]=None, display_name: Optional[str]=None, decided_by: Optional[str]=None, relink: bool=False) -> dict:
    """Accept or reject a proposed individual (the human adjudication step).

    'accepted' upserts a shark_catalog row (provided catalog_id / display_name, else derived from a
    nickname or 'unk:<photo_id>') and links each member encounter via encounter_priority — upsert-only
    on the existing v9 tables, never schema-edits. 'rejected' just marks the audit rows. Idempotent.

    An encounter already linked to a DIFFERENT individual is a contradictory identity claim, so the
    accept REFUSES the whole group (writing nothing) unless the caller passes `relink=True`. The old
    code silently dropped the new link — the `AND shark_catalog_id IS NULL` guard held — while still
    stamping the audit rows with the new catalog id and returning status 'accepted', so an admin's
    deliberate correction was discarded under a success message and the audit trail then named a
    different animal than the live link.

    Every accepted member gets an audit row: the UPDATE only reaches 'proposed' edges, and a matcher
    suggestion has none, so previously the singleton path wrote the identity claim with no
    decided_by/decided_at/basis anywhere.
    """
    ...

def init_reid_match_tables() -> None:
    """Idempotently ensure the v14 matcher suggestion/eval tables exist (defensive)."""
    ...

def _embedding_accepted_encounters(conn) -> set:
    """Encounters whose catalog link came from a human accepting the MATCHER'S OWN suggestion.

    These are not independent ground truth: the gallery neighbour whose cosine produced the
    suggestion survives eval's leave-one-encounter-out guard, so such an encounter is near-certain
    to rank 1 for its own label, while a REJECTED suggestion leaves the encounter unlabelled and its
    miss structurally unrecordable. Admitting them makes recall@k a function of how many of the
    matcher's proposals were accepted. (The provenance row this reads is written by
    `decide_reid_individual`; without it an embedding link is indistinguishable from a tag- or
    nickname-derived one.)
    """
    ...

def _individual_label_map(conn, *, exclude_embedding_links: bool=False) -> Dict[str, str]:
    """encounter_code -> individual label. A shark_catalog_id link wins ('cat:<id>'); otherwise a
    union-find evidence group ('grp:<root>') from reid_match_audit (excludes rejected edges).

    `exclude_embedding_links` drops the 'cat:' label for encounters linked by accepting a matcher
    suggestion (eval only — see `_embedding_accepted_encounters`). Such an encounter can still be
    labelled from INDEPENDENT evidence via the 'grp:' fallback below.
    """
    ...

def _signature_items(conn, *, permanence_filter: bool=True, model: Optional[str]=None) -> List[dict]:
    """Signed tracks (+ side + encounter) usable by the matcher. Parses + L2-normalizes vecs."""
    ...

def _resolve_model(items: List[dict], model: Optional[str]) -> Optional[str]:
    ...

def _catalog_links(conn):
    """(encounter->catalog_id linked map, catalog_id->display_name)."""
    ...

def run_matcher(*, model: Optional[str]=None, k: int=5, min_score: float=0.0, side_partition: bool=True, permanence_filter: bool=True, run_id: Optional[str]=None) -> dict:
    """k-NN suggest a catalog individual for each UNIDENTIFIED signed track. Propose-only.

    Gallery = tracks whose encounter is linked to a shark_catalog_id; queries = signed tracks whose
    encounter is NOT linked. Writes top-k candidates to reid_match_suggestions (latest-run cache);
    never writes shark_catalog. Suppresses (encounter, candidate) pairs already dismissed.
    """
    ...

def get_match_suggestions(*, limit: int=300, min_score: Optional[float]=None) -> List[dict]:
    """Latest-run suggestions for the catalog.js panel; 'accepted' derived from the live link."""
    ...

def candidates_for_track(track_id: int, *, model: Optional[str]=None, k: int=5, min_score: float=0.0, side_partition: bool=True, permanence_filter: bool=True) -> dict:
    """Live top-k candidate individuals for one track (no write) — plans/01 §A2 GET candidates."""
    ...

def run_eval(*, model: Optional[str]=None, k_list=(1, 5, 10), side_partition: bool=True, permanence_filter: bool=True, run_id: Optional[str]=None) -> dict:
    """Leakage-safe retrieval eval (recall@k / mAP). Labels = shark_catalog_id ∪ union-find groups.

    Persists a reid_eval_runs row for reproducibility. Read-only w.r.t. shark_catalog.

    Encounters labelled ONLY by accepting one of the matcher's own suggestions are excluded: they
    are the matcher's output, not independent ground truth, and admitting them makes the score rise
    with every acceptance and never fall for a rejection (the rejected encounter stays unlabelled,
    so its miss cannot be counted). plans/01 §A2 calls for a frozen eval set; until there is one,
    this keeps the denominator from being selected by the thing being measured.
    """
    ...

def init_reid_healing_tables() -> None:
    """Idempotently ensure the v15 healing observation/proposal tables exist (defensive)."""
    ...

def _bbox_area_px(bbox_json: Optional[str]) -> Optional[float]:
    """Area of a {x,y,width,height} bbox in px (cv2-free). None on bad/missing JSON."""
    ...

def _encounter_dates(conn, encounters) -> Dict[str, dict]:
    """encounter_code -> {obs_date, obs_year}. videos.date wins (it's ISO when present); else the
    encounter-code grammar (<SITE><YY><MM><DD><NN>); year backfills from videos.year. Reuses the A2
    importer's parser so A2/A3 derive dates identically (videos.date is empty for ~all rows today)."""
    ...

def _body_scale_px(conn, encounter_code: str) -> Optional[float]:
    """Internal body-size scale (px) for relative-area normalization (plans/09 F2): the longest
    persisted total_length (else fork_length) morphometric in that encounter. None if unavailable."""
    ...

def _healing_observations(conn, catalog_id: int, encounters, *, transient_only: bool=False) -> List[dict]:
    """Build per-track wound snapshots for one individual across its catalogued sightings."""
    ...

def _dedupe_per_encounter(group: List[dict]) -> List[dict]:
    """Collapse a scar-key group to one representative per encounter (prefer human colour, then a
    known stage, then larger area) so a chain has one point per sighting."""
    ...

def run_healing_analysis(*, transient_only: bool=False, run_id: Optional[str]=None) -> dict:
    """Snapshot wounds + propose healing trajectories for re-sighted individuals. Propose-only.

    Individuals = shark_catalog_id with >=2 linked encounters (encounter_priority). For each, snapshot
    candidate wounds and chain each (side,zone,type) scar across >=2 DATED sightings into a trend +
    latest-stage proposal. Latest-run cache (DELETE+rewrite), like the matcher. Never writes
    tracks/consensus/shark_catalog. Returns run counters incl. a by-trend breakdown.
    """
    ...

def get_healing_proposals(*, catalog_id: Optional[int]=None, trend: Optional[str]=None, min_confidence: Optional[float]=None, limit: int=300) -> List[dict]:
    """Latest-run healing proposals for review (read-only). Adds the individual display_name."""
    ...

def get_individual_timeline(catalog_id: int) -> dict:
    """Per-individual scar timeline (observations grouped by scar, in date order) + its proposals.
    Drives the catalog.js healing panel. Read-only."""
    ...

def healing_status() -> dict:
    """Coverage/summary for the healing analysis (status route). Read-only; OFF-safe on a fresh DB."""
    ...
