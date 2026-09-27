"""The one parser for `LOCYYMMDDnn` encounter codes.

The lab's naming convention *is* the data model: a code carries the site, the field
date, and the shark's sequence number within that day. Since a trip is one day at one
site, the trip key is already inside every code — trip ordering needs no new table, only
a parser everyone agrees on.

Why one module
--------------
Four regexes over this grammar had drifted across the codebase, each with its own idea
of which prefixes are real. This is now canonical;
`scripts.import_reid_records.parse_code` delegates here so `annotation/db_reid.py`, and
through it the Darwin Core `eventDate`, keep working unchanged.

Why `status` instead of None
----------------------------
Measured over 1,847 live encounter codes, the residue is not noise — it is a to-do list:

    1798  ok                    site, date and sequence all sound
      34  month_out_of_range    AN13130507 — a 13th month; provably not a date
       2  day_out_of_range      AN12106202
       4  unknown_site          ANI×3, AR×1 — prefixes outside the vocabulary
       6  not_a_code            'Folder APT18 (all encounterIDs)' — import junk
       2  truncated_seq         ANO2311040 — one digit short, shark number lost
       1  future_year           an AN code dating to 2031

Returning None for all of those would say "unparseable" about six different problems
with six different fixes. `status` lets the ingest UI show a trip's actual defects.

The `unknown_site` case matters most for correctness. `site_of('ANI13101401')` used to
return **'AN'** — it matched the `AN` prefix and stopped — while `CODE_RE` choked on the
`I` and returned no date at all. So those rows claimed a site nobody verified and
carried no date. Here an unrecognised prefix yields `site=None` with the raw prefix kept
in `site_raw`, which is the honest encoding *and* gives the UI something to offer a
mapping for. CLAUDE.md's rule: never guess a field.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date as _date
from typing import Optional

@dataclass(frozen=True)
class ParsedCode:
    """What a code says about itself. Every field is Optional — absent means unknown."""
    raw: str
    status: str
    site: Optional[str] = None
    site_raw: Optional[str] = None
    year: Optional[int] = None
    date: Optional[str] = None
    seq: Optional[int] = None
    trip_key: Optional[str] = None
    note: Optional[str] = None

    @property
    def ok(self) -> bool:
        ...

    @property
    def has_date(self) -> bool:
        ...

def year_from_yy(yy: int) -> int:
    """Two-digit year to four. Matches the legacy pivot so no existing date moves."""
    ...

def parse(code: Optional[str], *, today: Optional[_date]=None) -> ParsedCode:
    """Parse one encounter code. Never raises.

    `today` exists so the future-year check is testable and deterministic; it defaults
    to the real current date.
    """
    ...

def trip_key(code: Optional[str]) -> Optional[str]:
    """SITE+YYMMDD for a code that carries a date, else None."""
    ...

def legacy_dict(code: Optional[str]) -> dict:
    """The exact shape `scripts.import_reid_records.parse_code` has always returned.

    Kept byte-compatible because `annotation/db_reid._encounter_dates` feeds the Darwin
    Core `eventDate`, and a shifting date on a published record is unrecoverable.

    One deliberate behavioural change: an unrecognised prefix now yields `site=None`
    rather than the prefix it happened to share a few letters with. Four encounters are
    affected (ANI×3, AR×1) and all four already had no date, so no published eventDate
    moves — they simply stop asserting a site nobody verified.
    """
    ...
