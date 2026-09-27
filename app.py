"""
Shark Scar Annotation Platform — Flask Application
Run: ./venv/bin/python3 app.py
Open: http://localhost:5000
"""
import io
import os
import re
import sys
import json
import time
import uuid
import base64
import logging
import secrets
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from functools import wraps
from logging.handlers import RotatingFileHandler
import cv2
import numpy as np
import yaml
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, Response, redirect
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, BadRequest
from werkzeug.middleware.proxy_fix import ProxyFix

class CloudflareProtoFix:
    """Inject X-Forwarded-Proto from Cloudflare's Cf-Visitor header when missing."""

    def __init__(self, app):
        ...

    def __call__(self, environ, start_response):
        ...

def _load_runtime_overrides() -> dict:
    """The flat {dotted.key: value} map the app persisted for itself.

    Never raises: a malformed sidecar must degrade to "no overrides", exactly as
    an unreadable config.yaml degrades to "all gates OFF".
    """
    ...

def _apply_dotted(target: dict, dotted: str, value) -> None:
    """Set ``target["a"]["b"] = value`` for a dotted key "a.b", creating dicts."""
    ...

def _trusted_proxy_hops() -> int:
    """How many proxies sit in front of this process, i.e. how many trailing
    X-Forwarded-For entries were appended by infrastructure we control.

    Production is Cloudflare -> nginx -> Gunicorn, which is TWO hops:
    Cloudflare sends `X-Forwarded-For: <client>` and nginx.conf's
    `$proxy_add_x_forwarded_for` appends its own peer — the Cloudflare edge.
    Werkzeug's ProxyFix returns `values[-trusted]`, so the old `x_for=1` handed
    back the Cloudflare edge address on EVERY request: `request.remote_addr` was
    never a client address, which silently broke both the flask-limiter keying
    and every `IP=` field in the auth audit log.

    2 is also the strictly safer default when the config section is absent (it
    is, in prod): with fewer XFF entries than trusted hops ProxyFix leaves
    remote_addr untouched, so a client that talks straight to Gunicorn with a
    forged single-entry header cannot spoof its address — which `x_for=1` did
    allow. Override with `app.trusted_proxy_hops` for a single-proxy deployment.
    """
    ...

def _assignment_goal() -> str:
    """Semester annotation target, biasing WHICH encounters get assigned within a
    consensus tier. Config-only so it can be retargeted without a deploy:

        assignment:
          goal: pose        # pose | scar | segmentation | balanced

    Defaults to 'balanced' (today's behaviour). An unknown value degrades to
    balanced rather than raising — see database.goal_rank_sql.
    """
    ...

def _exclude_drop() -> bool:
    """Whether DROP-flagged encounters are withheld from assignment entirely.
    Off by default — see config.yaml.example: assignment.exclude_drop."""
    ...

def _follow_scar_enabled() -> bool:
    """Is FOLLOW A SCAR (bbox/SAM2 track propagation) offered to annotators?

        tracks:
          follow_scar: true       # default FALSE

    OFF by absence. Deliberately a NEW key rather than `tracks.enabled`: that one
    is documented and positioned in config.yaml.example as "gates sam2 tracker
    only", ships false, and honouring it here would disable follow-a-scar for
    everyone on the recommended default bbox tracker — see api_tracks_health's
    docstring, which warns against exactly that reuse.

    Why it defaults off rather than merely being available: propagation is the
    single most expensive thing a student can trigger on this box. Measured,
    `scripts/loadtest/scenario_propagation.py`: **+213 MB on one worker as a
    FLOOR** — that run produced ONE detection — with 254-764 MB the realistic
    envelope for a scar actually tracked across ~92 frames, because each
    detection additionally pins a padded crop. Production is a 1907 MB t3.small
    with NO SWAP and four gunicorn workers; ~1.1 GB is free at rest. Two
    simultaneous propagations is an OOM kill, and the OOM killer does not
    politely choose the propagation.

    Until now the UI was live for every student regardless: the client gates on
    `/api/tracks/health` -> `available`, and for the default bbox tracker that is
    `segmentation.bbox_tracker.is_available()`, which returns `(True, "")`
    unconditionally because it needs nothing but opencv. So "is the tracker
    installed" was standing in for "should this cohort be doing this", which are
    different questions.
    """
    ...

def _replenish_pose_enabled() -> bool:
    """Should the POSE (image-keypoint) task auto-top-up alongside the scar task?

        assignment:
          replenish_pose: true      # default FALSE

    OFF by absence, which is a deliberate behaviour CHANGE. `auto_replenish_pose`
    used to fire on every `GET /api/videos` for every non-admin behind no flag at
    all, immediately after `auto_replenish` — so a student assigned scar work on
    video clips was silently enrolled in the pose task too, and up to 8 single-
    frame image cards appeared in a rail they believed was their clip queue. The
    right panel then switches task on click, so the labeler's task changes
    depending on which card they happen to pick.

    That is precisely the shape this repo has already had to fix twice (the
    gamification panel, the per-frame scar form): a capability reaching students
    because nobody chose it. Pose work is still fully available — an admin
    assigns it deliberately via POST /api/admin/pose-frames/assign, which is the
    honest way to hand somebody a different task.

    Existing image assignments are NOT touched by this: it governs top-up only.

    Scope is deliberately ONE call site. `POST /api/videos/<id>/complete` also
    tops up pose, but it first checks `video["media_type"] == "image"` — i.e. it
    only ever hands you another pose frame when the thing you just finished WAS a
    pose frame. That is task-aware and correct, so it stays ungated: somebody
    deliberately given pose work keeps flowing, while nobody gets pose work
    injected into a scar rail they never asked for.
    """
    ...

def _rate_limit_key() -> str:
    """Bucket rate limits by *who is calling*, not by the address the request
    appears to come from.

    `get_remote_address` reads `request.remote_addr`, which behind Cloudflare is
    an edge address shared by an arbitrary, shifting subset of the cohort: one
    student's brightness-slider burst then spends a classmate's budget while a
    single heavy client scatters across several edge IPs and is under-throttled.
    Neither direction is what the limits are for. The abuse unit here is a
    logged-in annotator, so key on the JWT identity when there is one and fall
    back to the address only for the unauthenticated routes (`/auth/login`,
    `/auth/callback`), where there is no identity yet.

    Verification is cheap (an HS256 HMAC) and must not raise — a bad or absent
    token degrades to the address key rather than 500ing the request.
    """
    ...

def _rate_limit(limit_str):
    """Apply rate limit if flask-limiter is available, otherwise no-op."""
    ...

@app.before_request
def csrf_check():
    ...

@app.after_request
def set_security_headers(response):
    ...

def _refresh_session_if_needed(response):
    """Issue a fresh JWT cookie if the current one is past its halfway point (12h)."""
    ...
import atexit
from annotation import database as db
from annotation import db_effort
from annotation import effort as effort_lib
from annotation import frame_thumbs
from annotation import export as exp
from annotation import scar_pin
from annotation.models import SHARK_KEYPOINT_SEQUENCE, ScarType, TrackSource
from annotation.db_objects import init_object_tables as _init_object_tables
from annotation.db_frame_hints import init_frame_hints_table as _init_frame_hints
from annotation.db_side_hints import init_side_hints_table as _init_side_hints
_auth = None

def _get_auth():
    ...

def _is_browser_navigation() -> bool:
    """Whether this request is a person typing a URL, not a fetch() call.

    `/admin/dashboard`, `/exports/<file>` and `/admin/scar-pin-paint` are
    navigation targets behind an auth decorator whose 401 is a JSON body, so a
    bookmarked dashboard opened the next morning rendered `{"error":
    "Authentication required"}` as the whole page. The XHR recovery path cannot
    fire, because the document IS the 401.

    Deliberately narrow: anything under /api/ or /auth/ keeps answering JSON
    whatever its Accept header says, so no client's error handling changes.

    The Accept test is a literal "text/html", NOT
    `request.accept_mimetypes.accept_html` — that property is TRUE for the bare
    `*/*` that a `<video src>`, an XHR and every test client send, so it would
    turn an unauthenticated media fetch into a 302 at a login page. A navigating
    browser always names text/html explicitly.
    """
    ...

def _login_redirect():
    ...

def require_login(f):
    """Flask decorator: require valid JWT in Authorization header or session cookie."""
    ...

def require_admin(f):
    """Flask decorator: require admin privileges."""
    ...

def safe_video_path(user_path: str) -> Optional[Path]:
    """Validate that a path is within allowed directories. Returns resolved Path or None."""
    ...

def _reject_unknown_annotator(email: str):
    """None when the address is somebody who can actually log in; a 400 otherwise.

    `email and "@" in email` was the whole validation, so a typo created a real
    assignment: `videos.status` went to 'assigned', the encounter's queued badge
    went up, and nobody ever saw the work. Checked against `users` first and the
    login whitelist second, because a whitelisted person who has never signed in
    has no `users` row yet and is a legitimate assignee.
    """
    ...

def _int_field(data, key, default, *, lo=None, hi=None):
    """Read one integer out of a JSON body. 400, not 500.

    Five admin routes called `int(data.get(...))` straight, so a typo in a number
    field answered "Internal server error" — a request the admin could have fixed,
    reported as a fault they cannot. `POST /api/admin/assignments/recycle` already
    got this right; this is that shape, said once.

    `lo`/`hi` CLAMP rather than reject: the callers all want a bounded batch, and
    the clamp is what makes the previewed number and the performed number agree.
    """
    ...

def _sanitize_drive_query(value: str) -> str:
    """Sanitize a value for use in Google Drive API query strings.
    Strips to safe characters and escapes single quotes to prevent injection."""
    ...

def _get_mimetype(file_name: str, media_type: str='video') -> str:
    """Return the correct MIME type based on filename extension and media_type."""
    ...

def safe_filename(name: str) -> str:
    """Sanitize a filename: remove path separators and dangerous characters."""
    ...

@app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all: log the real error, return a safe message."""
    ...

@app.after_request
def log_request(response):
    ...
import threading
_segmenter = None
import queue as _queue_mod

def _persist_config_key(dotted_key: str, value) -> bool:
    """Apply ONE value to the live config and persist it to the sidecar.

    The single writer. Nothing in this module may call `yaml.dump(cfg)` again:
    that rewrites the operator's documented config.yaml from a parsed dict and
    loses every comment and the key order with it.

    Returns whether it reached disk. The in-memory apply always happens, so a
    caller can report "applied for this process, not persisted" honestly instead
    of pretending either half of that.
    """
    ...

class SyncTaskError(RuntimeError):
    """A sync task did not fully complete, so its outbox row must NOT be deleted.

    `_process_sync_task` used to swallow every exception from both halves and
    return normally, which made `_drain_one_outbox`'s success branch — and with
    it `db.finish_outbox`'s DELETE — unconditional. The whole durability
    substrate (attempts, _OUTBOX_MAX_ATTEMPTS, fail_outbox's requeue/park, the
    reclaim window) was therefore unreachable for the only failure mode it
    exists to handle, and the frame JPEG carried solely in the outbox payload
    was destroyed along with the row.
    """

def _is_blank_jpeg_b64(b64: str) -> bool:
    """True when a frame capture decodes to a picture with no light in it at all.

    Chrome cannot decode HEVC, and every 4K clip in this corpus is H.265. The
    hidden <video> element then reports a width and a height but paints nothing,
    and the client's captureCurrentFrame() faithfully encoded 1920x1080 of zeros
    — 12,998 bytes, byte-identical on every clip. Six of those reached Drive as
    the "backup" of an annotated frame (measured 2026-09-02: max pixel value 0 on
    all three channels). Undecodable counts as blank: garbage is no better.
    """
    ...

def _backup_frame_b64(video_id, frame_number, client_b64):
    """The JPEG the Drive backup carries for one annotation.

    The client's capture is used when it shows something. When it is missing or
    blank, the server answers from its OWN decode — the frame the labeler was
    actually served — through the same cache /api/frames reads, so on queue work
    this is a file read and elsewhere one decode, in the background worker where
    a decode is affordable. None when neither exists: no picture beats a black
    one filed as if it were evidence, and the JSON still goes up.
    """
    ...

def _resolve_encounter_folder(drive_svc, export_folder: str, enc_folder_name: str) -> str:
    """Find (or create) the per-encounter Drive backup folder, deterministically.

    Drive permits identically named siblings, so the old check-then-create could
    produce two folders for one encounter — either from two workers racing, or,
    more easily, from `_drive_api_retry` re-issuing a `files().create` that had
    already succeeded server-side but timed out client-side. Once split, the
    downstream "does this file already exist" probes (both scoped to the folder
    id) stop seeing each other's uploads and the encounter's archive silently
    forks in two.

    Two properties fix that: after creating, re-list and pick the SAME folder
    every caller would pick (lowest id wins — an arbitrary but stable total
    order), so all workers converge on one canonical folder even if a duplicate
    was created; and list more than one result so a pre-existing duplicate can't
    make the choice depend on Drive's unordered paging.
    """
    ...

def _process_sync_task(task):
    """Execute Sheets and Drive sync for a single annotation (runs in background
    thread). Raises SyncTaskError if either half did not complete, so the outbox
    row is requeued instead of deleted.

    Both halves are always attempted: a Sheets outage must not skip the Drive
    backup, which is the half with no manual healing path (the Sheets rows can
    be rebuilt from the DB with POST /api/export/sheets; the frame JPEG lives
    only in this task's payload).
    """
    ...

def _drain_one_outbox():
    """Claim and process a single outbox task: run its Sheets+Drive upload and
    delete it on success, or requeue/park it on failure. Returns True if a task
    was handled, False if the queue was empty. Extracted from the drain loop so
    the success->finish / failure->fail wiring is unit-testable."""
    ...

def _background_sync_worker():
    """Drain the durable sync outbox. Polls the DB, so tasks survive a worker
    recycle/redeploy (they live in the `outbox` table, not memory), and the
    atomic claim makes it safe for every worker to run its own drain loop."""
    ...
_propagator = None

def _get_propagator_config():
    """Build a PropagatorConfig from the YAML config (lazy import)."""
    ...

def _get_scoring_config():
    """Build a ScoringConfig from the YAML config."""
    ...

def _get_color_config():
    """Build a ColorConfig from the YAML config."""
    ...

def _get_pose_inference_config():
    """Build a PoseInferenceConfig from the YAML config."""
    ...

def _get_pose_zone_config():
    """Build a ZoneConfig from the YAML config (used by pose_zones geometry)."""
    ...

def _get_pose_inferencer():
    """Lazy-load the pose inferencer. Returns None if pose is disabled / unavailable."""
    ...

def _get_detector_config():
    """Build a DetectorConfig from the YAML config (Phase 5a)."""
    ...

def _get_detector():
    """Lazy-load the candidate-proposer detector. None if disabled / model missing."""
    ...

def _tracker_type() -> str:
    """Which tracker is active: 'bbox' (template matching, default) or 'sam2'."""
    ...

def _get_propagator():
    """Lazy-load the active propagator (bbox tracker or SAM2).

    BboxPropagator uses only opencv-python and is always available. SAM2 requires
    the Meta sam2 package + weights; caller should gate on is_available() first.
    Returns None only if the selected tracker can't be loaded.
    """
    ...

def _process_propagation_task(task):
    """Run a single propagation: SAM2 video → score → persist detections + update track."""
    ...
RETRY_DELAY_SEC = 60.0

def _maybe_schedule_retry(task):
    """Re-enqueue a failed task once, after RETRY_DELAY_SEC seconds.

    Marks the task with `_retried=True` so the second failure is final.
    Skips retries if the queue is full (don't block the worker).
    """
    ...

def _propagation_stale_seconds() -> int:
    """How long a track may sit at propagation_status='pending' before it is
    presumed abandoned. Deliberately generous (30 min default) — far longer than
    any real propagation, including one queued behind the 300 s SAM2 lock, so a
    live job is never reclaimed out from under itself. Even if one were, the
    worker's own completion write (`update_track_propagation_result`) sets
    'done' and heals it; the reverse — never reclaiming — has no cure at all.
    Override with `tracks.propagation_stale_seconds`.
    """
    ...

def _reclaim_stale_propagations(annotator_email: str) -> int:
    """Fail this annotator's abandoned 'pending' tracks so the cap unblocks.

    A track is created 'pending' and is only ever moved off it by the in-memory
    queue worker running to completion or failure. Every way that thread can die
    without running its handler — --max-requests recycle, redeploy, OOM — leaves
    the row 'pending' forever, and `count_active_propagations` keeps counting it.
    Returns the number of rows reclaimed.
    """
    ...

def _background_propagation_worker():
    """Drain the propagation queue, processing one track at a time."""
    ...

def get_segmenter():
    ...

def _register_scar_classifier():
    ...

def _register_reid():
    ...

def _register_gamification():
    ...

def _local_media_file(video):
    """The on-disk file for a video row, or None when it is not in the local cache.

    Resolution mirrors the track-preview route: the recorded path if it survives
    the ``safe_video_path`` whitelist, else the conventional tmp_videos filename.
    Deliberately does NOT reach for Drive — callers that only want a thumbnail
    must degrade rather than trigger a multi-hundred-MB download.
    """
    ...

def _warm_queue_media(items):
    """Decode what this lease is about to need, in the background, head first.

    Called with the items the queue just handed out, so the work happens while the
    labeler is still on the previous card. Everything here is cache-first and
    lock-guarded, so a second worker (or a second poll a minute later) costs
    nothing.

    Order matters: the frame comes before the clip proxy for every item, because a
    frame is ~0.3s and is what the canvas needs first, while a clip proxy is 7-15s
    and is only needed once they start moving through it. And items are warmed in
    queue order, so the head card is ready first.
    """
    ...

def _register_mlops():
    ...

def _register_scar_hints():
    ...

def _register_side_hints():
    ...

def _register_training():
    ...

def _register_roi():
    ...

def _register_missions():
    """Labeler-suggested missions. OFF by absence, and on its OWN switch rather than
    riding on `cooperative.enabled`: proposing a mission is a write route open to
    every signed-in student, so turning the shared goal on must not silently open
    it as well."""
    ...

def _register_objects():
    ...

def _register_signals():
    ...

def _register_pose3d():
    ...

def _register_ingest():
    ...

def _get_user_credentials(email: str):
    """Get cached Google credentials for a logged-in user."""
    ...

def _get_drive_service(email: str):
    """Build a read-only Drive API service using the user's OAuth credentials."""
    ...

def _get_sheets_service(email: str):
    """Build a Sheets API service using the user's OAuth credentials."""
    ...

def _get_sync_credentials():
    """One service identity for ALL background Sheets/Drive sync writes.

    Students' personal tokens are never used for writes — they only need
    permission to log in and read videos. Resolution order:
      1. google.service_account JSON file (if configured)
      2. google.sync_account_email's cached token
      3. the first admin's cached token (fallback, zero-config)
    """
    ...

def _get_sync_sheets_service():
    ...

def _get_sync_drive_service():
    ...

def _drive_api_retry(fn, max_retries=3):
    """Execute a Google Drive API call with exponential backoff on transient errors."""
    ...
CLIP_PROXY_WIDTHS = (640, 1280)

def _strip_jpeg_b64(frame, width: int) -> Optional[str]:
    """One strip frame at one width — the single definition of the resize + encode.

    Quality steps up with size on purpose. At 640 the frame is a thumbnail whose
    job is to find a moment (q70 keeps a whole clip near 2 MB). At 1280 it is what
    the labeler is actually looking at while the animal moves, and q70 blocking
    upscaled onto a laptop canvas reads as skin texture — which on a scar task is
    the one thing the picture must not invent.
    """
    ...

def _whole_clip_plan(media_path, width: int=640):
    """Sizing for a whole-clip scrub proxy: bounded frame count, coarse stride.

    The clips here run 120-1300 frames. A proxy exists to FIND the moment, not to
    annotate it — the frame the labeler settles on is fetched full-resolution — so
    it is capped at ~80 samples however long the clip is. Rendered at the width
    asked for: the same plan at 640 and at 1280 has the same frame numbers, which
    is what lets the client swap one for the other frame by frame.
    """
    ...

def _whole_clip_plan_for(n_total: int, width: int=640):
    """The plan for a clip of `n_total` frames. Pure, so a cached proxy can be
    recognised WITHOUT the clip: the payload records `total_frames`, and the plan
    for that count reproduces the name it was stored under."""
    ...

def _cached_frame_payload(video_id: str, position_arg) -> Optional[dict]:
    """A full-resolution frame already in data/frame_cache, or None.

    The media pipeline decodes a queue card's frame up front precisely so the clip
    file is NOT needed to serve it (prepare_queue_media, media_warm) — but the frame
    routes checked for the clip BEFORE consulting that cache, so a warmed frame on a
    clip that was evicted or never downloaded answered 409 and forced the Drive
    download the cache exists to avoid. Measured 2026-09-13 on production: 437 of
    the 450 queued clips had their frame cached and no clip on the box.
    Integer frame indices only; a fractional position is not a stable cache key.
    """
    ...

def _cached_context_window(video_id: str, center: int, span: int, stride: int, width: int) -> Optional[dict]:
    """A windowed strip already on disk under its deterministic name, or None."""
    ...

def _cached_whole_clip_proxy(video_id: str, width: int) -> Optional[dict]:
    """The whole-clip scrub proxy already on disk at `width`, or None.

    Its name comes from the clip's frame count, which normally needs the clip to
    probe. Without the clip the count is inside every candidate (`total_frames`),
    so a candidate is accepted only when the plan for ITS OWN count reproduces the
    name it was stored under — a windowed strip that happens to share the width
    cannot be mistaken for the proxy.
    """
    ...

def decode_context_payload(media_path, video_id: str, *, center: int, span: int, stride: int, width: int, whole: bool=False, extra_widths=()):
    """Frames around a point (or across a whole clip), cached on disk.

    Shared by the route and the background warmer so a warmed strip and a
    requested one are byte-identical and land in the same file — if these two ever
    disagreed about sizing, warming would silently populate a cache nobody reads.

    Decodes in ONE sequential pass rather than seeking per frame: seeking a 4K HEVC
    stream N times costs multiples of reading N frames in a row. `extra_widths`
    are rendered from that SAME pass and cached beside the requested one (the
    warmers ask for every CLIP_PROXY_WIDTHS tier this way); only the requested
    width is returned. A tier already on disk is not re-encoded.

    Returns (payload, None) or (None, reason).
    """
    ...

def _media_cache(kind: str, key: str, name: str) -> Path:
    """One place that decides where decoded media lives, so the request path and
    the background warmer cannot disagree about it."""
    ...

def decode_frame_payload(media_path, video_id: str, frame_number: int) -> Optional[dict]:
    """One full-resolution frame, cached on disk.

    Cached because the queue hands the SAME frame to several labelers — a
    walkthrough frame goes to everybody — and because it lets the warmer put the
    frame on disk before anyone opens the card. Decoding 4K on every open is the
    difference between an instant canvas and a visible wait.
    """
    ...

def frame_to_jpeg_b64(frame: np.ndarray) -> str:
    ...

def extract_frame(video_path: str, position: float) -> Optional[np.ndarray]:
    """Extract frame at normalized position [0,1] or absolute frame number if > 1."""
    ...

@app.route('/')
def index():
    ...

def _effort_record_enabled() -> bool:
    """Is the client asked to time the labeler? OFF unless chosen.

    Recording how long somebody takes is a capability that reaches students, so
    it defaults off by absence — production runs a minimal config.yaml with no
    `metrics:` section at all. The READING side (/api/admin/effort) is not gated:
    it only reads timestamps the app has written since March, and it is
    admin-only.
    """
    ...

@app.route('/api/config/features', methods=['GET'])
def api_features():
    """Return enabled features for frontend."""
    ...

@app.route('/health', methods=['GET'])
def health_check():
    """Health check for load balancers and monitoring."""
    ...

def _registered_redirect_uris():
    """The redirect URIs this OAuth client will accept, read from the client secret.

    Returns [] when the file is absent or shaped unexpectedly, so a missing list
    never blocks a login that would otherwise have worked.
    """
    ...

@app.route('/auth/login', methods=['GET'])
@_rate_limit('10 per minute')
def auth_login():
    """Start Google OAuth flow."""
    ...

@app.route('/auth/callback')
@_rate_limit('10 per minute')
def auth_callback():
    """Handle Google OAuth callback."""
    ...

@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    ...

@app.route('/auth/me', methods=['GET'])
@require_login
def auth_me():
    """Return current user info, including tutorial status."""
    ...

@app.route('/api/tutorial/complete', methods=['POST'])
@require_login
def api_tutorial_complete():
    """Mark a specific tutorial as seen for this user."""
    ...

@app.route('/api/videos', methods=['GET'])
@require_login
def api_list_videos():
    ...

@app.route('/api/videos', methods=['POST'])
@require_admin
def api_add_video():
    ...

@app.route('/api/videos/import-csv', methods=['POST'])
@require_admin
def api_import_csv():
    ...

@app.route('/api/videos/<vid_id>/assign', methods=['POST'])
@require_admin
def api_assign_video(vid_id):
    ...

def _caller_assignment(vid_id: str, email: str):
    """The caller's own assignment row for this video, or None."""
    ...

def _may_work_on(vid_id: str, email: str) -> bool:
    """Assigned to the clip, OR holding / having held a fed-queue item on it.

    The fed queue leases clips without writing an `assignments` row, so the
    assignment-only gate 403'd FINISH VIDEO on every queue clip (no completion, no
    quota credit, red error) and refused the labeler their own saved frames on a
    re-served clip. A queue outage must never widen access: any error => False.
    """
    ...

@app.route('/api/videos/<vid_id>/status', methods=['PATCH'])
@require_login
def api_update_status(vid_id):
    ...

@app.route('/api/videos/<vid_id>/complete', methods=['POST'])
@require_login
def api_complete_video(vid_id):
    """Mark annotator's work on a video as complete."""
    ...

@app.route('/api/drive/browse', methods=['GET'])
@require_login
def api_drive_browse():
    ...

@app.route('/api/admin/drive/unlinked', methods=['GET'])
@require_admin
def api_drive_unlinked():
    """Catalog clips with no drive_id. Database only, so it stays cheap."""
    ...

@app.route('/api/admin/drive/candidates/<video_id>', methods=['GET'])
@require_admin
def api_drive_candidates(video_id):
    """Drive files that might BE this catalog row.

    One search per call, on demand when the admin opens a row, rather than a sweep
    over every unlinked row up front: a bulk scan is a long external round trip and
    has no business inside a request.
    """
    ...

@app.route('/api/admin/drive/link/<video_id>', methods=['POST'])
@require_admin
def api_drive_link(video_id):
    """Attach a chosen Drive file to a catalog row."""
    ...

@app.route('/api/admin/drive/link-all/<video_id>', methods=['POST'])
@require_admin
def api_drive_link_all(video_id):
    """Attach EVERY clip of this encounter, creating rows for the extra ones.

    The encounter code is LOCYYMMDDnn: site, date, and a per-sighting sequence. So
    AN12092201_1/_2/_3 are three clips of ONE shark in ONE sighting, not three
    candidates for the same clip. Making the admin pick one therefore discards the
    other two, which is the opposite of what a corpus short of footage wants.

    The first clip fills this row; the rest become new rows sharing its encounter
    code, site and date. Existing drive_ids are never touched, and a clip already
    present in the catalog is skipped, so this is safe to re-run.
    """
    ...

@app.route('/api/drive/download', methods=['POST'])
@require_admin
def api_drive_download():
    ...

@app.route('/tmp_videos/<path:filename>')
@require_login
def serve_video(filename):
    """Serve video files from tmp_videos directory."""
    ...

def _expand_clips(original_video, extra_matches):
    """Create DB records for additional video clips found on Drive (skip images)."""
    ...

@app.route('/api/videos/<vid_id>/stream')
@require_login
def api_stream_video(vid_id):
    """Serve a video or image by database ID. Downloads from Drive if not cached locally."""
    ...

def _resolve_drive_id(video, user_email=''):
    """Resolve drive_id for a video, searching Drive if necessary. Returns (drive_id, file_name) or (None, None)."""
    ...

def _evict_tmp_videos_if_needed(keep_name=None):
    """LRU-evict cached videos in tmp_videos/ to stay under the configured size
    cap and disk-free floor, so a full class caching videos can't fill the disk.
    Oldest-served-first (serve routes bump mtime). Never touches pose_frames/ or
    the file we're about to use; clears videos.video_path for evicted files so
    the next request re-downloads."""
    ...

class DownloadDiskFullError(RuntimeError):
    """The volume ran below its floor while a download was writing to it."""

def _download_floor_bytes() -> float:
    """Hard floor the download loop refuses to write past.

    Deliberately BELOW `video.cache_min_free_gb` (the eviction target, 5 GB by
    default): eviction runs once before the first byte and aims at that target,
    so an abort floor equal to it would kill every download large enough to eat
    into the margin it just cleared. This one is the "stop before you take the
    database down with you" line — `database/catalog.db`, its WAL, and the
    Drive-backup scratch copy all live on the same volume as `tmp_videos/`.
    Override with `video.download_min_free_gb`.
    """
    ...
_FREE_SPACE_CHECK_CHUNKS = 16

def _sweep_orphan_downloads(tmp_dir: Path, file_name: str) -> None:
    """Remove this video's abandoned per-attempt scratch files.

    Bounded and best-effort: only `<file_name>.*.download` siblings older than
    twice the stale window, i.e. only ones whose owning thread is certainly
    gone. Keeps the per-attempt naming from leaking disk on a box that recycles
    workers mid-download.
    """
    ...

def _download_stale_seconds() -> int:
    """How long a `download:<id>` job may sit at status='downloading' without a
    progress tick before it is presumed abandoned.

    `_bg_download` writes a progress row on every 4 MB chunk, so `updated_at` is
    a live heartbeat; only a dead thread stops it. Dead threads are routine, not
    exceptional: the download runs in a daemon thread inside a Gunicorn worker
    that self-terminates every ~1000 requests (--max-requests), on redeploy, and
    on OOM — none of which run the except block that would have marked the job
    'error'. Without an expiry the row stays 'downloading' forever and the guard
    in api_prepare_video makes that video unopenable by ANY student, permanently.
    """
    ...

def _download_job_is_stale(info) -> bool:
    """True if a 'downloading' job's heartbeat is older than the stale window."""
    ...

def _claim_download_job(job_id: str) -> bool:
    """Atomically claim the download slot for one video across all workers.

    api_prepare_video used to read the job row, decide, and only then write it —
    a check-then-act with `_resolve_drive_id`'s Drive round trips sitting inside
    the window. Two calls landing in that window both spawned `_bg_download`,
    both opened the same `<name>.download` path "wb" on the same inode, and the
    loser's error handler unlinked the shared file out from under the winner's
    rename, discarding both multi-GB transfers.

    The claim succeeds when there is no live download for this video (no row, or
    a row that finished, errored, or went stale per _download_stale_seconds).
    Only the winner starts a thread. SQLite serializes the writes, so exactly one
    caller can win — the UPDATE's own WHERE clause is the lock.
    """
    ...

def _bg_download(vid_id, drive_id, file_name, user_email):
    """Background thread: download file from Google Drive with progress tracking."""
    ...

def _frame_hints_precompute_cfg():
    ...

def _bg_pose_hints(vid_id, local_path, media_type, params):
    """Background thread: walk one asset and cache its per-frame flank hints."""
    ...

def _maybe_start_pose_hints(vid_id, local_path, media_type=None):
    """Kick off a hint walk if one is warranted. Returns True if a thread started.

    Never blocks the caller and never fails a request: a missing hint costs a
    pre-filled field, and the annotator is ground truth either way.

    Concurrency is capped at one walk per process. The walk is CPU-bound inference
    on the same box that serves requests, and gunicorn runs gthread — letting these
    stack would trade an annotator's page load for a hint nobody is waiting on.
    """
    ...

def _probe_video_fps(path) -> Optional[float]:
    """Real fps straight from the container, or None.

    The browser cannot be asked this: HTMLVideoElement exposes no fps, and the
    non-standard `video.videoTracks` API the client used to try is implemented by
    no current browser — so the client silently assumed 30 while the source footage
    runs at 59.94. Every frame_number derived from that guess is roughly half its
    true value. The server has cv2 and the file, so it answers authoritatively.
    """
    ...

@app.route('/api/videos/<vid_id>/prepare', methods=['POST'])
@require_login
def api_prepare_video(vid_id):
    """Start background download if not cached. Returns download status."""
    ...

@app.route('/api/videos/<vid_id>/download-status')
@require_login
def api_download_status(vid_id):
    """Poll download progress for a video."""
    ...

@app.route('/api/frames', methods=['GET'])
@require_login
def api_get_frame():
    """Extract one frame server-side and return it as base64 JPEG.

    Accepts EITHER ``video_path`` (legacy) or ``video_id``. Prefer video_id: the
    stored ``videos.video_path`` is frequently stale — rows in this catalog still
    point at a directory the repo has since moved out of — and a client that has
    to guess the on-disk layout gets it wrong in a way that looks like a broken
    canvas rather than a bad path. Resolution goes through the same helper the
    queue thumbnail uses, which falls back to tmp_videos/<video_name>.
    """
    ...

@app.route('/api/frames/context', methods=['GET'])
@_rate_limit('30 per minute')
@require_login
def api_frame_context():
    """The frames AROUND one frame, as a short flipbook.

    A scar is a texture judgement, and a still lies: glare, ripple and a fold of
    skin all read as a scar until you see the animal move through the moment. The
    labeler needs that motion — but the <video> element cannot give it here. The
    2022 4K clips in this corpus are HEVC, which Chrome does not decode, which is
    why a canvas fed by captureCurrentFrame() stayed blank on exactly the clips
    that matter. ffmpeg decodes them fine, so the motion comes from the server.

    Deliberately downscaled: this is for judging MOVEMENT, not for annotating. The
    annotation itself always happens on the full-resolution pinned frame, and the
    client never lets a context frame become the thing being labelled — a scar
    boxed on frame 305 and filed as frame 300 is a silent, unrecoverable error.

    Decodes in ONE sequential pass rather than seeking per frame: seeking a 4K HEVC
    stream N times costs multiples of reading N frames in a row.
    """
    ...

@app.route('/api/frames/segment', methods=['POST'])
@_rate_limit('5 per minute')
@require_login
def api_segment():
    """Run SAM2 segmentation on a point in the frame."""
    ...

@app.route('/api/annotations', methods=['POST'])
@require_login
def api_save_annotation():
    ...

@app.route('/api/annotations/<ann_id>', methods=['GET'])
@require_login
def api_load_annotation(ann_id):
    ...

@app.route('/api/annotations/video/<vid_id>', methods=['GET'])
@require_login
def api_video_annotations(vid_id):
    ...

@app.route('/api/scars/pin/health', methods=['GET'])
def api_scar_pin_health():
    """Public capability probe — the client gates the 3D zone picker on this.

    Always registered, like /api/tracks/health: the probe has to be answerable
    for the client to learn the feature is OFF. `enabled` reflects the config
    alone, so "switched on but the template asset is missing" is distinguishable
    from "nobody turned it on" — the other fields go null when there is nothing
    to serve, so the client never fetches a URL that will 404.
    """
    ...

@app.route('/api/admin/scars/pin/template/paint', methods=['POST'])
@require_admin
def api_scar_pin_paint():
    """Write hand-painted zones back into the template asset.

    The (station, girth-angle, fin) rule that painted the shipped asset is a
    guess fitted to the 2D SVG; this route lets the lab lead say where the zones
    actually are, once, by hand. It rewrites ONE file and only its zone columns
    — geometry is never touched, because pins already stored against face N must
    keep naming the same triangle.

    TWO body shapes, one route. `{"zone_map": {...}}` writes the 2D body map,
    where a boundary can be straight; `{"face_zone": [...]}` is the legacy
    per-face array. One route because it is one decision, one revision counter
    and one lock — a second endpoint would be a second writer racing the first
    for the same file, and the 409 that makes concurrent painting safe only
    works if every writer counts the same revisions.

    404 rather than 403 when painting is off: the capability does not exist on
    this deployment, and answering 403 would tell a non-admin the route is there
    and merely out of reach. Admin-ness is a separate question, decided by the
    decorator above, and answers 401/403 as every other admin route does.

    409 on a stale `base_revision` — two admins painting the same asset is rare,
    and a silent last-write-wins loses a whole session of strokes with no error
    anywhere.
    """
    ...

@app.route('/api/tracks/health', methods=['GET'])
def api_tracks_health():
    """Public health check — frontend gates the auto-propagate UI on this.

    ``simplify_scar_form`` is reported separately and defaults to FALSE (plan-11
    audit). The client used to hide the per-frame scar form whenever the tracker
    merely *existed* — and the bbox tracker's is_available() returns (True, "")
    unconditionally because it needs nothing but opencv, so that was always true.
    Measured cost: 61 scars against 1,815 keypoints banked, and scars_visible left
    blank on 389 of 440 saves, so the absence signal never got captured. Hiding the
    primary data-capture surface is now an explicit opt-in, never a side effect of
    a health probe.

    NOTE on ``tracks.enabled``: the audit flagged it as a flag with zero readers and
    proposed honouring it here. Do NOT — it is documented (CLAUDE.md) and positioned
    in config.yaml.example as "gates sam2 tracker only", sitting under the SAM2
    block and shipping false. Gating this endpoint on it would disable follow-a-scar
    for everyone on the recommended default bbox tracker. Its zero-reader status is
    a naming problem, not the scar-form bug.
    """
    ...

def _track_owner_or_admin_required(track: dict):
    """IDOR check for MUTATING a track: returns None if allowed, else (resp, status).

    Correct for anything that changes the SHARED track row — /reject, /merge,
    /delete, PATCH, recompute — so only the seeder or an admin may do them. It is
    NOT correct for recording an opinion about it; see _track_verifier_allowed.
    """
    ...

def _target_raters() -> int:
    """How many independent verifications a track needs. 1 == today, exactly."""
    ...

def _multi_rater_mode() -> bool:
    """One switch: `tracks.consensus.target_raters`. Above 1 is multi-rater.

    There was briefly a second, `tracks.multi_rater_verification`, from a branch
    that merged alongside this one. It set the SERVING rule without setting the
    quota, so the first vote drove the track to 'verified' and the second opinion
    it existed to enable could never happen — the flag was on and the feature was
    not. Two knobs for one decision cannot be kept in step; the quota subsumes the
    boolean (>1 is on, 1 is off), so the boolean is gone.
    """
    ...

def _track_verifier_allowed(track: dict):
    """Who may VERIFY a track — deliberately wider than who may mutate it.

    /verify writes a row keyed by the caller (track_verifications has
    UNIQUE(track_id, annotator)), so a second rater structurally cannot clobber
    the first. Restricting it to the seeder is what made multi-rater agreement
    unreachable: the table exists, and nothing could ever put two rows in it.

    In single-rater mode this falls back to the owner check, so those deployments
    behave exactly as before. In multi-rater mode it widens to the video's
    ASSIGNEES -- not to everyone with a login.

    Two boundaries, and both are load-bearing:

      * **Assignment.** An earlier version of this returned None above quota,
        which authorised any authenticated account to read and vote on any track
        in the catalog. Assignment is the existing "trusted with this footage"
        model; reuse it rather than inventing a wider one.
      * **No self-corroboration.** The seeder proposed this track, so counting
        them as one of its N independent raters is one person agreeing with
        themselves -- the single easiest way to inflate a consensus number, and
        the thing the multi-rater design exists to prevent. Admins are exempt
        because they adjudicate rather than contribute.
    """
    ...

def _redact_for_blind_review(track: dict, viewer_email: str, is_admin: bool) -> dict:
    """Hide the running consensus from a rater who has not voted yet.

    After the first verification `tracks.human_*` IS the first rater's answer, and
    the verify modal renders it. A second rater who sees it is anchored — and
    anchoring is precisely the behaviour multi-rater review exists to MEASURE,
    not to induce. Without this the flow manufactures agreement and inflates κ,
    which is worse than having no κ at all.

    Fields are set to None, never dropped, so the shape of the response is
    identical for every caller — a missing key would itself leak whether somebody
    else had already voted.
    """
    ...

def _propagations_per_hour() -> str:
    """`tracks.max_propagations_per_hour`, which nothing read.

    config.yaml.example has documented `max_propagations_per_hour: 10` since the
    knob was written, while the decorator below hardcoded 120 — so an operator who
    tightened the limit got twelve times what they asked for, with no way to tell.
    flask-limiter accepts a callable, evaluated per request, so the config value is
    now the limit. Absent config keeps the 120 that has actually been in force.
    """
    ...

@app.route('/api/tracks/propagate', methods=['POST'])
@_rate_limit(_propagations_per_hour)
@require_login
def api_tracks_propagate():
    """Kick off a SAM2 video propagation. Returns 202 + track_id immediately."""
    ...

@app.route('/api/tracks/<int:track_id>/status', methods=['GET'])
@require_login
def api_tracks_status(track_id):
    """Cheap polling endpoint — returns just propagation_status + error."""
    ...

@app.route('/api/tracks/<int:track_id>', methods=['GET'])
@require_login
def api_tracks_get(track_id):
    """Return a track with all its detections."""
    ...

@app.route('/api/tracks/video/<video_id>', methods=['GET'])
@require_login
def api_tracks_for_video(video_id):
    """List tracks for a video. Annotators see their own; admins see all."""
    ...

@app.route('/api/tracks/video/<video_id>/detections-by-frame', methods=['GET'])
@require_login
def api_tracks_video_detections_by_frame(video_id):
    """Polish 6 — every live track's per-frame bbox map for canvas overlays.

    Annotators see only their own tracks; admins see all (matches the rest of
    the /api/tracks/* access pattern).

    Also returns the video's REAL fps (read via cv2, not estimated). The
    HTML5 video element falls back to 30fps when the videoTracks API isn't
    supported (most browsers), so a 59.94fps video produces wrong frame
    numbers on the client. The canvas overlay needs `currentTime × real_fps`
    to look up the right bbox row.
    """
    ...

@app.route('/api/tracks/unverified', methods=['GET'])
@require_login
def api_tracks_unverified():
    """Triage queue: unverified tracks for the active annotator (or everyone, if admin).

    Query params:
      - video_id  (optional) — filter to a single video
      - limit     (optional) — default 50, hard-capped at 200 by the DB helper
      - strategy  (optional) — 'most_uncertain' (default) | 'diverse' | 'balanced'
                                 (Polish 5 B1 — active-learning sampling)
      - gold      (optional, 0..1) — Polish 5 B2 — fraction of slots reserved
                                       for blind gold-track injection (admin can
                                       force this; default reads from config).
    """
    ...

@app.route('/api/tracks/<int:track_id>/verify', methods=['POST'])
@require_login
def api_tracks_verify(track_id):
    """Human verifies a track is a real scar.

    Phase 2: scar_type, human_zone, AND human_side are all REQUIRED — the human
    is ground truth for type and location. Auto-* fields are never overwritten.
    """
    ...

@app.route('/api/tracks/<int:track_id>/reject', methods=['POST'])
@require_login
def api_tracks_reject(track_id):
    """Soft-delete a track. Detections are preserved as negative-example data."""
    ...

@app.route('/api/tracks/<int:track_id>/merge', methods=['POST'])
@require_login
def api_tracks_merge(track_id):
    """Tier 4J — mark this track as a duplicate of `into_track_id`.

    Body: {"into_track_id": <int>}
    Effect: soft-merge — sets merged_into_track_id; the row stays for audit.
    Validation (DB layer): both tracks exist, same video, neither already merged.
    """
    ...

@app.route('/api/admin/tracks/<int:track_id>/gold', methods=['POST'])
@require_admin
def api_admin_tracks_gold(track_id):
    """Tier 3H — admin toggles the gold-standard flag on a verified track.

    Body: {"is_gold": true|false}  (default toggles current value)
    Future: gold tracks get blind-injected into the triage queue for
    inter-rater calibration. Annotators can't tell gold from regular tracks.
    """
    ...

@app.route('/api/admin/tracks/recompute-consensus', methods=['POST'])
@require_admin
def api_admin_recompute_consensus():
    """Tier 4M — recompute consensus for all tracks. Useful after annotator
    weights or proficiency change."""
    ...

@app.route('/api/admin/models', methods=['GET'])
@require_admin
def api_admin_models():
    """The one place every model and its numbers are listed.

    Two populations, merged and labelled rather than blended: the committed
    catalogue at models/registry.json (source "file"), which covers foundation
    checkpoints, hand-trained weights, the deployed model and scaffolds alike,
    and the v20 model_registry table (source "db"), which is the orchestrator's
    own ledger of artifacts it trained and gated. Read-only on both, and the
    file is never written from here.

    `problems` is validate() on the committed file. It is surfaced rather than
    swallowed because a catalogue that has quietly gone stale is the failure
    this whole feature exists to prevent.
    """
    ...

@app.route('/api/admin/catalog', methods=['GET'])
@require_admin
def api_admin_catalog_list():
    ...

@app.route('/api/admin/catalog', methods=['POST'])
@require_admin
def api_admin_catalog_create():
    ...

@app.route('/api/admin/catalog/<int:shark_id>', methods=['GET'])
@require_admin
def api_admin_catalog_get(shark_id):
    ...

@app.route('/api/admin/catalog/<int:shark_id>', methods=['PATCH'])
@require_admin
def api_admin_catalog_patch(shark_id):
    ...

@app.route('/api/admin/catalog/<int:shark_id>', methods=['DELETE'])
@require_admin
def api_admin_catalog_delete(shark_id):
    ...

@app.route('/api/admin/encounters/<encounter_id>/link-catalog', methods=['POST'])
@require_admin
def api_admin_encounter_link_catalog(encounter_id):
    """Attach (or detach with shark_catalog_id=null) an encounter to a catalog entry."""
    ...

@app.route('/api/tracks/hint-calibration', methods=['GET'])
@require_login
def api_tracks_hint_calibration():
    """Each auto_* suggestion's own track record, for the annotator UI.

    Annotator-facing on purpose (the admin metrics route stays admin): the
    labeler being asked to trust a suggestion is exactly who should be able to
    see how often it has been right.

    `show` reflects `tracks.show_prediction_threshold` PER AXIS, so a suggestion
    that stops earning its place stops being offered without a deploy -- and
    only on the axis that failed. Below `min_n` there is no evidence either way,
    so the suggestion is still shown and labelled unproven: suppressing it there
    would guarantee it never accumulates the checks that could prove it.
    """
    ...

@app.route('/api/admin/metrics/auto-vs-human', methods=['GET'])
@require_admin
def api_admin_metrics_auto_vs_human():
    """Polish 5 E1 — model-agreement metrics across all verified tracks.

    Tells you which subsystems (zone projection, side, color) are weakest
    and which scar types are best/worst represented in the training set.
    Numbers come from `tracks.auto_*` vs `tracks.human_*` agreement.
    """
    ...

@app.route('/api/tracks/auto-propose', methods=['POST'])
@require_admin
def api_tracks_auto_propose():
    """Phase 5a — run the candidate proposer on a video.

    Two modes:
      1. Server-walks-video (default): omit `candidates`. Server uses the
         detector to scan the video, dedupe, and create up to top_k tracks
         with seed_source='auto'.
      2. Client-supplied candidates: pass {candidates: [{frame_number, bbox,
         class_name, score}, ...]}. Useful for offline batch jobs that ran the
         detector elsewhere. Server skips its own walk.

    Body: {"video_id": "...", "candidates": [...] (optional)}

    Returns 503 with a stable shape if the detector isn't configured/loaded
    (model file missing, detector.enabled=false). Frontend plumbed against
    this contract gracefully degrades to "no auto suggestions today."
    """
    ...

@app.route('/api/tracks/<int:track_id>', methods=['PATCH'])
@require_login
def api_tracks_patch(track_id):
    """Field-level overrides on a track. Currently allows: notes, human_color."""
    ...

@app.route('/api/tracks/<int:track_id>/preview', methods=['GET'])
@require_login
def api_tracks_preview(track_id):
    """Return a JPEG of a track detection frame with the propagated mask outlined.

    Query params:
      frame: frame number to render (default = best_frame_number)
      crop:  if 'bbox', return the frame cropped to the detection bbox + padding
             (Polish 7 — used by the triage card so the scar is big and clear).
      pad:   padding fraction (default 0.5 = 50% of bbox dim added on each side)

    Used by the verify modal AND the triage card; crop=bbox cuts mobile bandwidth
    dramatically and makes small scars visible without zooming.
    """
    ...

def _crop_to_bbox(img_bgr, bb: dict, pad_frac: float):
    """Crop a BGR image to bbox + padding fraction. Returns None on bad inputs."""
    ...

@app.route('/api/tracks/<int:track_id>/recompute', methods=['POST'])
@require_login
def api_tracks_recompute(track_id):
    """Re-run scoring + auto-color with the CURRENT config without re-propagating.

    Useful for tuning weights without burning SAM2 inference time. Only operates on
    detections already in the DB; doesn't decode persisted masks (cheap pass — uses
    stored sub-scores when present).
    """
    ...

def _require_export_video_id():
    ...

@app.route('/api/export/coco', methods=['GET'])
@require_login
def api_export_coco():
    ...

@app.route('/api/export/forms-csv', methods=['GET'])
@require_login
def api_export_forms_csv():
    ...

@app.route('/api/export/json', methods=['GET'])
@require_login
def api_export_json():
    ...

def _min_agreement_arg():
    """`min_agreement=3` is the headline case: scars at least three raters
    agreed on. A malformed value is REFUSED rather than coerced to the default —
    silently exporting the whole corpus to somebody who asked for a filtered
    slice is the failure that looks like success."""
    ...

def _consensus_rows_for_export():
    ...

@app.route('/api/export/consensus-csv', methods=['GET'])
@require_admin
def api_export_consensus_csv():
    ...

@app.route('/api/export/consensus-json', methods=['GET'])
@require_admin
def api_export_consensus_json():
    ...

@app.route('/api/export/consensus-summary', methods=['GET'])
@require_admin
def api_export_consensus_summary():
    """What the download WOULD contain, without downloading it — so the button
    can say "256 scars from 93 encounters" instead of handing over a file whose
    emptiness is indistinguishable from a broken export."""
    ...

def _gold_sets_with_items(set_id=None):
    ...

@app.route('/api/export/gold-json', methods=['GET'])
@require_admin
def api_export_gold_json():
    """Every gold standard set (frozen MLOps eval sets + their items) and every
    answer key, in one bundle. `?set_id=N` scopes to one set."""
    ...

@app.route('/api/export/golden-items-csv', methods=['GET'])
@require_admin
def api_export_golden_items_csv():
    """The frozen eval sets flattened to one row per item — the tabular grain a
    researcher compares a model against."""
    ...

def _dwc_adapter():
    """Build the shark adapter from config. Imported lazily so a config or
    vendored-package problem surfaces as a 500 on these routes rather than
    preventing the whole app from starting."""
    ...

@app.route('/api/export/dwc-validate', methods=['GET'])
@require_login
def api_export_dwc_validate():
    """Validate the DwC projection without writing anything.

    Run this before publishing: it reports exactly what an aggregator would
    reject (errors) and what would ingest but be less useful (warnings).
    """
    ...

@app.route('/api/export/dwc-archive', methods=['GET'])
@require_admin
def api_export_dwc_archive():
    """Build a Darwin Core Archive (zip) — the publishable artifact.

    `?strict=1` refuses to write when any validation error is present, which is
    the right setting for anything actually going to OBIS/GBIF.
    """
    ...

@app.route('/api/export/dwc-csv', methods=['GET'])
@require_login
def api_export_dwc_csv():
    """Flat DwC-termed CSV — same terms and column order as the archive core.

    `?compact=1` drops columns that are empty across every record.
    """
    ...

@app.route('/api/export/dwc-json', methods=['GET'])
@require_login
def api_export_dwc_json():
    """DwC-termed JSON: dataset metadata, occurrences, and both extensions."""
    ...

@app.route('/api/export/sheets', methods=['POST'])
@require_admin
def api_export_sheets():
    """Export annotations to a Google Sheet."""
    ...

@app.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    """Full-page admin dashboard."""
    ...

@app.route('/admin/scar-pin-paint')
@require_admin
def admin_scar_pin_paint():
    """The zone painter on a page of its own: the 3D template and the two flank
    maps at window size instead of inside the annotator's canvas panel. Same
    viewer, same editor, same save route; the page only supplies the DOM the
    modules expect and asks the editor to open. 404 unless both the picker and
    painting are on — like the paint route itself."""
    ...

@app.route('/api/admin/encounters/import', methods=['POST'])
@require_admin
def api_import_priority_csv():
    """Import the encounter priority CSV. Requires confirm=true form field (data protection)."""
    ...

def _priority_import_would_destroy() -> dict:
    """What `import_priority_csv` deletes before it re-inserts.

    Both priority importers replace the WHOLE pool: every `encounter_priority`
    and `encounter_completions` row is archived to a timestamped table and then
    DELETEd. Encounters absent from the incoming sheet do not come back, and
    they take their human-entered overlay (admin_flag, admin_notes,
    shark_catalog_id — the last of which becomes dwc:organismID on publication)
    with them.

    Returns counts, so the refusal can name what is at stake instead of
    gesturing at it. Best-effort: a count that cannot be read must not stop the
    gate from firing, so failure degrades to zeros rather than to "proceed".
    """
    ...

@app.route('/api/admin/encounters/import-sheet', methods=['POST'])
@require_admin
def api_import_priority_sheet():
    """Import encounter priority data from a Google Sheet.

    Requires confirm=true, exactly like the CSV importer it delegates to. Both
    call `db.import_priority_csv`, which wipes and re-inserts the pool; only the
    CSV route was gated, so the destructive operation was one prompt-and-click
    away in the dashboard while its file-upload twin demanded a confirmation.
    """
    ...

@app.route('/api/admin/encounters/import-input-sheet', methods=['POST'])
@require_admin
def api_import_input_sheet():
    """Import scar annotation data from the Google Forms input sheet (read-only)."""
    ...

@app.route('/api/admin/encounters', methods=['GET'])
@require_admin
def api_list_encounters():
    """Paginated encounter list with filtering and sorting."""
    ...

@app.route('/api/admin/encounters/<enc_id>', methods=['GET'])
@require_admin
def api_encounter_detail(enc_id):
    """Get full encounter detail with all annotator completions."""
    ...

@app.route('/api/admin/encounters/summary', methods=['GET'])
@require_admin
def api_encounter_summary():
    """Aggregate stats for dashboard header cards."""
    ...

def _encounter_exists(enc_id: str) -> bool:
    """Cheap existence check — one indexed lookup, not a full detail load.

    Lives here rather than in `annotation/database.py` only because that file is
    someone else's in this pass; it belongs beside `get_encounter_detail`.
    """
    ...

@app.route('/api/admin/encounters/<enc_id>/notes', methods=['POST'])
@require_admin
def api_encounter_notes(enc_id):
    """Update admin notes, and the triage flag only if one was explicitly sent.

    ``data.get("flag", "")`` used to coerce a missing key into '' and wipe the
    imported triage tier. Absent key now means "leave it alone"; only an explicit
    non-null "flag" in the body changes it.

    404 on an unknown encounter: `update_encounter_notes`' UPDATE matches zero
    rows and used to answer 200 "ok", so the modal flashed "Saved" for a note that
    went nowhere. The sibling assign route on the same object already 404s.
    """
    ...

@app.route('/api/admin/encounters/sync-flags', methods=['POST'])
@require_admin
def api_sync_flags():
    """Sync admin flags/notes to Google Sheets 'Admin Flags' tab."""
    ...

@app.route('/api/admin/encounters/<enc_id>/assign', methods=['POST'])
@require_admin
def api_assign_encounter(enc_id):
    """Assign an encounter to an annotator."""
    ...

@app.route('/api/admin/annotator-map', methods=['GET'])
@require_admin
def api_get_annotator_map():
    """Get CSV name -> email mappings."""
    ...

@app.route('/api/admin/annotator-map', methods=['POST'])
@require_admin
def api_update_annotator_map():
    """Update a CSV name -> email mapping."""
    ...

@app.route('/api/admin/consensus/refresh', methods=['POST'])
@require_admin
def api_refresh_consensus():
    """Recompute all consensus scores.

    This used to be the ONLY caller of `refresh_all_consensus` in production —
    a button. Meanwhile every student save deletes the encounter's computed cache
    row (`save_annotation`, qualified by NOT_IMPORT_SQL), so between a save and
    the next admin click the encounter genuinely has no consensus: the table
    renders "N/A" and `priority_need` sorts it with the never-analysed ones.
    `scripts/install_consensus_cron.sh` now runs the same function hourly on the
    box; this route stays as the "do it now" path and is unchanged.
    """
    ...

@app.route('/api/admin/effort', methods=['GET'])
@require_admin
def api_admin_effort():
    """How long the work takes, and which frames the time says are hard.

    Read-only and NOT gated: it reads `annotation_date`, which every row has
    carried since March, so it answers something today rather than only after
    somebody switches recording on. `metrics.effort.record` governs the client's
    clock, not this.

    `?annotator=` narrows to one person. `?full=1` returns the item lists as
    well as the counts — off by default because the four difficulty buckets are
    the whole corpus and nobody reads them in a browser.
    """
    ...

def _consensus_behind_counts(conn):
    """How far the computed consensus is behind, and how much of the corpus is
    not scar-scored at all.

    ONE definition, read by `/api/admin/consensus/status` and by the corpus
    export's summary. An export that reported a different staleness number from
    the readout beside the Refresh button would be the more convincing of the
    two, because it is attached to a file.

    An encounter is behind when somebody was asked about scars on it and there is
    either no computed row (an imported row in the live slot is a DIFFERENT
    POPULATION, not a stale copy of this one) or one older than its newest save.

    The scar-question filter is the whole point. `cache_consensus` returns None
    and DELETEs for an encounter where nobody was asked — 132 of 144 on this
    catalog are pose/keypoint-only — so counting those as behind made `behind`
    unable to reach zero, and the route's own docstring says it should hover near
    it. An operator then concludes the cron is broken when it is working.
    Reported separately rather than dropped, because "132 frames nobody was asked
    about" is a real fact about the corpus.
    """
    ...

@app.route('/api/admin/consensus/status', methods=['GET'])
@require_admin
def api_consensus_status():
    """How far behind the cached consensus is. Read-only — never recomputes.

    Exists so the gap above is VISIBLE rather than inferred from a blank cell,
    and so an operator can tell whether the cron is actually running on this box:
    `behind` should hover near zero and `newest_computed_at` should move every
    hour. It deliberately does not call `cache_consensus`, which writes.

    An encounter is `behind` when somebody was asked about scars on it and there
    is either no COMPUTED cache row (an imported row in the live slot is a
    different population, not a stale copy of this one — see `consensus_imports`)
    or one older than its newest save. Both timestamps are written by
    `datetime.now().isoformat()` in this same module, so the string comparison is
    a real time comparison; nothing else writes either column.

    `not_scar_scored` is the rest: encounters annotated only for pose/keypoints,
    which the consensus engine has nothing to score and never will. They used to
    be counted as behind, which is why `behind` could not reach zero.
    """
    ...

@app.route('/api/admin/side-hints/status', methods=['GET'])
@require_admin
def api_side_hints_status():
    """How much of the assignment queue carries a SIDES SEEN suggestion, and
    whether the batch that fills it has stopped running. Read-only.

    Same job as `/api/admin/consensus/status` beside it, for the same reason: the
    annotator UI renders "no suggestion" identically whether the encounter was
    walked and the model declined, or nobody has run the precompute since the last
    twenty videos were assigned. Only an operator can tell those apart, and only if
    something says which.

    It cannot compute anything, by design and not merely by omission. The walk is
    52 ms/frame on the lab Mac's MPS across 576,902 frames; this box has 2 cores
    and 1.9 GB of RAM and would need CPU inference at 172 ms/frame. Rows arrive
    here through `scripts/precompute_encounter_sides.py --import-jsonl` and by no
    other path.

    Answers with `enabled: false` when `pose.encounter_side.enabled` is off but
    still reports the numbers — an operator checks coverage BEFORE turning the
    suggestion on, and a route that refuses to say anything until the feature is
    live makes that impossible.
    """
    ...

def _scar_consensus_v2():
    """Resolved `scars.consensus` v2 knobs. `enabled` is False unless BOTH the
    flag is set and `identity` is `geometric` — production runs a minimal
    config.yaml with no `scars:` section at all, so absence must mean off.

    Thresholds are NOT defaulted from `scar_consensus`'s module constants by
    import here on purpose: they are re-stated with the same values so a
    malformed config degrades to a documented number rather than to whatever the
    algorithm module happens to hold. Every run records what it used in `params`.
    """
    ...

def _encounter_scar_inputs(encounter_id):
    """Every rater's saved scars for one encounter, in the shape compute_consensus
    takes. Read-only, and the pure module never learns where any of it came from.

    The three-way split mirrors `db_datasets._unit_scar_inputs`, which does the
    same job for one queue unit — and the rules are the ones that matter more than
    the plumbing:

      * a rater who was never SHOWN the scar form is `not_asked`, not `absent`. A
        pose assignment stores `scars_visible=""`, and counting that as "I saw no
        scars" is what deflated every scar's agreement ratio and then wrote a
        fabricated 0.0 agreement rate against a labeler who did the keypoint task
        they were given.
      * `side` comes from the SCAR and only from the scar. `sides_visible` is an
        encounter-level COVERAGE statement (measured: 58.2% agreement with the
        true per-frame flank, against 97.2% for the pose hint and a 54.5%
        always-Left baseline), and `scar_consensus._lane` consumes side as
        IDENTITY — a wrong flank does not lower agreement, it puts two raters in
        different lanes where they can never agree at all.
      * `reviewed` carries the sides each rater says they could see, which is what
        `eligible_raters` needs to keep an absence vote inside the flanks that
        rater was actually in a position to judge. It comes from
        `db_datasets.sides_seen`, which is the ONE definition and which drops a
        coverage claim the labeler merely ACCEPTED from the machine suggestion —
        otherwise a model answer silently narrows a human's absence-vote
        eligibility and nothing downstream can tell. `model_sourced_sides` names
        the raters that applied to, so the count is reported rather than buried.
    """
    ...

def _v2_cluster_payload(c):
    """One cluster, JSON-safe. `n_voters`/`annotators` are properties, so
    `dataclasses.asdict` silently drops exactly the two fields a reader needs."""
    ...

@app.route('/api/admin/consensus/geometric/<path:enc_id>', methods=['GET'])
@require_admin
def api_geometric_consensus(enc_id):
    """The v2 geometric consensus for one encounter, beside the shipped one.

    Admin-only and read-only. Admin because a cluster names who voted what, which
    is the peer identity every other consensus surface in this repo redacts
    (`signal_consensus.redact_for`, `db_datasets.redact_agreement_for`): a labeler
    who can see how a colleague called a scar starts calling it the same way, and
    that anchoring is what the multi-rater design exists to MEASURE. Read-only
    because nothing here is cached — `consensus_cache` holds the signature
    algorithm's answer and must keep holding exactly that until the lab decides to
    switch, or the two numbers stop being comparable.

    `signature` is `compute_encounter_consensus`, which only SELECTs, so the two
    identities can be compared on real data before anybody commits to one.
    """
    ...

@app.route('/api/admin/seed-weights', methods=['POST'])
@require_admin
def api_seed_weights():
    """Bulk-seed proficiency weights.

    Body: {"weights": {"email@example.com": 0.9, ...}, "experts": ["email@example.com"]}

    The admin dashboard no longer offers a button for this. It had one, and it posted
    an empty body — so `weights` was always `{}`, `seed_annotator_weights` returned at
    its `if not weights` guard, and the UI reported success over a no-op. Nothing else
    in the repo ever supplied a payload. Rather than build a bulk weights editor for a
    seven-person lab, the button is gone and `POST /api/admin/annotator-weights` (a
    working per-user setter, used by the annotator table) is the supported path.

    The route is kept because it does work when given real input — it is reachable by
    script for a bulk import — but it now refuses an empty payload instead of claiming
    to have done something. Note `seed_annotator_weights` only updates users still on
    the exact 0.5 default, so it seeds; it does not overwrite.
    """
    ...

@app.route('/api/admin/annotator-weights', methods=['GET'])
@require_admin
def api_get_annotator_weights():
    """List all users with their weights and annotation counts."""
    ...

@app.route('/api/admin/annotator-weights', methods=['POST'])
@require_admin
def api_update_annotator_weights():
    """Update proficiency_weight or is_expert for a user."""
    ...

def _import_raw_scar_csv(path: str, source_file: str):
    """`db.import_raw_scar_csv` with a STABLE import identity.

    The keyword is a data-layer addition; if this checkout predates it, degrade to
    the old call and say so, rather than 500ing an import over a keyword. Do not
    turn this into a bare `except TypeError` — that would swallow a genuine
    TypeError raised inside the importer and report it as a missing feature.
    """
    ...

def _upload_identity(filename: str, path: str) -> str:
    """A stable name for an uploaded CSV: its filename plus a hash of its bytes.

    `legacy_scar_reports` dedupes on UNIQUE(source_file, source_row), so the
    identity handed to an importer has to survive a re-upload of the same file. A
    tempfile name never does. Streamed, because these uploads are megabytes.
    """
    ...

@app.route('/api/admin/import-historical', methods=['POST'])
@require_admin
def api_import_historical():
    """Import historical consensus and/or raw scar CSVs."""
    ...
SMART_ASSIGN_MIN, SMART_ASSIGN_MAX = (1, 25)

def _split_smart_assign(results):
    """(assigned rows, videos rows minted) out of `db.smart_batch_assign`.

    Smart assign MINTS a `videos` row for an encounter that has none, and
    "Assigned 10 encounters" hid four fabricated, media-less rows. The data layer
    reports that count by returning a dict; a layer that still returns a bare list
    reads as 0 minted — the claim it was already making, not a new one.
    """
    ...

@app.route('/api/admin/encounters/candidates', methods=['GET'])
@require_admin
def api_assignment_candidates():
    """Get prioritized list of encounters needing annotation."""
    ...

@app.route('/api/me/next-encounter', methods=['POST'])
@require_login
def api_next_encounter():
    """PULL one encounter on demand, instead of waiting for a push batch.

    Why a pull endpoint over the ENCOUNTER queue rather than /api/me/next-task:
    next-task samples unverified TRACKS, and `tracks` holds 1 row, so it can
    serve one item ever. The encounter queue has ~1,700 ranked candidates.

    Unlike get_next_task (read-only, writes no assignment row), this goes through
    smart_batch_assign, so the pulled item appears in the annotator's list and in
    admin workload/quota views like any other assignment.
    """
    ...

@app.route('/api/admin/assignments/recycle', methods=['POST'])
@require_admin
def api_recycle_assignments():
    """Return long-stale 'pending' assignments to the pool.

    auto_replenish only fires below 5 pending; every annotator currently sits far
    above that with March-2026 work, so nobody can receive new assignments at all.
    Recycling unblocks replenish. Dry-run unless confirm=true.
    """
    ...

@app.route('/api/admin/encounters/smart-assign', methods=['POST'])
@require_admin
def api_smart_batch_assign():
    """Auto-assign a batch of encounters to an annotator."""
    ...

@app.route('/api/admin/pose-frames/stats', methods=['GET'])
@require_admin
def api_pose_frame_stats():
    """Get pose frame pool stats: total, unassigned, per-annotator breakdown."""
    ...

@app.route('/api/admin/pose-frames/assign', methods=['POST'])
@require_admin
def api_assign_pose_frames():
    """Assign a batch of pose frames to an annotator."""
    ...

@app.route('/api/admin/workload', methods=['GET'])
@require_admin
def api_annotator_workload():
    """Get annotator workload and semester quota progress."""
    ...

@app.route('/api/admin/annotator-quota', methods=['POST'])
@require_admin
def api_update_annotator_quota():
    """Set per-annotator semester quota."""
    ...

@app.route('/api/admin/semester', methods=['GET'])
@require_admin
def api_get_semester():
    """Get active semester info."""
    ...

@app.route('/api/auth/access-token', methods=['GET'])
@_rate_limit('10 per minute')
@require_admin
def api_access_token():
    """Return the user's OAuth access token for Google Picker.

    Security note: This exposes the raw OAuth token to the admin frontend.
    Required by Google Picker API (client-side). Mitigated by:
    - Admin-only access (@require_admin)
    - CSP prevents XSS exfiltration
    - Token scoped to Drive/Sheets only
    """
    ...

@app.route('/api/admin/backup-config', methods=['GET'])
@require_admin
def api_backup_config():
    """Return backup-related config (picker API key, saved folder)."""
    ...

@app.route('/api/admin/config-report', methods=['GET'])
@require_admin
def api_config_report():
    """What is switched on here, and what is merely absent from the config?

    Read-only. Changes nothing, turns nothing on.

    This exists because production runs a minimal config.yaml that is gitignored
    AND rsync-excluded, so whole sections are simply ABSENT there and each feature
    silently falls back to its coded default. Working out why a feature is dark
    previously meant reading the code, the deployed config and the volume schema
    together. Each row reports the flag, whether the section exists at all, the
    effective value, and whether the tables it needs are actually present — which
    separates "switched off" from "switched on but its migration never ran", a
    distinction that has bitten this project before.
    """
    ...

@app.route('/api/admin/backup-status', methods=['GET'])
@require_admin
def api_backup_status():
    """Report the last successful DB backup (heartbeat written by backup_to_drive.py).

    Flags stale=True if the newest backup is older than `fresh_hours` (default 48),
    so the admin dashboard can surface a missed nightly backup.
    """
    ...

@app.route('/api/admin/set-annotation-folder', methods=['POST'])
@require_admin
def api_set_annotation_folder():
    """Save the annotation export Drive folder ID to config."""
    ...

def _snapshot_sqlite(src_path: Path, dst_path: Path) -> None:
    """Take a consistent snapshot of a live WAL database, and verify it.

    A raw `shutil.copy2` of catalog.db copies the MAIN FILE ONLY, so every
    committed-but-uncheckpointed transaction — everything still in
    catalog.db-wal — is silently missing from the result. That is not a narrow
    race: with thread-local connections held for a worker's whole lifetime, a
    PASSIVE autocheckpoint cannot reset the WAL while any reader holds an older
    snapshot, so under a live class the WAL carries real work indefinitely. The
    uploaded file then opens fine and passes quick_check while being short by N
    annotations, which is indistinguishable from a complete backup at the only
    moment it matters.

    SQLite's Online Backup API reads THROUGH the WAL under proper locking, which
    is what scripts/backup_to_drive.py already does. Raises on a snapshot that
    fails integrity, so a broken backup is never uploaded as a good one.
    """
    ...

@app.route('/api/admin/backup-to-drive', methods=['POST'])
@require_admin
def api_backup_to_drive():
    """Upload app data to a user-selected Drive folder."""
    ...

@app.route('/api/users', methods=['GET'])
@require_admin
def api_list_users():
    ...

@app.route('/api/users', methods=['POST'])
@require_admin
def api_upsert_user():
    ...

@app.route('/api/admin/active-learning/select', methods=['POST'])
@require_admin
def api_active_learning_select():
    """Run active learning frame selection in a background thread."""
    ...

@app.route('/api/admin/active-learning/status', methods=['GET'])
@require_admin
def api_active_learning_status():
    """Return the current status of the active learning background task."""
    ...

def _bbox_as_list(bbox):
    """`body_bbox` as [x, y, w, h] floats, whatever shape it was stored in.

    canvas.js writes `{x, y, width, height}` (static/js/canvas.js, the ONLY
    writer in this repo); older rows and `_bbox_from_keypoints` use a 4-list.
    The export indexed the dict as a list and died with KeyError: 0 on the first
    real row — 231 of 305 image annotations on the live catalog — so it produced
    nothing while its test, seeded with the list shape, stayed green. Same reader
    scripts/export_yolo_pose.py:112 uses. None for anything unrecognised or
    degenerate, which the caller counts as "no bbox".
    """
    ...

def _bbox_from_keypoints(kps, w: int, h: int, pad_frac: float=0.05):
    """[x, y, w, h] in pixels spanning the PLACED keypoints, or None.

    `body_bbox` is usually absent on a complete skeleton in this corpus, so this
    is the normal path rather than an edge case. Deliberately NOT
    `gold_scoring`'s normaliser: that divides by the animal's SHORT axis for PCK,
    while a YOLO box wants the actual extents.

    Padding is a fraction of the spread, clamped to the image. A degenerate spread
    (one point, or a line) yields no box — a zero-area box is a broken label, not
    a conservative one.
    """
    ...

def _validated_dataset_name(raw) -> Optional[str]:
    """A dataset name safe to use as a single path segment under exports/.

    This value is free text from an admin form and was used unchecked as
    `ROOT / "exports" / dataset_name`, then handed to `shutil.rmtree`. pathlib
    makes that arbitrary directory deletion: an ABSOLUTE second operand replaces
    the whole prefix (`Path("/app/exports") / "/etc"` -> `/etc`), `".."` walks
    out, and — the case that needs no malice at all — CLEARING the field yields
    `""`, which collapses to `exports/` itself and rmtree's the entire
    bind-mounted exports directory.

    Returns None if the name is unusable, so the caller can 400 rather than
    silently rewriting what the operator asked for.
    """
    ...

@app.route('/api/admin/export-training-data', methods=['POST'])
@require_admin
def api_export_training_data():
    """Export annotations as YOLO pose format, stratified split, zipped."""
    ...

@app.route('/api/admin/export-training-data/status', methods=['GET'])
@require_admin
def api_export_training_data_status():
    """Return the current status of the export task."""
    ...

@app.route('/exports/<filename>')
@require_admin
def serve_export(filename):
    """Serve exported zip files for download."""
    ...
