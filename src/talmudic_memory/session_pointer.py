"""SessionStart pointer text: Gemara is indexed; search it. Not a Gemara dump."""

from __future__ import annotations

SESSION_START_POINTER = (
    "Talmudic Memory is active. You are part of an ongoing project. "
    "Files may be unfinished or still present a later-rejected path as current — leftover, not a new mandate. "
    "Gemara is the record earlier agents and the operator left (Sugyot, Resume, breadcrumbs): "
    "why decisions were made and how the work was carried out — tried, worked, failed and why — so it isn't retried. "
    "Later records supersede what a file still says. If reality contradicts a Sugya, add a new one with the operator; the old record stays. "
    "SessionStart already synced and ran preflight. Your first move: launcher in `.talmudic/runtime.json`, "
    'then `orient "<task>"` or `recall "<question>"`. '
    "Quote S-#### / R-####; tie work to the record, not a leftover file. "
    "Search pulls this task's slice; `digest` dumps the workstream; globbing the tree or the plugin cache is starting over. "
    "After Gemara has the why and how, open files to extend or change the work. "
    "You inherit this handoff, and it's yours to keep current: when this session learns a why, a how, "
    "or a why-not a future agent would miss, record it in Gemara "
    "through that same launcher (`sugya` or `note`). Material writes go through In-Flight on that launcher."
)


def session_start_pointer() -> str:
    return SESSION_START_POINTER


def estimate_tokens(text: str) -> int:
    """UTF-8 bytes / 4. Good enough to compare dump vs fetch without a tokenizer dep."""
    return max(1, (len(text.encode("utf-8")) + 3) // 4)
