"""Escaped, line-highlighted full-file previews for human review."""
from __future__ import annotations

import difflib
import html


def changed_lines(before: str, after: str) -> dict:
    removed, added = set(), set()
    blocks = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, before.splitlines(), after.splitlines(), autojunk=False
    ).get_opcodes():
        if tag != "equal":
            blocks += 1
            removed.update(range(i1 + 1, i2 + 1))
            added.update(range(j1 + 1, j2 + 1))
    return {"before": removed, "after": added, "blocks": blocks}


def highlighted_code(source: str, changed: set[int], *, side: str) -> str:
    """Return inert HTML; source is always escaped, including script/HTML text."""
    if side not in {"before", "after"}:
        raise ValueError("Unknown review side")
    marker = "−" if side == "before" else "+"
    label = "Removed or replaced" if side == "before" else "Added or changed"
    rows = []
    for number, line in enumerate(source.splitlines(), 1):
        is_changed = number in changed
        kind = f" changed-{side}" if is_changed else ""
        title = f"{label} line {number}" if is_changed else f"Unchanged line {number}"
        rows.append(
            f'<div class="review-line{kind}" title="{title}">'
            f'<span class="review-number">{number}</span>'
            f'<span class="review-marker">{marker if is_changed else " "}</span>'
            f'<code class="review-source">{html.escape(line) or " "}</code></div>'
        )
    if not rows:
        rows.append('<div class="review-empty">Empty file</div>')
    return """
<style>
.review-code {border: 1px solid #8885; border-radius: 8px; overflow: auto;
    max-height: 600px; padding: 10px 0; font-size: 13px; line-height: 1.7;}
.review-lines {display: table; min-width: 100%; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;}
.review-line {display: table-row;}
.review-line > span, .review-line > code {display: table-cell; white-space: pre;}
.review-number {width: 3.5em; text-align: right; padding: 0 10px; opacity: .65; user-select: none;}
.review-marker {width: 1.5em; font-weight: bold; user-select: none;}
.review-source {font: inherit; padding-right: 14px; background: transparent; color: inherit;}
.changed-before {background: rgba(239, 68, 68, .17);}
.changed-after {background: rgba(34, 197, 94, .20);}
.changed-before .review-marker {color: #c53030;}
.changed-after .review-marker {color: #16803c;}
.review-empty {padding: 8px 16px; opacity: .65;}
</style>
""" + '<div class="review-code" tabindex="0" aria-label="' + (
        "Current code; minus marks removed or replaced lines" if side == "before"
        else "Suggested code; plus marks added or changed lines"
    ) + '"><div class="review-lines">' + "".join(rows) + "</div></div>"
