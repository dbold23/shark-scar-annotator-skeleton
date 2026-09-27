"""Marking a trainee's Training-Survey answers against the lab's expert KEY.

Pure: no sqlite3, no Flask, no config reads — the same split ``gold_scoring.py``,
``scar_consensus.py`` and ``signal_consensus.py`` use, so every rule here can be
pinned on hand-built rows instead of a database. The only project import is the
vocabulary in ``annotation.models`` (stdlib-only itself).

The lab's onboarding works like this: a student fills in the Google-Forms
"Training Survey" for a fixed set of encounters, and an expert has already
filled in a KEY sheet for the same encounters. Both arrive as loosely spelled
spreadsheet rows ("6 _FLANK", "Above_Gills", "Propeller", "Tag"...), so the
first half of this module is normalisation onto the app's own codes, and the
second half is the marking.

Three rules, each a way to be quietly unfair if got wrong:

  * **A scar's identity is ``(side, zone, scar_type)``. Colour is reported but
    never disqualifying.** Same rule as ``gold_scoring.DEFAULT_REQUIRED_FIELDS``:
    pink-vs-white on a healing scar is a judgement call that experienced
    annotators split on, and failing somebody for it would measure agreement
    with one person's eye rather than skill. Making colour part of the identity
    also manufactures phantom disagreements — measured on the recovered corpus,
    keying on colour produced 3,717 "scars" where geometry finds 2,049. So the
    match is exact on the three-tuple, and ``color_agreement`` rides alongside
    as a diagnostic.
  * **An encounter the trainee never submitted is not counted.** The survey is
    served one encounter at a time, and a student who stopped after twelve has
    twelve answers, not twelve answers and thirty blanks. Treating the
    un-attempted rest as misses would make the score a progress bar — a student
    halfway through would fail with a perfect record. ``coverage`` says how much
    of the key was attempted, separately, so nobody can quote the F1 without it.
  * **"Nothing attempted" is ``None``, never 0.0.** A zero here would rank a
    student who has not started below one who answered everything wrong.

Known no-scar encounters are questions too: the key lists them with an empty
scar list, the trainee answers by ticking "Scars visible: No" and reporting
nothing, and that earns one true positive. Reporting scars on an animal the
expert says is clean costs one false positive per invented scar.
"""
from __future__ import annotations
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple
from annotation.models import ScarColor, ScarType, ZONE_LABELS

def _clean(s: Any) -> str:
    """Upper-case, and collapse every spreadsheet separator to one space."""
    ...

def norm_side(s: Any) -> str:
    """``"Left"`` / ``"Right"`` / ``""``.

    "Both" comes back empty on purpose: it is the encounter-level ``sides_visible``
    answer, and a per-scar side of "Both" is not a location (``scar_vocab.js``
    makes the same call for the form).
    """
    ...

def norm_zone(s: Any) -> str:
    """A ``BodyZone`` code (``"1"``..``"9"``, ``"D"``, ``"P"``, ``"T"``, ``"B"``,
    ``"V"``) or ``""``.

    Two spellings are in the wild. The form writes ``"<code> _<LABEL>"``
    (``AREA_FORM_FORMAT``), so a leading token that is a code wins outright —
    ``"6 _FLANK"`` is zone 6 whatever follows. The expert KEY writes the label
    alone in whatever case and separator came to hand (``"Flank"``,
    ``"Above_Gills"``, ``"above gills"``, ``"Pectoral_fin"``), which the alias
    table resolves. A spreadsheet that has turned ``6`` into ``6.0`` is caught by
    the leading-code rule too.
    """
    ...

def norm_type(s: Any) -> str:
    """A ``ScarType`` name or ``""``.

    The form writes ``"<TYPE> _<description>"`` (``SCAR_TYPE_FORM_FORMAT``), so the
    first token decides; the KEY writes ``"Propeller"``, ``"Tag"``, ``"Scratch"``
    and so on, which the alias table folds. Anything unrecognised is ``""``
    rather than ``"OTHER"``: OTHER is a claim the rater made, not a bucket for
    strings this code cannot read.
    """
    ...

def norm_color(s: Any) -> str:
    """A ``ScarColor`` name or ``""``. First token wins, ``GRAY`` folds to ``GREY``."""
    ...

def _norm_confidence(v: Any) -> Optional[int]:
    """``"1".."5"`` (the form's strings) → int; anything else ``None``."""
    ...

def _is_no(v: Any) -> bool:
    ...

def norm_encounter(s: Any) -> str:
    """An encounter code as the catalog spells it: stripped and UPPER-CASED.

    Every code in ``videos.encounter_code`` and ``encounter_priority`` is upper-case
    (``LOCYYMMDDnn``); the survey and the KEY are typed by hand, and a key row on
    ``"apt22062203 "`` against a survey row on ``"APT22062203"`` would otherwise be
    two encounters — the rater scored as never having attempted the one that is in
    the key. Same reason ``norm_annotator`` exists for people.
    """
    ...

def _enc(row: Mapping[str, Any]) -> str:
    ...

def signature_of(row: Mapping[str, Any]) -> Signature:
    """The normalised ``(side, zone, scar_type)`` of one row."""
    ...

def dedupe(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Collapse one rater's rows to unique scar signatures per encounter.

    The survey takes one scar per submission, so a rater who saw three scars on
    an animal submitted three rows — and one who re-submitted the same scar to
    fix its confidence submitted it twice. Rows are folded on
    ``(side, zone, scar_type)``; colour, being outside the identity, is the modal
    colour across the folded rows (ties to the first seen), ``confidence`` is the
    maximum and ``n_rows`` says how many rows folded in.

    Returns ``{encounter_id: [ {side, zone, scar_type, color, confidence, n_rows}, ... ]}``
    plus one extra entry, ``result[ABSENT_KEY]``: the ``set`` of encounter ids on
    which the rater made an explicit ABSENCE claim (``scars_visible`` "No" with no
    scar type on the row). An absence encounter is ALSO present under its own id
    with an empty list, so the plain "which encounters did this rater attempt"
    reading needs no special case. A row with ``scars_visible`` "No" AND a type is
    taken as the scar claim it spells out — the type is the more specific answer.
    A row with neither a readable type nor a "No" still marks the encounter as
    attempted (present, empty) but claims nothing.
    """
    ...

def split_absent(deduped: Mapping[str, Any]) -> Tuple[Dict[str, List[Dict[str, Any]]], Set[str]]:
    """``dedupe()``'s result → ``(reports, absent)`` as :func:`score_rater` takes them."""
    ...

def build_key(rows: Iterable[Mapping[str, Any]], *, min_confidence: Optional[int]=None) -> Dict[str, List[Signature]]:
    """The expert's answers: ``{encounter_id: [Signature, ...]}``.

    An encounter listed with an EMPTY list is a known no-scar animal (the expert
    said "Scars visible: No" and reported nothing), and is a question the rater
    can get right or wrong. An encounter absent from the dict is not in the key
    at all and is never scored.

    ``min_confidence`` drops expert rows below that confidence. If that empties an
    encounter the encounter is DROPPED, not listed empty — "the expert was unsure
    about every scar here" is not "the expert says there are none", and listing
    it empty would fail every rater who saw what the expert tentatively saw.
    An explicit absence row survives the filter; it carries no confidence.
    """
    ...

def build_key_colors(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[Signature, str]]:
    """``{encounter_id: {Signature: colour}}`` — the expert's colours, kept OUT of
    the key itself so the key type stays ``list[Signature]``. Feed it to
    :func:`score_rater` as ``key_colors`` to get ``color_agreement``."""
    ...

def _f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    ...

def _reported_signatures(entries: Iterable[Any]) -> Dict[Signature, str]:
    """``{Signature: colour}`` from either dedupe dicts or bare tuples."""
    ...

def _key_signatures(entries: Iterable[Any]) -> Tuple[List[Signature], Dict[Signature, str]]:
    """Key values are 3-tuples by contract; a 4-tuple with a colour is tolerated
    and its colour used when no ``key_colors`` was passed."""
    ...

def score_rater(key: Mapping[str, List[Signature]], reports: Mapping[str, List[Dict[str, Any]]], absent: Optional[Iterable[str]]=None, *, key_colors: Optional[Mapping[str, Mapping[Signature, str]]]=None) -> Dict[str, Any]:
    """Mark one rater's deduped reports against the key.

    ``reports`` is ``dedupe()``'s per-encounter dict (the ``ABSENT_KEY`` entry is
    tolerated and, when ``absent`` is not given, used). ``absent`` is the set of
    encounters on which the rater explicitly claimed no scars.

    Per encounter that the rater attempted AND that is in the key:

      * key has scars — ``matched = key ∩ reported`` (exact on Signature),
        ``missed = key − reported``, ``extra = reported − key``; tp/fn/fp are
        their sizes. ``absent_correct`` is ``False`` if the rater claimed absence
        (every key scar is then a miss), else ``None`` — the question was not asked.
      * key is empty (known no-scar) — tp=1 if the rater claimed absence and
        reported nothing, else fp = number of scars reported; ``absent_correct``
        says which.

    Micro precision/recall/f1 pool tp/fp/fn over those encounters; ``macro_f1``
    averages the per-encounter f1. ``proficiency`` is the micro f1 — one number,
    named for what the admin dashboard calls it. ``coverage`` is
    ``n_encounters / len(key)``. **Nothing attempted → f1, proficiency, precision,
    recall, macro_f1 and color_agreement are all ``None``**, never 0.0.

    ``color_agreement`` is the fraction of true positives whose colour matched
    the expert's, over the TPs where the expert's colour is known (``key_colors``,
    or a 4th tuple element on the key). ``None`` when there is no such TP. It is
    reported and never folded into f1 — see the module docstring.
    """
    ...

def redact_for_labeler(score: Mapping[str, Any]) -> Dict[str, Any]:
    """What the trainee themselves may see: their headline numbers and nothing
    that reconstructs the key.

    ``per_encounter`` carries ``missed`` — literally the answer to every
    question they got wrong — and ``matched``/``extra`` narrow the rest. Even
    ``n_key_scars`` says how many to look for. The same reason
    ``signal_consensus.redact_for`` and ``db_pose3d.redact_agreement_for`` exist:
    a training set that has leaked is a training set the lab cannot reuse.
    ``computed_at`` is passed through when present.
    """
    ...
