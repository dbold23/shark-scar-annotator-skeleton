"""Scar objects — the gradable unit.

The lab's protocol is *encounter -> which sides are visible -> scar by scar*. The
app was *frame -> box*. This module holds the missing middle: an object that
belongs to the ANIMAL rather than to a frame or a clip.

    encounter_passes         one per (encounter, annotator) -- the sighting
      └─ encounter_pass_clips    sides_visible + usable, PER CLIP
    scar_objects             one physical mark on one animal   <- THE UNIT
      └─ tracks                  one appearance in ONE clip     (unchanged)
           └─ track_detections     per-frame boxes              (unchanged)

WHY ABOVE tracks AND NOT INSTEAD OF THEM. `tracks` already is the per-clip
object: propagation, per-frame detections, per-annotator `track_verifications`,
consensus. But `tracks.video_id` is NOT NULL and `merge_track` hard-refuses
cross-video merges, so a track is a tracklet *within one clip* -- and 35% of
encounters have more than one clip. Adding a parent costs one table plus one
nullable FK; making tracks span clips would be a rewrite of the propagator, the
scorer and every export.

GRAIN, DECIDED BY MEASUREMENT NOT PREFERENCE:

    scars_visible        ENCOUNTER  a property of the animal, not the camera
    sides_visible        PER CLIP   differs across clips of one encounter in
                                    22 of 112 (annotator, clip) pairs, and across
                                    frames of ONE clip in 5 of 16 -- per-clip is
                                    the coarsest grain the data actually supports
    scar_count_declared  ENCOUNTER  exists nowhere today; it is the only thing
                                    that makes RECALL measurable, because a
                                    consensus built from marks cannot see a scar
                                    the whole cohort missed

CROSS-CLIP IDENTITY IS A HUMAN CLICK, NEVER INFERRED. Attaching a second clip's
track to an existing scar_object is an explicit action. `tracks.signature_json`
may later RANK suggestions; it must never auto-attach. Attach is reversible by
nulling the FK, because the annotator is now making a judgement they never made
before -- "is this the mark I logged in clip 1?" -- and they will sometimes be
wrong.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from annotation.database import _column_exists, get_conn

def init_object_tables():
    """Create the object tables + tracks.scar_object_id. Idempotent."""
    ...

def encounter_clips(encounter_id: str) -> List[Dict]:
    """Every clip of one encounter, assigned or not.

    The sighting card lists all of them deliberately. An encounter can have up to
    17 clips and `encounter_priority.video_id` is a single scalar, so assignment
    can currently only ever reach ONE of them -- an annotator who sees just their
    assigned clip has no way to know the other four exist, and "I saw no scars on
    this animal" would be a claim about a third of the footage.
    """
    ...

def open_pass(encounter_id: str, annotator: str, video_ids: List[str]) -> int:
    """Start (or resume) one annotator's sighting of one encounter."""
    ...

def record_clip(pass_id: int, video_id: str, *, sides_visible: Optional[str]=None, usable: Optional[str]=None) -> Dict:
    """Record what was visible in ONE clip, and recount progress.

    clips_reviewed is recomputed from the child rows rather than incremented, so
    re-reviewing a clip cannot inflate it past clips_total.
    """
    ...

def close_pass(pass_id: int, *, scars_visible: Optional[str]=None, scar_count_declared: Optional[int]=None) -> Dict:
    """Finish a sighting. Refuses while any clip is unreviewed.

    The refusal is the point of the encounter grain: 'I saw no scars' is only
    evidence about the animal if the person actually looked at every clip of it.
    """
    ...

def get_pass_by_id(pass_id: int) -> Optional[Dict]:
    """One pass by its row id — for answering "whose is this?".

    The routes take `pass_id` from the URL, so they need to resolve the owner before
    writing. Deliberately does NOT join the clips: the only caller is an ownership
    check, and fetching children it will not read invites someone to use this where
    `get_pass` belongs.
    """
    ...

def get_pass(encounter_id: str, annotator: str) -> Optional[Dict]:
    ...

def create_scar_object(encounter_id: str, annotator: str, *, provenance: str='human', **fields) -> int:
    ...

def attach_track(track_id: int, scar_object_id: Optional[int]) -> Dict:
    """Say that this clip's track is an appearance of that physical scar.

    `scar_object_id=None` detaches. Reversible on purpose: cross-clip identity is
    a human judgement made from two different views of a moving animal, and an
    irreversible attach would make people hesitate to record one at all.
    """
    ...

def list_scar_objects(encounter_id: str, annotator: Optional[str]=None) -> List[Dict]:
    ...
