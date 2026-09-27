"""Stream A (re-ID) Phase A3 — scar healing / aging: pure trajectory logic.

No I/O, no DB, no heavy deps (stdlib only) → import-safe and unit-testable in isolation.
`annotation/db_reid.py` gathers per-individual scar observations from the DB and calls
`build_chain_proposal()` per matched scar-chain; the routes surface the result. PROPOSE-ONLY:
nothing here writes anything — it returns plain dicts a human reviews.

Research basis (plans/09-a3-healing-research.md, verified 2026-06-23):
  - White-shark colour-healing progression is **pink/red (fresh) → white (intermediate) → black
    (old)**, fading to skin over years [Frontiers Mar. Sci. 2025, 10.3389/fmars.2025.1520348].
    NOTE: this is the species-correct AGE direction; it intentionally differs from
    segmentation/track_scoring.py's per-pixel visual-`SEVERITY_ORDER` comment (which is not an age
    scale). A3 only *interprets* an already-assigned colour label with the correct age direction.
  - Healing is quantified as **relative** %-area reduction normalized by an internal scale, anchored
    to FIRST sighting (absolute size/age are ill-posed from monocular field photos)
    [Conserv. Physiol. coaa120]. So area trend is emitted only with a body-size scale at both ends.
  - Underwater colour is unreliable absolutely → trust the trajectory (Δstage) and human-confirmed
    colour over a single auto-colour observation; confidence reflects this.
"""
from __future__ import annotations
import json
from typing import Dict, List, Optional, Tuple

def color_to_stage(color: Optional[str]) -> Tuple[Optional[int], str]:
    """Map a scar colour label to (stage_ordinal, stage_label). Unknown → (None, 'unknown')."""
    ...

def scar_key(side: Optional[str], zone: Optional[str], scar_type: Optional[str]) -> str:
    """Identity of a scar ACROSS sightings = (side, zone, type), colour-free (colour is the variable
    being measured). Mirrors the consensus signature minus colour. Normalized; blanks kept as ''."""
    ...

def _days_between(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """Whole days between two ISO YYYY-MM-DD dates (b - a). None if either unparizable."""
    ...

def build_chain_proposal(catalog_id: Optional[int], skey: str, observations: List[dict]) -> Optional[dict]:
    """Summarize one scar-chain (same (side,zone,type) on one individual across sightings).

    `observations` = list of per-sighting dicts with keys: encounter_code, obs_date (ISO|None),
    obs_year, track_id, color, color_source ('human'|'auto'|'none'), stage_ordinal (int|None),
    area_rel (float|None), side, zone, scar_type. Returns a proposal dict, or None if <2 DATED
    sightings (a trajectory needs at least two points in time). Pure — never raises on bad data.
    """
    ...

def _classify_trend(known_stages: List[int], first_stage: Optional[int], last_stage: Optional[int], area_change: Optional[float]) -> str:
    """healing | stable | worsening | new | inconclusive.

    Colour-stage trajectory is the PRIMARY signal (relative, species-validated direction); relative
    area is corroborating. 'new' = a later sighting looks fresher (pink) than an earlier one — a
    fresh re-injury at the same site. Area thresholds are deliberately loose (monocular noise).
    """
    ...

def _confidence(dated: List[dict], known_stages: List[int], area_change: Optional[float]) -> float:
    """Heuristic 0..1. Rewards human-confirmed colour, more sightings, and an available area scale;
    penalizes auto-only colour and missing stages (underwater colour caveat — plans/09 F6)."""
    ...

def _notes(dated: List[dict], span_days: Optional[int], area_change: Optional[float]) -> str:
    ...
