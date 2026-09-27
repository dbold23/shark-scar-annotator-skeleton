"""Who is one person. Stdlib-only, no DB, no Flask.

This exists as its own module rather than living in ``database.py`` because two
of its consumers — ``scar_consensus.py`` and ``signal_consensus.py`` — are pure
algorithm layers that must not import the storage layer. A shared helper that
forced them to would have been a worse fix than the duplication.

The rule was implemented FIVE times (scar_consensus, db_gold, signal_consensus,
db_pose3d, and ``db_signals._norm_email``). All five agreed on
``.strip().lower()``, which is precisely why nobody would have noticed the day
one of them stopped agreeing.
"""
from __future__ import annotations
from typing import Any

def norm_annotator(email: Any) -> str:
    """One human, one identity.

    ``annotations.annotator`` and ``signal_labels.annotator`` keep the JWT's
    casing, while the assignment tables lower-case theirs. Unfolded, the same
    person becomes two raters — and the phantom marks nothing, so it reads as a
    labeler who disagrees with everything: ``n_raters`` inflates, kappa collapses,
    and a ghost row appears on the scorecard. Worse in the other direction, one
    person labelling under two spellings CORROBORATES THEMSELVES, defeating the
    one-vote-per-annotator rule that every agreement figure here rests on.

    Nothing errors either way, which is what makes it worth a module.
    """
    ...
