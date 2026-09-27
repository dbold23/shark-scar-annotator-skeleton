"""3D scar pin — the server half.

The labeler clicks a point on the rest-pose great white template instead of
clicking a zone on the 2D SVG. The click yields a *surface address*
``(face, bary)`` on that template, which is pose-invariant: it names a spot on
the animal, not a spot on a picture of the animal. Everything else the form and
the exports want — zone, side, station ``s``, girth angle ``theta`` — is
DERIVED from that address plus the template asset.

Three rules shape this module.

**The client's derived fields are never trusted.** The browser computes them for
immediate display (it has the mesh loaded anyway), but a zone is a scientific
value, so the server recomputes every one of them from ``(template, face,
bary)`` and overwrites whatever arrived, stamping ``derived_by: "server"``. A
client-supplied zone is a self-graded exam — the same argument
``pose3d_masks.iou_vs_source`` makes about a client-supplied agreement score.

**The gate is OFF by absence.** Production runs a minimal ``config.yaml`` with
whole sections missing, so ``pin_enabled`` defaults to False and a malformed
``scars:`` block degrades to False rather than raising inside a student's save.
With the gate off ``sanitize_scars`` STRIPS ``pin`` from every scar, so the
stored blob is byte-identical to today — a half-shipped experimental key in the
annotation JSON would reach every export and every consumer downstream.

**Garbage is dropped, never propagated.** A pin that fails validation, or one
that arrives while the asset is missing, becomes ``None`` and is counted. It is
not silently repaired and it is not allowed to abort the save: losing a
student's frame because a decorative field was malformed is the worse failure.

**Station and zone are derived AT THE CLICKED POINT, girth angle is not.** ``s``
is ``(snout_y - y) / body_length_snout_to_precaudal``, both of which the asset
carries, so it is exactly recomputable from the interpolated position — and it
has to be: a face on this mesh spans up to 20.9% of body length (p90 4.6%), so
reading ``face_s`` off the centroid quantises the station to as much as 83 cm on
a 4 m animal, and 10.6% of faces straddle a ``cuts_s`` boundary, publishing the
centroid's zone for a click at the far corner. ``theta_deg`` CANNOT be
recomputed on a ``rule`` or ``painted`` asset: it is measured from a per-slice
body-core z curve that the build script derives from the mesh and did not write
into the asset. It therefore stays at FACE resolution there, deliberately and as
a documented part of the pin contract, not as an oversight of the field name.
Zone binning consumes it, but the bands are 44-58 degrees wide, so
face-resolution theta is far below the resolution of the decision it feeds.

**A ``map`` asset changes that, and changes what a zone IS.** Per-face labels
cannot give a straight zone boundary at any mesh density — the boundary is a
staircase of triangle edges, and refining the mesh only makes the steps smaller.
So on a ``map`` asset the zone truth lives on a 2D BODY MAP in body coordinates
(station ``s`` along the animal x girth angle ``theta`` around it, one panel per
flank), where a line is straight by construction. The map carries
``core_curve``, so ``theta_deg`` becomes exactly recomputable at the clicked
point and IS recomputed — ``face_theta_deg`` stops being the answer and becomes
a stale build artefact. ``face_zone`` is still written for every body face (the
map sampled at the face centroid) because every existing consumer reads it, but
a pin's zone is the map sampled at the exact click, never the centroid's.

Fin faces (``face_part != 0``) are not on the map at all: their zone is their
part's code (D / P / T / V), exactly as today. A fin does not stop being a fin
because of where along the animal it sits, and putting fins on an (s, theta)
map would require a projection that does not exist.

Pure python — json + math only. No Flask, no sqlite, no numpy (this runs inline
on the save path, and the asset is a few thousand floats).
"""
from __future__ import annotations
import bisect
import json
import logging
import math
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
_BARY_EPS = 0.01
_BARY_SUM_EPS = 0.02
MAP_VERSION = 1

def rle_decode(runs: Any, n: int) -> bytearray:
    """``"count:index,count:index,…"`` -> a ``bytearray`` of exactly ``n`` cells.

    Deliberately the dumbest format that works: JS and Python both decode it in
    six lines, so client and server cannot drift in the way a bit-packed or
    base64 encoding invites. Raises ``ValueError`` on anything that is not
    exactly ``n`` cells — a run list that is short would decode to a map with a
    silent hole in it, and a hole reads as zone ``codes[0]`` everywhere.
    """
    ...

def rle_encode(cells: Any) -> str:
    """Inverse of :func:`rle_decode`. Empty input encodes to the empty string."""
    ...

def pin_enabled(cfg: Any) -> bool:
    """``scars.pin.enabled``, default False.

    Note the ``or {}`` rather than ``.get(k, {})``: a section present but null
    (``scars:`` with nothing under it, which is what a half-edited YAML file
    looks like) yields None, and None has no ``.get``. Anything non-dict on the
    way down degrades to False instead of raising on the save path.
    """
    ...

def paint_enabled(cfg: Any) -> bool:
    """``scars.pin.paint_enabled``, default False.

    A SECOND gate under the same section, not a widening of ``pin.enabled``:
    reading the painted asset is what every labeler does, and rewriting it is
    what one admin does once. An operator who switched the picker on must not
    thereby hand out a brush that rewrites the zone vocabulary of the whole
    corpus. Same degradation rules as ``pin_enabled`` — absent, null or
    malformed all mean False.
    """
    ...

def _num(v: Any) -> Optional[float]:
    """A finite float, or None. Rejects bool, which is an int in python."""
    ...

def _element_ok(key: str, v: Any) -> bool:
    """Per-element type check for the five per-face arrays.

    Length alone was checked, which let a rebuilt asset carry a string or a null
    in ``face_s`` / ``face_theta_deg`` / ``face_part`` straight through
    validation and into the stored pin — exactly the "partially-correct template"
    this function exists to refuse.
    """
    ...

def _parse_landmarks(raw: Any) -> Optional[tuple[float, float]]:
    """``(snout_y, body_length_snout_to_precaudal)`` or None.

    None means "station stays at face resolution" — a degraded pin, not a
    refused template, because an asset without landmarks is still a usable mesh.
    """
    ...

def _parse_zone_params(raw: Any) -> Optional[dict]:
    """The station cuts + dorsal/ventral bands, or None if any part is unusable.

    All-or-nothing on purpose: a cut list without the band that splits one of its
    members would bin half the animal correctly and guess at the rest.
    """
    ...

def _parse_core_curve(raw: Any) -> Optional[dict]:
    """``{"s": [...ascending], "z": [...]}`` or None.

    The per-station body-core z centre the build script already computes and
    used to throw away. Without it ``theta`` is not recomputable at a point, so
    a ``map`` asset that lacks it is refused wholesale rather than degraded: a
    body map indexed by an angle nobody can measure is not a partially useful
    asset, it is a lookup into the wrong row.
    """
    ...

def _zone_map_error(zm: Any) -> Optional[str]:
    """Why ``zm`` is not a usable body map, or None if it is.

    One validator for both doors — the loader (which turns a reason into "refuse
    the asset") and the save route (which turns it into a 400 the admin can act
    on). Two copies of this would drift, and the drift would be an asset the
    server writes and then refuses to read.
    """
    ...

def _parse_zone_map(raw: Any) -> Optional[dict]:
    """The decoded body map, or None. Stores CELLS, not the rle string: every
    reader wants a random-access lookup, and keeping both invites the day they
    disagree."""
    ...

def _parse_vertex_array(raw: Any, key: str, n_verts: int, lo: float, hi: float) -> tuple[bool, Optional[list]]:
    """``(ok, values)`` for an optional per-vertex float array.

    Absent is fine — it is a shader convenience, and Builder A's asset may
    predate it. PRESENT AND WRONG is not: it would upload a wrong body
    coordinate to every vertex and draw zone boundaries in the wrong place while
    the server still answered correctly, which is the hardest kind of
    disagreement to notice. So a malformed array refuses the whole asset.
    """
    ...

def _parse_face_uv(raw: Any, n_faces: int) -> tuple[bool, Optional[list]]:
    """``(ok, values)`` for the optional per-corner skin UVs.

    ``face_uv`` is ``n_faces * 6`` floats — (u, v) for each of the three corners
    of each face, in FACE order, because the viewer's geometry is non-indexed
    (three render vertices per face). Absent is fine: an asset built before the
    skin was baked still draws zones, which is the whole fallback.

    PRESENT AND WRONG is not fine, so it refuses the template — the same rule as
    ``vertex_s``, for a stronger version of the same reason. A truncated or
    non-numeric array would texture part of the animal from whatever floats
    happened to follow, and a wrongly-textured shark reads as a plausible
    animal rather than as a failure. No range check: a UV outside [0, 1] is
    legitimate (the sampler wraps), and clamping here would silently move a
    texel.
    """
    ...

def _parse_face_uv_seam(raw: Any, n_faces: int) -> tuple[bool, Optional[list]]:
    """``(ok, flags)`` for the optional per-face UV-seam flag: 1 where a face's
    three UVs straddle a UV island, so the viewer paints it neutral grey instead
    of stretching texels across half the atlas.

    Strictly 0/1 ints, and ``bool`` is refused even though it is an int in
    python: a ``true`` in the asset is a hand-edit, and accepting it here would
    make the one malformed asset load while every other consumer sees a type it
    did not expect.
    """
    ...

def _parse_skin(raw: Any) -> tuple[bool, Optional[dict]]:
    """``(ok, skin)`` for the optional skin-texture descriptor.

    ``url`` must live under ``/static/``. This is a containment check, not
    tidiness: the asset is a JSON file an admin can hand-edit and a paint save
    rewrites, and the value goes straight into an ``<img>`` the labeler's
    browser fetches. Unconstrained, a stray edit points every annotator at a
    third-party host. ``//host/x`` and ``https://…`` both fail the prefix; the
    explicit ``..`` test refuses a traversal that starts inside /static/ and
    climbs out.
    """
    ...

def _parse_skin_version(raw: Any) -> tuple[bool, Optional[int]]:
    """``(ok, version)``. Non-negative int or absent; anything else refuses the
    asset, because a cache-buster that is not a number is a cache-buster that
    does not bust."""
    ...

def _parse_template(raw: Any) -> Optional[dict]:
    """Validate the asset's shape. A partially-correct template is worse than no
    template: it would derive a plausible zone from a truncated array."""
    ...

def load_template(path: Path | str | None=None) -> Optional[dict]:
    """Parse the template asset, cached by (path, mtime, size).

    Returns None — logged once per path — when the file is missing or
    malformed. Builder A writes this asset in parallel, and the whole feature is
    optional, so an absent asset must degrade to "no pins" and never to a 500.

    ``path`` defaults to None rather than to ``ASSET_PATH`` directly: a default
    argument is bound once at def time, so the module global would be frozen at
    import and a test (or a future relocation) that repoints ``ASSET_PATH``
    would be silently ignored while every assertion still read plausibly.
    """
    ...

def invalidate(path: Path | str | None=None) -> None:
    """Drop the cached parse for ``path`` (or every path).

    The cache key already carries ``st_mtime_ns``, so a rewritten file is
    normally picked up on its own. This is the belt to that suspenders: a paint
    save rewrites the asset from inside the same process that is serving it, and
    "the writer explicitly says the parse is stale" costs one dict clear and
    removes the whole class of filesystem-timestamp-granularity bugs from the
    argument. Cheap enough to do unconditionally; the next read re-parses a few
    thousand floats.
    """
    ...

def validate_pin(pin: Any, tpl: Optional[dict]=None) -> tuple[bool, str]:
    """(ok, err). ``tpl`` bounds the face index; without it the range check is
    skipped and only the shape is verified."""
    ...

def _normalized_bary(bary: list) -> list[float]:
    ...

def station_of(tpl: dict, y: float) -> Optional[float]:
    """Station along snout -> precaudal for a template-space ``y``, or None when
    the asset carries no landmarks."""
    ...

def core_z(tpl: dict, s: float) -> Optional[float]:
    """The body-core z centre at station ``s``, linearly interpolated and
    CLAMPED at both ends (``numpy.interp``'s behaviour, which is what the build
    script used to derive the published ``face_theta_deg``)."""
    ...

def theta_at(tpl: dict, xyz: list) -> Optional[float]:
    """Girth angle in degrees at a template-space point, or None without a core
    curve or landmarks.

    ``0`` is the dorsal midline, ``180`` the belly midline; unsigned, because
    the flank is carried separately (see :func:`flank_of`). Uses the rounded
    ``s`` that :func:`station_of` publishes, so the angle is a function of the
    station the pin reports rather than of a slightly different one.
    """
    ...

def flank_of(xyz: list) -> str:
    """``"L"`` / ``"R"`` under the asset's ``shark_left: -x`` convention. Exactly
    the split ``derive``'s ``side`` uses, so a pin can never report Left and be
    sampled off the right-hand panel."""
    ...

def map_cell(tpl: dict, s: float, theta_deg: float, flank: str) -> Optional[tuple[int, int]]:
    """``(row, col)`` into the body map. Row-major, rows ``0..h/2-1`` LEFT and
    ``h/2..h-1`` RIGHT; row 0 of a panel is the dorsal midline."""
    ...

def map_zone_at(tpl: dict, xyz: list) -> Optional[str]:
    """The body map sampled at a template-space point, or None when the asset
    cannot answer (no map, no core curve, no landmarks). Callers fall back to
    ``face_zone`` — never to the rule, which the map exists to replace."""
    ...

def zone_at(tpl: dict, s: float, theta_deg: float, part: int) -> Optional[str]:
    """Re-bin a body zone at an arbitrary station, or None if it cannot be.

    Only ``part == 0`` (body) is binned: D / P / T are anatomical parts, not
    stations, and a fin does not stop being a fin because of where along the
    animal it sits. Verified against the shipped asset: re-binning every face at
    its own centroid reproduces the published ``face_zone`` for all 5,628 faces,
    so this is a strict refinement of the centroid value and never a second
    opinion about it.
    """
    ...

def derive(pin: dict, tpl: dict) -> dict:
    """Recompute every derived field from (face, bary) and the template.

    The client's face/bary survive verbatim (bary renormalised); everything else
    it sent is replaced. Side comes from the sign of the interpolated x under
    the asset's ``shark_left: -x`` convention, and is reported in the FORM's
    vocabulary ("Left"/"Right") so the pin can drive the existing side radio
    without a second mapping living somewhere else.

    ``s`` and ``zone`` are computed AT THE INTERPOLATED POINT (see the module
    docstring). ``theta_deg`` is the FACE's on a ``rule`` or ``painted`` asset,
    because those assets do not carry the body-core curve it is measured from —
    but a ``map`` asset does, so there ``theta_deg`` is recomputed at the
    clicked point too, and ``face_theta_deg`` is not consulted. Where the asset
    lacks landmarks or zone params, values fall back to the face centroid rather
    than to a guess.
    """
    ...

def sanitize_scars(scars: Any, enabled: bool, tpl: Optional[dict]) -> tuple[Any, int, int]:
    """Enforce the pin contract over a scars list, in place.

    Returns ``(scars, dropped, derived)``. Off => the key is REMOVED, so the
    stored blob matches today byte for byte. On => each pin is validated and
    re-derived server-side, or replaced with ``None`` and counted as dropped.
    Never raises: a non-list, a non-dict member, or a garbage pin all pass
    through without taking the save down with them.
    """
    ...

def apply_pin_policy(scars: Any, cfg: Any) -> tuple[Any, int, int]:
    """``sanitize_scars`` with the gate and the asset resolved for you.

    THE one call every route that accepts a client scars payload makes. It exists
    because there was briefly more than one such route: the answer-key authoring
    route stored the payload verbatim, so with the gate off it wrote ``"pin":
    null`` into ``gold_answers.answer_json`` (not byte-identical to today) and
    with the gate on it froze the CLIENT's zone and side as the grading key —
    unvalidated, unstamped, and then re-published by the gold export. Three lines
    duplicated per route is three lines the next route forgets.
    """
    ...

class StaleRevision(Exception):
    """The caller painted on top of a revision that is no longer current.

    Carries ``paint_revision`` — the revision actually on disk — so the route
    can tell the client what to reload. Two admins painting the same asset is
    rare and a silent last-write-wins is unrecoverable: the loser's whole
    session of strokes disappears with no error anywhere, and the only record
    that they existed is a ``.prev`` file nobody knows to look at.
    """

    def __init__(self, current: int):
        ...

def _utc_now_iso() -> str:
    ...

def _umask() -> int:
    """Read the process umask without leaving it changed."""
    ...

class AssetUnreadable(RuntimeError):
    """The asset ON THE SERVER could not be parsed. Distinct from ``ValueError``
    on purpose: the route maps that to 400, and a truncated template file is not
    the client's payload being wrong."""

def _under_asset_lock(p: Path, fn):
    """Run ``fn()`` holding an exclusive lock on ``<asset>.lock``.

    Read-check-write with no lock made the 409 racy: two admins' saves could
    both read revision N, both pass, both write N+1, and one whole session of
    strokes would vanish while both were told they succeeded. Prod runs four
    gunicorn workers, so the lock is a FILE lock, the same shape as media_warm's
    cross-process claim; a ``threading.Lock`` cannot see the other three
    processes.

    Shared by every writer of this asset. A second writer with its own copy of
    the lock/revision/.prev/atomic-write dance is a second chance to get one of
    those four wrong, and the one that gets it wrong is the one nobody tested.
    """
    ...

def _read_asset_for_write(p: Path) -> tuple[dict, int]:
    """``(raw, current_revision)`` read from the FILE, not the cached parse.

    The cache holds a *validated projection* of the asset — a handful of arrays,
    some landmarks, no ``zone_colors``, no ``source``, no ``refinement`` — so
    writing from it would quietly amputate every key the loader does not
    consume. The file is the truth; the parse is a reader's convenience.
    """
    ...

def _guard_revision(raw: dict, base_revision: int, current: int) -> None:
    """Raise ``StaleRevision`` unless the caller painted on top of what is on
    disk. Called AFTER the payload is validated, so a client holding a stale
    revision AND sending garbage is told about the garbage — retrying the same
    garbage against a fresh revision would only fail again."""
    ...

def _commit_asset(raw: dict, p: Path, by: str, current: int) -> int:
    """Stamp the revision, take one generation of ``.prev``, write atomically,
    keep the file mode, drop the cache. Returns the new revision.

    **Geometry is never touched by any caller** — vertices, faces, ``face_s``
    and ``face_side`` are properties of the mesh, not of somebody's opinion
    about where the flank ends, and a pin stored against face N last week must
    still name the same triangle.
    """
    ...

def _counts(codes) -> dict[str, int]:
    ...

def save_painted_zones(face_zone: Any, by: str, base_revision: int, path: Path | str | None=None) -> dict:
    """Write a hand-painted ``face_zone`` back into the asset, under a lock.

    The LEGACY per-face door, kept working: a boundary painted triangle by
    triangle is a staircase, which is why the body map exists, but assets and
    editors painted this way must keep loading and saving.
    """
    ...

def _save_painted_zones_unlocked(face_zone: Any, by: str, base_revision: int, p: Path) -> dict:
    """Changes exactly six keys: ``face_zone``, ``face_part`` (recomputed from
    the new zones), ``zone_source``, ``paint_revision``, ``painted_at``,
    ``painted_by``.

    Raises ``ValueError`` for a payload that is not exactly ``n_faces`` known
    zone codes, and ``StaleRevision`` when the caller's ``base_revision`` is not
    the one on disk.
    """
    ...

def save_zone_map(zone_map: Any, by: str, base_revision: int, path: Path | str | None=None, part_overrides: Any=None) -> dict:
    """Write a hand-painted BODY MAP back into the asset, under the same lock.

    A map save IS a paint save — same revision counter, same 409, same ``.prev``,
    same atomic write — because it is the same decision (a human saying where the
    zones are) recorded in a coordinate system where a boundary can be straight.
    """
    ...

def _save_zone_map_unlocked(zone_map: Any, by: str, base_revision: int, p: Path, part_overrides: Any=None) -> dict:
    """Store the map and re-derive ``face_zone`` for every BODY face at its
    centroid.

    ``face_zone`` is kept — and kept honest — because every existing consumer
    reads it: the rule-mode loader, the exports, the viewer's per-face colour
    upload, ``relabel_*`` scripts. It is now a DERIVED projection of the map
    rather than the truth, so it is recomputed here rather than accepted from
    the client: a client-supplied projection of a client-supplied map is two
    chances for them to disagree, and the disagreement would only surface as a
    pin whose zone differs from the colour under the cursor.

    FIN faces are copied through untouched. Their zone is their part's code and
    they are not on the map; re-deriving one would sample whatever body zone
    lies under the fin.

    Geometry is read from the FILE (``vertices`` / ``faces`` / ``face_part`` /
    ``landmarks`` / ``core_curve``), not from the cached projection, for the
    same reason ``_read_asset_for_write`` exists.
    """
    ...

def health_payload(cfg: Any) -> dict:
    """The public capability probe the client gates the 3D panel on.

    ``enabled`` reflects the CONFIG only — an operator who switched the feature
    on and has no asset yet must be able to tell that apart from a feature
    nobody turned on. Everything else goes null whenever there is nothing to
    serve, so a client cannot fetch a URL that will 404.
    """
    ...

def remove_islands(cells: bytes | bytearray, w: int, h: int, max_cells: Optional[int]=None, passes: int=3) -> tuple[bytearray, int]:
    """Recolour every enclosed island to the zone that encloses it.

    An island is a 4-connected component of one zone index, INSIDE one flank
    panel, whose every boundary neighbour carries a single other index. It is
    recoloured to that index — unless it is the largest component of its zone
    (the zone's main body, which may legitimately sit inside another zone: the
    pectoral footprint inside the flank) or larger than ``max_cells`` (default
    2% of a panel). Repeats up to ``passes`` times because removing one island
    can enclose another. Returns ``(cells, n_changed)``; the input is not
    modified. Same algorithm as the editor's "Remove islands" button.
    """
    ...
