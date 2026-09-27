"""Darwin Core adapter for the shark scar catalog.

Projects this app's schema onto Darwin Core so the catalog can be published as a
DwC Archive (OBIS/GBIF) without changing how anything is stored. Read-only: it
opens the DB, streams rows, and writes nothing back.

Three occurrence grains feed the core, because the app genuinely records three
different kinds of observation:

  1. `reid_sightings`  — photographic survey records. The richest grain: real
     dates, coordinates, sex, tag and biopsy identifiers. HumanObservation.
  2. `annotations`     — a shark annotated in a video frame. MachineObservation
     (the animal was recorded by a camera, then identified by a human — the same
     treatment GBIF applies to camera-trap data). Carries an absence signal:
     `no_shark` becomes occurrenceStatus=absent, which is real ecological
     information and is normally thrown away.
  3. `reid_catalogue`  — imported re-ID records not covered by either above.

`morphometrics` becomes the MeasurementOrFact extension; videos and sighting
photos become Multimedia.

Individual identity flows through the existing link:
    shark_catalog.organism_id  ←  encounter_priority.shark_catalog_id  ←  encounter
so an occurrence carries dwc:organismID exactly when a human has adjudicated the
individual. Unlinked occurrences are still valid DwC — they just have no
organismID, which is the honest representation of "we saw a shark but haven't
identified which one".
"""
import json
import logging
from typing import Any, Dict, Iterator, Optional
from marine_dwc import BaseAdapter, Contact, DatasetMeta, Measurement, Multimedia, Occurrence, measurement_id, merge_dynamic_properties, normalize_sex, occurrence_id, event_id
from annotation.database import get_conn
from annotation.db_datasets import sides_from_model

def _model_side(payload: Dict[str, Any]) -> Optional[str]:
    """The model's own flank suggestion for this row, or None.

    Populated whether or not the human touched the control: where they did
    answer, having both beside each other is the comparison the suggestion is
    judged by. Falls back to `sides_visible` when an accepted hint carries no
    side of its own, so the value is re-attributed rather than lost.
    """
    ...
_FEET_TO_METERS = 0.3048

def _stable_event_id(key: Optional[str]) -> Optional[str]:
    """eventID for a sampling occasion, or None when there is no stable key for it.

    Two failure modes have to be avoided at once, and they pull in opposite directions.

    Minting from a *substitute* key is unstable: this used to fall back to
    `videos.id`, which is `str(uuid.uuid4())[:12]` (database.py:535), so re-importing a
    clip minted a new id and silently moved the event out from under every record
    already published against it.

    But minting from a *missing* key is worse. `marine_dwc.ids._uuid5` renders None as
    the empty string before hashing, so `event_id(DATASET_ID, None)` returns a perfectly
    valid uuid — the SAME one for every keyless row, collapsing unrelated encounters into
    one shared event.

    So an occasion we cannot name stably gets no eventID at all. `Occurrence.event_id` is
    Optional and no validator requires it; absent is the honest encoding, and the field
    starts working the moment a real encounter code is filled in.
    """
    ...

def _site_fields(site: Optional[str]) -> Dict[str, Optional[str]]:
    ...

def _iso_datetime(date: Optional[str], time_obs: Optional[str]) -> Optional[str]:
    """Combine a date and a clock time into one ISO 8601 eventDate.

    Returns the bare date when the time is absent or unparseable — a wrong
    timestamp is worse than a coarser one.
    """
    ...

def _json_field(raw: Optional[str]) -> Dict[str, Any]:
    """Parse an annotation's json_data blob; never raise on malformed rows."""
    ...

class SharkScarAdapter(BaseAdapter):
    """Darwin Core projection of the shark scar catalog.

    `publish_coordinates` passes stored coordinates through at full precision
    (the configured behaviour for this dataset). Set it False to withhold them —
    the export then populates dwc:informationWithheld so consumers can see that
    location was suppressed rather than never recorded.

    `default_scientific_name` fills the taxon for occurrences whose individual
    isn't catalogued yet. Without it every record exports untaxonomised and
    cannot be indexed by an aggregator — but it is left unset by default,
    because a wrong species applied to a whole dataset is far more damaging than
    a missing one. Set it in config.yaml under `dwc:`.
    """

    def __init__(self, *, publish_coordinates: bool=True, include_absences: bool=True, default_scientific_name: Optional[str]=None, default_scientific_name_id: Optional[str]=None, license_url: Optional[str]=None, rights_holder: Optional[str]=None, institution_code: Optional[str]=None, contact_name: Optional[str]=None, contact_email: Optional[str]=None, contact_organization: Optional[str]=None):
        ...

    @classmethod
    def from_config(cls, cfg: Optional[Dict[str, Any]]=None) -> 'SharkScarAdapter':
        """Build from the app's parsed config.yaml (`dwc:` section)."""
        ...

    def dataset_meta(self) -> DatasetMeta:
        ...

    def _organism_map(self, conn) -> Dict[str, Dict[str, Any]]:
        """encounter_code → the catalogued individual, where one is linked."""
        ...

    def _external_id_map(self, conn) -> Dict[str, str]:
        """photo_id → 'kind:value; kind:value' for dwc:otherCatalogNumbers."""
        ...

    def _dates_for(self, conn, encounters) -> Dict[str, Dict[str, Any]]:
        """encounter_code → {obs_date, obs_year}.

        Delegates to the existing resolver in db_reid so DwC dates are derived
        identically to the healing/re-ID pipelines — videos.date when present,
        else the encounter-code grammar. Reimplementing it here would guarantee
        the two drift apart.
        """
        ...

    def _coords(self, lat, lon) -> Dict[str, Any]:
        """Coordinate block, honouring the publish/withhold setting."""
        ...

    def _sighting_occurrences(self, conn) -> Iterator[Occurrence]:
        """Photographic survey records — the richest grain."""
        ...

    def _annotation_occurrences(self, conn) -> Iterator[Occurrence]:
        """A shark annotated in a video frame.

        `no_shark` annotations become occurrenceStatus=absent rather than being
        dropped: a surveyed frame with no animal is a real negative observation,
        and DwC models exactly that.
        """
        ...

    def _catalogue_occurrences(self, conn) -> Iterator[Occurrence]:
        """Imported re-ID records with no matching sighting row."""
        ...

    def occurrences(self) -> Iterator[Occurrence]:
        ...

    def measurements(self) -> Iterator[Measurement]:
        """Morphometrics and recorded sizes.

        Pixel morphometrics are emitted with measurementUnit='pixel' and a method
        that says so. They are comparable within an encounter, not absolute
        lengths — converting them to metres without a scale reference would
        fabricate precision.
        """
        ...

    def media(self) -> Iterator[Multimedia]:
        """Videos backing annotation occurrences, and sighting photographs."""
        ...
