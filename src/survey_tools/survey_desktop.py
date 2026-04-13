"""
survey_desktop.py  —  Desktop Survey Tool for Word Documents
=============================================================
Run directly:
    python survey_desktop.py
    python survey_desktop.py --docx path/to/file.docx

A native desktop window opens immediately.  No browser, no server.

Workflow:
  1. Pick a .docx questionnaire file (or pass --docx on the CLI).
  2. Navigate sections using the left-side tree.
  3. Fill in each leaf section (text fields + multi-select checkboxes).
  4. Click "Save as HTML" on the Summary page — a formatted HTML report
     is written to disk and the save path is shown in a dialog.

Requirements:
    pip install python-docx
    tkinter  — ships with the standard Python installer on Windows and macOS.
               Linux:  sudo apt install python3-tk   (Debian/Ubuntu)
                       sudo dnf install python3-tkinter  (Fedora/RHEL)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# ── python-docx ──────────────────────────────────────────────────────────────
try:
    from docx import Document
    from docx.text.paragraph import Paragraph as DocxPara
    from docx.table import Table as DocxTable
except ImportError:
    sys.exit(
        "python-docx is not installed.\n"
        "Run:  pip install python-docx\n"
    )

# ── tkinter ───────────────────────────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    sys.exit(
        "tkinter is not available.\n"
        "Windows / macOS: reinstall Python from python.org (include Tcl/Tk).\n"
        "Ubuntu / Debian: sudo apt install python3-tk\n"
        "Fedora / RHEL:   sudo dnf install python3-tkinter\n"
    )


# =============================================================================
# Colour palette & fonts  (easy to customise)
# =============================================================================
C = {
    "bg":           "#F7F8FA",   # window background
    "sidebar_bg":   "#FFFFFF",   # sidebar background
    "sidebar_sel":  "#EEF2FF",   # selected nav item background
    "sidebar_txt":  "#374151",   # normal nav text
    "accent":       "#4F46E5",   # indigo accent (buttons, active items)
    "accent_lt":    "#EEF2FF",   # light accent fill
    "btn_fg":       "#FFFFFF",   # primary button text
    "btn_sec_bg":   "#F3F4F6",   # secondary button background
    "btn_sec_fg":   "#374151",   # secondary button text
    "card_bg":      "#FFFFFF",   # card / panel background
    "border":       "#E5E7EB",   # subtle border
    "text_primary": "#111827",   # main text
    "text_muted":   "#6B7280",   # secondary / hint text
    "green":        "#10B981",   # done status
    "green_lt":     "#D1FAE5",   # done badge fill
    "red":          "#EF4444",   # error
    "progress_bg":  "#E5E7EB",   # progress bar trough
    "progress_fg":  "#4F46E5",   # progress bar fill
    "check_on":     "#4F46E5",   # checkbox selected border
    "check_on_bg":  "#EEF2FF",   # checkbox selected fill
    "divider":      "#F3F4F6",   # divider lines inside forms
}

FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else (
    "SF Pro Display" if sys.platform == "darwin" else "DejaVu Sans"
)
FONT        = (FONT_FAMILY, 10)
FONT_BOLD   = (FONT_FAMILY, 10, "bold")
FONT_SMALL  = (FONT_FAMILY, 9)
FONT_TITLE  = (FONT_FAMILY, 15, "bold")
FONT_H2     = (FONT_FAMILY, 12, "bold")
FONT_CODE   = ("Courier New" if sys.platform == "win32" else "Courier", 9)


# =============================================================================
# Document parser
# =============================================================================
HEADING_STYLES = {
    "Heading 1": 1, "Heading 2": 2, "Heading 3": 3,
    "Heading 4": 4, "Heading 5": 5,
}
CHECKBOX_RE = re.compile(r"☐\s*|□\s*|\[\s*\]\s*")


class Node:
    """One node in the heading hierarchy of the parsed .docx file."""

    def __init__(self, level: int, title: str, parent: "Node | None" = None):
        self.level   = level
        self.title   = title
        self.parent  = parent
        self.children: list[Node]      = []
        self.fields:   list[FormField] = []

    # ------------------------------------------------------------------
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def breadcrumb(self) -> str:
        """Full path string used as a unique key, e.g. '1. Intro > 1.1 Auth'."""
        parts, node = [], self
        while node and node.level > 0:
            parts.append(node.title)
            node = node.parent
        return " > ".join(reversed(parts))

    def all_leaves(self) -> list["Node"]:
        """Return every leaf node in document order under this subtree."""
        if self.is_leaf():
            return [self]
        result = []
        for child in self.children:
            result.extend(child.all_leaves())
        return result


class FormField:
    """One answerable item (text input, multi-select checkboxes, or API table)."""

    def __init__(
        self,
        ftype: str,
        label: str,
        options: list[str] | None = None,
        rows: list[str] | None = None,
        hints: dict | None = None,
        hint: str = "",
    ):
        self.ftype   = ftype   # "text" | "checkbox" | "table_row" | "api_table"
        self.label   = label
        self.options = options or []   # checkbox options OR api_table column names
        self.rows    = rows    or []   # api_table row labels
        self.hints   = hints   or {}   # api_table pre-filled cell text used as placeholders
                                       # {row_label: {col_name: original_cell_text}}
        self.hint    = hint    or ""   # single-value placeholder (table_row / text fields)


def _extract_checkboxes(text: str) -> list[str]:
    """Split on checkbox markers and return option labels."""
    if not CHECKBOX_RE.search(text):
        return []
    return [p.strip() for p in CHECKBOX_RE.split(text) if p.strip()]


def parse_document(docx_path: str) -> Node:
    """
    Walk every paragraph and table in the .docx, build a Node tree.
    Returns the invisible root (level 0).
    """
    doc   = Document(docx_path)
    root  = Node(level=0, title="ROOT")
    stack: list[Node] = [root]

    def cur() -> Node:
        return stack[-1]

    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

        if tag == "p":
            para  = DocxPara(block, doc)
            sname = para.style.name if para.style else ""
            level = HEADING_STYLES.get(sname, 0)
            raw = "".join(r.text for r in para.runs)
            # Strip invisible characters (NBSP, zero-width, BOM, …) then whitespace
            raw = re.sub(r'[\u00a0\u200b\u200c\u200d\ufeff\u2028\u2029]+', ' ', raw).strip()
            if not raw:
                continue

            if level:
                while len(stack) > 1 and stack[-1].level >= level:
                    stack.pop()
                node = Node(level=level, title=raw.strip("*_ "), parent=stack[-1])
                stack[-1].children.append(node)
                stack.append(node)
            else:
                parent = cur()
                cbs = _extract_checkboxes(raw)
                if cbs:
                    if parent.fields and parent.fields[-1].ftype == "checkbox":
                        parent.fields[-1].options.extend(cbs)
                    else:
                        parent.fields.append(
                            FormField("checkbox", "Select all that apply", cbs)
                        )
                elif len(raw) > 5 and not raw.startswith("*Note*"):
                    parent.fields.append(FormField("text", raw))

        elif tag == "tbl":
            tbl    = DocxTable(block, doc)
            parent = cur()
            n_cols = len(tbl.columns)

            def _fallback_rows(rows_cells: list[list[str]], skip_first: bool) -> None:
                """Original row-by-row field creation used as a fall-back."""
                for i, cells in enumerate(rows_cells):
                    if not any(cells):
                        continue
                    if i == 0 and skip_first:
                        continue
                    label = cells[0] if cells[0] else f"Row {i+1}"
                    if len(label) < 3:
                        continue
                    second = cells[1] if len(cells) > 1 else ""
                    cbs = _extract_checkboxes(second)
                    if cbs:
                        parent.fields.append(FormField("checkbox", label, cbs))
                    else:
                        # Store the docx second-column text as the placeholder hint
                        parent.fields.append(FormField("table_row", label,
                                                        hint=second.strip()))

            if n_cols >= 3:
                # ── Structured multi-column table (e.g. API endpoints) ────
                all_rows = [
                    [c.text.strip() for c in row.cells]
                    for row in tbl.rows
                ]
                if not all_rows:
                    continue

                hdr = all_rows[0]
                # Treat the first row as a column-header when EITHER:
                #   a) every cell is ALL-CAPS or empty (e.g. "API METHOD")
                #   b) the first (row-label) cell is blank but the rest have
                #      content (pivot-table style, e.g. "Applies to Your System?")
                all_caps         = all(c == c.upper() or not c for c in hdr)
                pivot_style      = (not hdr[0]) and any(c for c in hdr[1:])
                is_hdr           = all_caps or pivot_style

                # Always read column names from the first row so they are never
                # replaced with generic "Col N" labels.
                col_names = [c for c in hdr[1:] if c] or \
                            [f"Col {i+1}" for i in range(n_cols - 1)]
                data_rows = all_rows[1:] if is_hdr else all_rows

                row_labels = [
                    r[0].strip() for r in data_rows
                    if r and r[0].strip() and len(r[0].strip()) >= 2
                ]

                if row_labels:
                    # Collect pre-existing cell text as placeholder hints
                    hints: dict = {}
                    for r in data_rows:
                        rl = r[0].strip() if r else ""
                        if rl not in row_labels:
                            continue
                        row_hints: dict = {}
                        for ci, cn in enumerate(col_names):
                            cell_text = r[ci + 1].strip() if ci + 1 < len(r) else ""
                            if cell_text:
                                row_hints[cn] = cell_text
                        if row_hints:
                            hints[rl] = row_hints
                    parent.fields.append(
                        FormField("api_table", "|".join(row_labels),
                                  options=col_names, rows=row_labels, hints=hints)
                    )
                else:
                    # Can't build a labelled table → fall back to row-by-row
                    _fallback_rows(all_rows, skip_first=is_hdr)
            else:
                # ── Original 1-2 column table handling ────────────────────
                all_rows = [
                    [c.text.strip() for c in row.cells]
                    for row in tbl.rows
                ]
                is_hdr = bool(all_rows) and all(
                    c == c.upper() or not c for c in all_rows[0]
                )
                _fallback_rows(all_rows, skip_first=is_hdr)

    return root


# =============================================================================
# HTML export
# =============================================================================

def build_html_report(
    docx_name: str,
    responses: dict[str, dict[str, object]],
    total_leaves: int,
) -> str:
    """
    Generate a self-contained, styled HTML report from all collected answers.
    Returns the full HTML string.
    """
    def _has_any(fields: dict) -> bool:
        for v in fields.values():
            if isinstance(v, list) and v:
                return True
            if isinstance(v, str) and v.strip():
                return True
            if isinstance(v, dict):
                for rv in v.values():
                    if isinstance(rv, dict) and any(
                        cv.strip() for cv in rv.values() if isinstance(cv, str)
                    ):
                        return True
        return False

    done_count = sum(1 for fields in responses.values() if _has_any(fields))
    pct = int(done_count / total_leaves * 100) if total_leaves else 0

    def _api_table_html(tbl_data: dict) -> str:
        """Render a {row_label: {col: value}} dict as an HTML table."""
        if not tbl_data:
            return "<em>—</em>"
        cols: list[str] = []
        for rv in tbl_data.values():
            if isinstance(rv, dict):
                for c in rv:
                    if c not in cols:
                        cols.append(c)
        if not cols:
            return "<em>—</em>"
        hdr = "".join(f"<th>{_he(c)}</th>" for c in cols)
        body = ""
        for rlbl, rv in tbl_data.items():
            cells = "".join(
                f'<td>{_he(rv.get(c,"") or "") if isinstance(rv,dict) else ""}</td>'
                for c in cols
            )
            body += f'<tr><td class="api-lbl">{_he(rlbl)}</td>{cells}</tr>'
        return (
            f'<table class="api-tbl">'
            f'<thead><tr><th></th>{hdr}</tr></thead>'
            f'<tbody>{body}</tbody>'
            f'</table>'
        )

    def row_html(label: str, value: object) -> str:
        if isinstance(value, list):
            display = ", ".join(value) if value else "<em>—</em>"
        elif isinstance(value, dict):
            display = _api_table_html(value)
        else:
            display = _he(value).replace("\n", "<br>") if value and value.strip() else "<em>—</em>"
        return (
            f'<tr><td class="key">{_he(label)}</td>'
            f'<td class="val">{display}</td></tr>\n'
        )

    sections_html = ""
    for section, fields in responses.items():
        rows = "".join(row_html(k, v) for k, v in fields.items())
        sections_html += f"""
        <div class="card">
          <div class="card-header">{_he(section)}</div>
          <table class="data-table">{rows}</table>
        </div>
        """

    now = datetime.now().strftime("%Y-%m-%d  %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Survey Results — {_he(docx_name)}</title>
<style>
  /* ── reset & base ── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    font-size: 14px; line-height: 1.6;
    background: #F0F2F5; color: #111827; min-height: 100vh;
  }}

  /* ── header ── */
  .page-header {{
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
    color: #fff; padding: 36px 48px 28px;
  }}
  .page-header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 6px; }}
  .page-header .meta {{ font-size: 13px; opacity: .8; }}

  /* ── progress bar ── */
  .progress-wrap {{
    background: rgba(255,255,255,.25); border-radius: 99px;
    height: 10px; margin: 18px 0 6px; overflow: hidden;
  }}
  .progress-bar {{
    height: 10px; border-radius: 99px;
    background: #fff;
    width: {pct}%;
    transition: width .6s ease;
  }}
  .progress-label {{ font-size: 12px; opacity: .85; }}

  /* ── stats row ── */
  .stats {{
    display: flex; gap: 16px; padding: 20px 48px;
    background: #fff; border-bottom: 1px solid #E5E7EB;
    flex-wrap: wrap;
  }}
  .stat {{
    background: #F9FAFB; border: 1px solid #E5E7EB;
    border-radius: 10px; padding: 12px 20px; min-width: 140px;
  }}
  .stat-num {{ font-size: 26px; font-weight: 700; color: #4F46E5; }}
  .stat-label {{ font-size: 12px; color: #6B7280; margin-top: 2px; }}

  /* ── main content ── */
  .content {{ max-width: 900px; margin: 28px auto; padding: 0 24px 60px; }}

  /* ── cards ── */
  .card {{
    background: #fff; border: 1px solid #E5E7EB;
    border-radius: 12px; margin-bottom: 18px; overflow: hidden;
  }}
  .card-header {{
    background: #F9FAFB; border-bottom: 1px solid #E5E7EB;
    padding: 12px 20px; font-weight: 600; font-size: 13px;
    color: #374151; letter-spacing: .01em;
  }}

  /* ── data table inside cards ── */
  .data-table {{ width: 100%; border-collapse: collapse; }}
  .data-table tr:not(:last-child) td {{
    border-bottom: 1px solid #F3F4F6;
  }}
  .data-table td {{ padding: 9px 20px; vertical-align: top; }}
  .data-table td.key {{
    width: 38%; color: #6B7280; font-size: 13px;
    padding-right: 12px; font-weight: 500;
  }}
  .data-table td.val {{ font-size: 13px; color: #111827; }}
  .data-table td.val em {{ color: #D1D5DB; font-style: normal; }}

  /* ── nested API table (inside a .val cell) ── */
  .api-tbl {{
    width: 100%; border-collapse: collapse;
    font-size: 12px; margin: 2px 0;
  }}
  .api-tbl thead tr {{ background: #EEF2FF; }}
  .api-tbl thead th {{
    padding: 6px 10px; text-align: left;
    color: #4338CA; font-weight: 600;
    border: 1px solid #E0E7FF;
  }}
  .api-tbl tbody tr:nth-child(even) {{ background: #F9FAFB; }}
  .api-tbl tbody tr:nth-child(odd)  {{ background: #FFFFFF; }}
  .api-tbl tbody td {{
    padding: 6px 10px; vertical-align: top;
    border: 1px solid #F3F4F6; color: #111827;
    white-space: pre-wrap;
  }}
  .api-tbl td.api-lbl {{
    font-weight: 600; color: #374151;
    background: #F3F4F6; white-space: nowrap;
  }}

  /* ── footer ── */
  .footer {{
    text-align: center; font-size: 12px;
    color: #9CA3AF; padding: 24px;
    border-top: 1px solid #E5E7EB; margin-top: 40px;
  }}

  @media(max-width:600px){{
    .page-header{{ padding: 24px 20px 20px; }}
    .stats{{ padding: 16px 20px; }}
    .content{{ padding: 0 12px 40px; }}
    .data-table td.key{{ width: 45%; }}
  }}
</style>
</head>
<body>

<div class="page-header">
  <h1>{_he(docx_name)}</h1>
  <div class="meta">Generated {now} &nbsp;·&nbsp; {done_count} of {total_leaves} sections answered</div>
  <div class="progress-wrap">
    <div class="progress-bar"></div>
  </div>
  <div class="progress-label">{pct}% complete</div>
</div>

<div class="stats">
  <div class="stat">
    <div class="stat-num">{total_leaves}</div>
    <div class="stat-label">total sections</div>
  </div>
  <div class="stat">
    <div class="stat-num">{done_count}</div>
    <div class="stat-label">sections answered</div>
  </div>
  <div class="stat">
    <div class="stat-num">{pct}%</div>
    <div class="stat-label">completion</div>
  </div>
</div>

<div class="content">
  {sections_html if sections_html else '<p style="color:#9CA3AF;padding:24px 0">No answers recorded yet.</p>'}
</div>

<div class="footer">
  Survey report &nbsp;·&nbsp; {_he(docx_name)} &nbsp;·&nbsp; {now}
</div>

</body>
</html>
"""


def _he(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# =============================================================================
# GUI — helper widgets
# =============================================================================

# ── Gradient-button paint helpers ────────────────────────────────────────────

def _lerp_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two #rrggbb hex colours (t in 0..1)."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return (f"#{int(r1 + (r2-r1)*t):02x}"
            f"{int(g1 + (g2-g1)*t):02x}"
            f"{int(b1 + (b2-b1)*t):02x}")


# Visual state tokens → colour recipe
_NAV_STATES: dict[str, dict] = {
    "off": dict(
        c_top="#FFFFFF", c_bot="#F0F2FF",
        border="#D1D5DB",
        text="#374151",
        badge_bg="#E5E7EB", badge_fg="#6B7280",
    ),
    "hover": dict(
        c_top="#EEF2FF", c_bot="#DDE4FF",
        border="#6366F1",
        text="#4338CA",
        badge_bg="#C7D2FE", badge_fg="#4338CA",
    ),
    "on": dict(
        c_top="#818CF8", c_bot="#4338CA",
        border="#4338CA",
        text="#FFFFFF",
        badge_bg="#4338CA", badge_fg="#FFFFFF",
    ),
}


def _is_yesno_col(col_name: str) -> bool:
    """True when a table column expects a Yes/No answer."""
    lo = col_name.lower()
    return (
        col_name.rstrip().endswith("?")
        or any(k in lo for k in ("applies", "applicable", "supported",
                                  "available", "yes/no", "y/n", "support",
                                  "applicable to"))
    )


def _paint_nav_canvas(
    canvas: "tk.Canvas",
    label: str,
    badge_text: str,
    badge_done: bool,
    state: str,
) -> None:
    """Repaint a Canvas-based nav button.  state ∈ {'off', 'hover', 'on'}."""
    canvas.delete("all")
    W = canvas.winfo_width()
    H = canvas.winfo_height()
    if W < 8 or H < 8:
        return

    s  = _NAV_STATES[state]
    r  = 10   # corner radius (px)

    # ── gradient background clipped to rounded rect ──────────────────────
    for y in range(H):
        t     = y / max(H - 1, 1)
        color = _lerp_color(s["c_top"], s["c_bot"], t)
        xc    = 0
        if y < r:
            dy = r - y
            xc = r - int(math.sqrt(max(0.0, r * r - dy * dy)))
        elif y >= H - r:
            dy = r - (H - 1 - y)
            xc = r - int(math.sqrt(max(0.0, r * r - dy * dy)))
        x1, x2 = xc, W - xc
        if x2 > x1:
            canvas.create_line(x1, y, x2, y, fill=color)

    # ── top-edge shine on active button ──────────────────────────────────
    if state == "on":
        shine = _lerp_color(s["c_top"], "#FFFFFF", 0.35)
        canvas.create_line(r, 1, W - r, 1, fill=shine, width=1)

    # ── rounded outline (smooth polygon) ─────────────────────────────────
    pts = [r,0,  W-r,0,  W,0,  W,r,
           W,H-r, W,H,   W-r,H, r,H,
           0,H,   0,H-r,  0,r,  0,0]
    canvas.create_polygon(pts, smooth=True, fill="", outline=s["border"], width=1)

    # ── badge ─────────────────────────────────────────────────────────────
    text_right = W - 10
    if badge_text:
        if badge_done:
            bbg, bfg = C["green"], "#FFFFFF"
        else:
            bbg, bfg = s["badge_bg"], s["badge_fg"]
        bpad = 6
        bh   = 16
        bw   = max(len(badge_text) * 6 + bpad * 2, 24)
        bx2  = W - 10
        bx1  = bx2 - bw
        by1  = (H - bh) // 2
        by2  = by1 + bh
        br   = bh // 2
        bpts = [bx1+br,by1, bx2-br,by1, bx2,by1, bx2,by1+br,
                bx2,by2-br, bx2,by2,    bx2-br,by2, bx1+br,by2,
                bx1,by2,    bx1,by2-br, bx1,by1+br, bx1,by1]
        canvas.create_polygon(bpts, smooth=True, fill=bbg, outline="")
        canvas.create_text((bx1+bx2)//2, H//2,
                           text=badge_text, fill=bfg,
                           font=(FONT_FAMILY, 8, "bold"))
        text_right = bx1 - 8

    # ── label text ────────────────────────────────────────────────────────
    avail = max(text_right - 16, 10)
    canvas.create_text(14, H // 2,
                       text=label, fill=s["text"],
                       font=FONT, anchor="w", width=avail)


class ScrollableFrame(tk.Frame):
    """
    A frame that can scroll vertically.
    The scrollbar is hidden when all content fits and appears automatically
    when content overflows.  Attach child widgets to .inner_frame.
    """

    def __init__(self, parent, bg: str = C["bg"], **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self._scroll = ttk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview
        )
        self.inner_frame = tk.Frame(self._canvas, bg=bg)

        self._canvas.configure(yscrollcommand=self._set_scrollbar)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        # scrollbar starts hidden; shown dynamically via _set_scrollbar

        self._win_id = self._canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw"
        )

        self.inner_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # Mouse-wheel bindings are handled at the app level (_dispatch_scroll)
        # to avoid multiple ScrollableFrame instances fighting over bind_all.

    def _set_scrollbar(self, first, last):
        """Show the scrollbar only when content doesn't fully fit."""
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._scroll.grid_remove()
        else:
            self._scroll.grid(row=0, column=1, sticky="ns")
        self._scroll.set(first, last)

    def _on_frame_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def scroll_to_top(self):
        self._canvas.yview_moveto(0)


def make_button(
    parent,
    text: str,
    command,
    primary: bool = True,
    width: int = 0,
) -> tk.Label:
    """
    A flat, styled button implemented as a Label with click binding.
    Avoids the dated look of tk.Button.
    """
    bg = C["accent"] if primary else C["btn_sec_bg"]
    fg = C["btn_fg"] if primary else C["btn_sec_fg"]

    lbl = tk.Label(
        parent, text=text, bg=bg, fg=fg,
        font=FONT_BOLD, cursor="hand2",
        padx=16, pady=8, relief="flat",
    )
    if width:
        lbl.config(width=width)

    def _enter(_): lbl.config(bg="#4338CA" if primary else "#E5E7EB")
    def _leave(_): lbl.config(bg=bg)
    def _click(_): command()

    lbl.bind("<Enter>",   _enter)
    lbl.bind("<Leave>",   _leave)
    lbl.bind("<Button-1>", _click)
    return lbl


# =============================================================================
# GUI — Main application window
# =============================================================================

class SurveyApp(tk.Tk):
    """
    Main application window.

    Layout:
      ┌──────────────────────────────────────────┐
      │  Header bar (title + doc name)           │
      ├──────────────┬───────────────────────────┤
      │              │                           │
      │  Sidebar     │   Content area            │
      │  (nav tree)  │   (changes per section)   │
      │              │                           │
      └──────────────┴───────────────────────────┘
      │  Status bar + progress                   │
      └──────────────────────────────────────────┘
    """

    def __init__(self, preload_docx: str | None = None):
        super().__init__()
        self.title("Controler Discovery Data Collection")
        self.geometry("1100x720")
        self.minsize(800, 560)
        self.configure(bg=C["bg"])
        self.state("zoomed")   # start maximised (Windows; ignored on other OS)

        # ── Application state ──────────────────────────────────────────────
        self.root_node:    Node | None = None
        self.docx_path:    str         = ""
        self.responses:    dict        = {}   # {breadcrumb: {label: value}}
        self.all_leaves:   list[Node]  = []   # ordered leaf nodes
        self._nav_items:   list[dict]  = []   # sidebar item descriptors
        self._current_id:  str | None  = None # breadcrumb of current section

        # tkinter variables for the active form (rebuilt each section)
        self._field_vars:  list        = []

        self._build_ui()
        self._configure_styles()

        if preload_docx:
            self.after(100, lambda: self._load_docx(preload_docx))
        else:
            self.after(100, self._show_welcome)

    # ── UI construction ────────────────────────────────────────────────────

    def _dispatch_scroll(self, event):
        """Route mouse-wheel events to whichever ScrollableFrame is under the cursor."""
        widget = event.widget
        while widget is not None:
            if isinstance(widget, ScrollableFrame):
                widget._on_mousewheel(event)
                return
            widget = getattr(widget, "master", None)

    def _configure_styles(self):
        """Set up ttk styles used by the progress bar and scrollbar."""
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Survey.Horizontal.TProgressbar",
            troughcolor=C["progress_bg"],
            background=C["progress_fg"],
            borderwidth=0,
            thickness=6,
        )
        style.configure(
            "Vertical.TScrollbar",
            troughcolor=C["sidebar_bg"],
            background=C["border"],
        )

    def _build_ui(self):
        """Assemble all top-level frames and widgets."""

        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=C["accent"], height=54)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        _title_lbl = tk.Label(
            header, text="Third-Party System Data Collection",
            bg=C["accent"], fg="#FFFFFF",
            font=(FONT_FAMILY, 13, "bold"), padx=20, anchor="w", justify="left",
        )
        _title_lbl.pack(side="left", pady=10, fill="x", expand=True)

        def _update_title_wrap(_=None):
            avail = header.winfo_width() - 160  # leave room for the Open button
            if avail > 50:
                _title_lbl.config(wraplength=avail)

        header.bind("<Configure>", _update_title_wrap)

        # Open file button in header
        open_btn = tk.Label(
            header, text="  Open file  ", bg="#6366F1", fg="#FFFFFF",
            font=FONT_SMALL, cursor="hand2", padx=4, pady=5,
        )
        open_btn.pack(side="right", padx=16, pady=10)
        open_btn.bind("<Button-1>", lambda _: self._browse_docx())
        open_btn.bind("<Enter>", lambda _: open_btn.config(bg="#4338CA"))
        open_btn.bind("<Leave>", lambda _: open_btn.config(bg="#6366F1"))

        # ── Body (sidebar + content) ──────────────────────────────────────
        body = tk.Frame(self, bg=C["bg"])
        body.pack(side="top", fill="both", expand=True)

        # Sidebar
        self._sidebar = tk.Frame(body, bg=C["sidebar_bg"], width=320)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # Thin border between sidebar and content
        tk.Frame(body, bg=C["border"], width=1).pack(side="left", fill="y")

        # Content area (scrollable)
        self._content_scroll = ScrollableFrame(body, bg=C["bg"])
        self._content_scroll.pack(side="left", fill="both", expand=True)
        self._content = self._content_scroll.inner_frame

        # Single app-level mouse-wheel dispatcher — walks the widget
        # hierarchy from the event source to find the nearest ScrollableFrame.
        self.bind_all("<MouseWheel>", self._dispatch_scroll)
        self.bind_all("<Button-4>",   self._dispatch_scroll)
        self.bind_all("<Button-5>",   self._dispatch_scroll)

        # ── Status bar ────────────────────────────────────────────────────
        status_bar = tk.Frame(self, bg=C["sidebar_bg"], height=36)
        status_bar.pack(side="bottom", fill="x")
        status_bar.pack_propagate(False)

        tk.Frame(status_bar, bg=C["border"], height=1).pack(
            side="top", fill="x"
        )

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            status_bar,
            variable=self._progress_var,
            maximum=100,
            style="Survey.Horizontal.TProgressbar",
            length=160,
        )
        self._progress_bar.pack(side="left", padx=(16, 8), pady=10)

        self._lbl_status = tk.Label(
            status_bar, text="Ready",
            bg=C["sidebar_bg"], fg=C["text_muted"], font=FONT_SMALL,
        )
        self._lbl_status.pack(side="left")

        self._lbl_pct = tk.Label(
            status_bar, text="0%",
            bg=C["sidebar_bg"], fg=C["accent"], font=FONT_BOLD,
        )
        self._lbl_pct.pack(side="right", padx=16)

    # ── Document loading ───────────────────────────────────────────────────

    def _browse_docx(self):
        path = filedialog.askopenfilename(
            title="Select a .docx questionnaire",
            filetypes=[("Word Documents", "*.docx"), ("All files", "*.*")],
        )
        if path:
            self._load_docx(path)

    def _load_docx(self, path: str):
        """Parse the document and reset the application state."""
        try:
            root = parse_document(path)
        except Exception as exc:
            messagebox.showerror("Parse error", str(exc))
            return

        self.root_node   = root
        self.docx_path   = path
        self.responses   = {}
        self.all_leaves  = root.all_leaves()
        self._current_id = None

        # filename no longer shown in the header
        self._set_status(f"Loaded {len(self.all_leaves)} sections", 0)
        self._build_sidebar()
        self._show_home()

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        """Rebuild the navigation sidebar — top-level chapters only."""
        for w in self._sidebar.winfo_children():
            w.destroy()
        self._nav_items = []

        # Header label
        tk.Label(
            self._sidebar, text="Sections",
            bg=C["sidebar_bg"], fg=C["text_muted"],
            font=FONT_SMALL, anchor="w", padx=16, pady=10,
        ).pack(fill="x")
        tk.Frame(self._sidebar, bg=C["border"], height=1).pack(fill="x")

        # Scrollable list of chapter buttons
        nav_scroll = ScrollableFrame(self._sidebar, bg=C["sidebar_bg"])
        nav_scroll.pack(fill="both", expand=True)
        nav_frame = nav_scroll.inner_frame

        # Home button
        self._add_nav_btn(nav_frame, "__home__", "Home", self._show_home)

        # One button per top-level chapter
        if self.root_node:
            for node in self.root_node.children:
                nid = node.breadcrumb()
                click = (
                    (lambda nid: lambda: self._navigate_to(nid))(nid)
                    if node.is_leaf()
                    else (lambda n: lambda: self._show_branch(n))(node)
                )
                self._add_nav_btn(nav_frame, nid, node.title, click, node=node)

        # Divider + Summary & Save at bottom of scroll area
        tk.Frame(nav_frame, bg=C["border"], height=1).pack(
            fill="x", padx=12, pady=(8, 0)
        )
        self._add_nav_btn(
            nav_frame, "__summary__", "Summary & Save", self._show_summary
        )

    def _get_badge(self, node: "Node | None") -> tuple[str, bool]:
        """Return (badge_text, all_done) for a chapter node."""
        if not node:
            return "", False
        leaves = node.all_leaves()
        total  = len(leaves)
        if total == 0:
            return "", False
        done     = sum(1 for lf in leaves if self._is_section_done(lf.breadcrumb()))
        all_done = done == total
        return ("✓" if all_done else f"{done}/{total}"), all_done

    def _add_nav_btn(
        self,
        parent,
        node_id: str,
        label: str,
        on_click,
        node: "Node | None" = None,
    ):
        """Add a full-width gradient rounded-rect button to the sidebar."""
        is_on = (node_id == self._current_id)

        # Item dict created first so the <Configure> closure can reference it
        item: dict = {
            "id":    node_id,
            "label": label,
            "node":  node,
            "state": "on" if is_on else "off",
            "canvas": None,
        }
        self._nav_items.append(item)

        outer = tk.Frame(parent, bg=C["sidebar_bg"])
        outer.pack(fill="x", padx=8, pady=3)

        canvas = tk.Canvas(
            outer, height=50, bg=C["sidebar_bg"],
            highlightthickness=0, cursor="hand2",
        )
        canvas.pack(fill="x")
        item["canvas"] = canvas

        def _repaint(_=None):
            btxt, bdone = self._get_badge(item["node"])
            _paint_nav_canvas(canvas, item["label"], btxt, bdone, item["state"])

        # Repaint on resize (also fires on first layout)
        canvas.bind("<Configure>", _repaint)
        # Backup in case <Configure> fires before geometry is resolved
        canvas.after(30, _repaint)

        def _hover_on(_):
            if item["state"] != "on":
                btxt, bdone = self._get_badge(node)
                _paint_nav_canvas(canvas, label, btxt, bdone, "hover")

        def _hover_off(_):
            if item["state"] != "on":
                btxt, bdone = self._get_badge(node)
                _paint_nav_canvas(canvas, label, btxt, bdone, item["state"])

        def _click(_): on_click()

        canvas.bind("<Enter>",    _hover_on)
        canvas.bind("<Leave>",    _hover_off)
        canvas.bind("<Button-1>", _click)

    def _is_ancestor_active(self, node_id: str) -> bool:
        """True if the current view is a descendant of this sidebar button."""
        if not self._current_id or node_id in ("__home__", "__summary__"):
            return False
        return self._current_id.startswith(node_id + " > ")

    def _refresh_nav(self):
        """Update gradient button states in the sidebar without full rebuild."""
        for item in self._nav_items:
            nid   = item["id"]
            is_on = (nid == self._current_id) or self._is_ancestor_active(nid)
            item["state"] = "on" if is_on else "off"
            canvas = item.get("canvas")
            if canvas:
                btxt, bdone = self._get_badge(item["node"])
                _paint_nav_canvas(canvas, item["label"], btxt, bdone, item["state"])

    def _is_section_done(self, section_id: str) -> bool:
        """Return True if any non-empty answer was recorded for this section."""
        data = self.responses.get(section_id, {})
        for v in data.values():
            if isinstance(v, list) and v:
                return True
            if isinstance(v, str) and v.strip():
                return True
            if isinstance(v, dict):
                # api_table: {row_label: {col: value}}
                for row_val in v.values():
                    if isinstance(row_val, dict):
                        if any(cv.strip() for cv in row_val.values()
                               if isinstance(cv, str)):
                            return True
        return False

    # ── Progress ───────────────────────────────────────────────────────────

    def _update_progress(self):
        total = len(self.all_leaves)
        done  = sum(1 for n in self.all_leaves if self._is_section_done(n.breadcrumb()))
        pct   = int(done / total * 100) if total else 0
        self._progress_var.set(pct)
        self._lbl_pct.config(text=f"{pct}%")

    def _set_status(self, msg: str, pct: float | None = None):
        self._lbl_status.config(text=msg)
        if pct is not None:
            self._progress_var.set(pct)
            self._lbl_pct.config(text=f"{int(pct)}%")

    # ── Content area helpers ───────────────────────────────────────────────

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()
        self._field_vars = []
        self._content_scroll.scroll_to_top()

    def _pad_frame(self, padx=36, pady=28) -> tk.Frame:
        """Return a padded container frame inside the content area."""
        f = tk.Frame(self._content, bg=C["bg"])
        f.pack(fill="both", expand=True, padx=padx, pady=pady)
        return f

    def _section_header(self, parent, title: str, breadcrumb: str):
        tk.Label(
            parent, text=title, bg=C["bg"],
            fg=C["text_primary"], font=FONT_TITLE, anchor="w",
            wraplength=680,
        ).pack(fill="x", pady=(0, 4))
        tk.Label(
            parent, text=breadcrumb, bg=C["bg"],
            fg=C["text_muted"], font=FONT_SMALL, anchor="w",
        ).pack(fill="x")
        tk.Frame(parent, bg=C["border"], height=1).pack(
            fill="x", pady=(14, 0)
        )

    # ── Welcome / home screen ──────────────────────────────────────────────

    def _show_welcome(self):
        """Shown at startup when no document is loaded."""
        self._clear_content()
        self._current_id = None

        pad = self._pad_frame()

        tk.Label(
            pad,
            text="Welcome to Third-Party System Data Collection",
            bg=C["bg"], fg=C["text_primary"], font=FONT_TITLE,
        ).pack(pady=(40, 12))

        tk.Label(
            pad,
            text=(
                "Load a Word (.docx) questionnaire to begin.\n"
                "The app will parse its heading structure into a step-by-step survey."
            ),
            bg=C["bg"], fg=C["text_muted"], font=FONT,
            justify="center",
        ).pack(pady=(0, 28))

        make_button(pad, "  Open .docx file  ", self._browse_docx).pack()

    def _show_home(self):
        """Home / overview screen after a document is loaded."""
        self._clear_content()
        self._current_id = "__home__"
        self._refresh_nav()

        if not self.root_node:
            self._show_welcome()
            return

        pad = self._pad_frame(padx=36, pady=0)

        # ── Categorise intro paragraphs ──────────────────────────────────
        intro_fields = [f for f in self.root_node.fields if f.ftype == "text"]
        hero_fields, body_fields, note_fields = [], [], []
        for f in intro_fields:
            first = f.label[0] if f.label else ""
            if first and ord(first) > 127 and not first.isalpha() and not first.isdigit():
                note_fields.append(f)          # ⚡ ☆ ★ …  → amber note box
            elif len(f.label) <= 90:
                hero_fields.append(f)          # short → hero title / subtitle
            else:
                body_fields.append(f)          # long  → body card

        # ── Hero banner ──────────────────────────────────────────────────
        HERO_BG  = C["accent"]
        HERO_FG  = "#FFFFFF"
        HERO_SUB = "#C7D2FE"

        hero = tk.Frame(pad, bg=HERO_BG)
        hero.pack(fill="x", pady=(28, 16))
        # Top highlight stripe
        tk.Frame(hero, bg="#818CF8", height=3).pack(fill="x")

        hero_row = tk.Frame(hero, bg=HERO_BG)
        hero_row.pack(fill="x")

        # Left: title + subtitle
        left_col = tk.Frame(hero_row, bg=HERO_BG)
        left_col.pack(side="left", fill="both", expand=True, padx=28, pady=22)

        title_txt = hero_fields[0].label if hero_fields else os.path.basename(self.docx_path)
        title_lbl = tk.Label(
            left_col, text=title_txt,
            bg=HERO_BG, fg=HERO_FG,
            font=(FONT_FAMILY, 15, "bold"),
            anchor="w", justify="left", wraplength=700,
        )
        title_lbl.pack(fill="x", pady=(0, 6))
        sub_lbls = []
        for sf in (hero_fields[1:] if hero_fields else []):
            lbl = tk.Label(
                left_col, text=sf.label,
                bg=HERO_BG, fg=HERO_SUB,
                font=FONT, anchor="w", justify="left", wraplength=700,
            )
            lbl.pack(fill="x", pady=(0, 2))
            sub_lbls.append(lbl)

        # Right: section-count badge
        right_col = tk.Frame(hero_row, bg=HERO_BG)
        right_col.pack(side="right", padx=28, pady=22)
        badge = tk.Frame(right_col, bg="#6366F1")
        badge.pack()
        tk.Label(
            badge,
            text=str(len(self.all_leaves)),
            bg="#6366F1", fg=HERO_FG,
            font=(FONT_FAMILY, 22, "bold"), padx=18, pady=10,
        ).pack()
        tk.Label(
            right_col, text="sections to complete",
            bg=HERO_BG, fg=HERO_SUB, font=FONT_SMALL,
        ).pack(pady=(6, 0))

        # Bottom accent stripe
        tk.Frame(hero, bg="#4338CA", height=2).pack(fill="x")

        # ── Body paragraphs ──────────────────────────────────────────────
        auto_wrap_labels: list[tk.Label] = [title_lbl] + sub_lbls
        if body_fields:
            body_card = tk.Frame(
                pad, bg=C["card_bg"],
                highlightthickness=1, highlightbackground=C["border"],
            )
            body_card.pack(fill="x", pady=(0, 10))
            for i, f in enumerate(body_fields):
                if i > 0:
                    tk.Frame(body_card, bg=C["divider"], height=1).pack(
                        fill="x", padx=20
                    )
                lbl = tk.Label(
                    body_card, text=f.label,
                    bg=C["card_bg"], fg=C["text_primary"],
                    font=FONT, anchor="w", justify="left",
                    wraplength=860, padx=24, pady=12,
                )
                lbl.pack(fill="x")
                auto_wrap_labels.append(lbl)

        # ── Note / highlight boxes (⚡ ☆ paragraphs) ─────────────────────
        for f in note_fields:
            note_outer = tk.Frame(pad, bg="#FDE68A")   # amber border
            note_outer.pack(fill="x", pady=(0, 8))
            note_inner = tk.Frame(note_outer, bg="#FFFBEB")
            note_inner.pack(fill="x", padx=1, pady=1)
            tk.Frame(note_inner, bg="#F59E0B", width=4).pack(
                side="left", fill="y"
            )
            lbl = tk.Label(
                note_inner, text=f.label,
                bg="#FFFBEB", fg="#78350F",
                font=FONT, anchor="w", justify="left",
                wraplength=860, padx=16, pady=10,
            )
            lbl.pack(side="left", fill="x", expand=True)
            auto_wrap_labels.append(lbl)

        # Auto-update wraplength on resize so text never clips
        def _on_resize(_, labels=auto_wrap_labels, p=pad):
            avail = p.winfo_width() - 100
            if avail > 100:
                for lb in labels:
                    lb.config(wraplength=avail)
        pad.bind("<Configure>", _on_resize)

        # ── Sections heading ─────────────────────────────────────────────
        tk.Label(
            pad, text="Sections",
            bg=C["bg"], fg=C["text_muted"],
            font=FONT_BOLD, anchor="w",
        ).pack(fill="x", pady=(8, 6))

        # Grid of top-level section cards
        grid = tk.Frame(pad, bg=C["bg"])
        grid.pack(fill="x", pady=(20, 0))

        for col_idx, node in enumerate(self.root_node.children):
            done_count = sum(
                1 for leaf in node.all_leaves()
                if self._is_section_done(leaf.breadcrumb())
            )
            total_here = len(node.all_leaves())

            card = tk.Frame(
                grid, bg=C["card_bg"],
                relief="flat", bd=1,
                highlightthickness=1,
                highlightbackground=C["border"],
            )
            card.grid(row=col_idx // 2, column=col_idx % 2,
                      padx=6, pady=6, sticky="ew")
            grid.columnconfigure(0, weight=1)
            grid.columnconfigure(1, weight=1)

            inner = tk.Frame(card, bg=C["card_bg"])
            inner.pack(fill="x", padx=14, pady=12)

            # Status badge
            badge_bg = C["green_lt"] if done_count == total_here else C["accent_lt"]
            badge_fg = "#065F46"    if done_count == total_here else C["accent"]
            badge_txt = "done" if done_count == total_here else f"{done_count}/{total_here}"
            tk.Label(
                inner, text=badge_txt,
                bg=badge_bg, fg=badge_fg,
                font=(FONT_FAMILY, 8, "bold"), padx=6, pady=2,
            ).pack(side="right", anchor="ne")

            # Title (clickable)
            title_short = node.title if len(node.title) <= 45 else node.title[:43] + "…"
            title_lbl = tk.Label(
                inner, text=title_short, bg=C["card_bg"],
                fg=C["text_primary"], font=FONT_BOLD, anchor="w",
                wraplength=240, justify="left",
            )
            title_lbl.pack(fill="x")

            sub = f"{total_here} leaf sections" if not node.is_leaf() else f"{len(node.fields)} fields"
            tk.Label(
                inner, text=sub, bg=C["card_bg"],
                fg=C["text_muted"], font=FONT_SMALL, anchor="w",
            ).pack(fill="x", pady=(3, 0))

            # Bind click
            def _make_click(n):
                return lambda _: (
                    self._navigate_to(n.breadcrumb())
                    if n.is_leaf()
                    else self._show_branch(n)
                )
            for w in (card, inner, title_lbl):
                w.bind("<Button-1>", _make_click(node))
                w.config(cursor="hand2")

    # ── Branch (non-leaf) screen ───────────────────────────────────────────

    def _show_branch(self, node: Node):
        self._clear_content()
        self._current_id = node.breadcrumb()
        self._refresh_nav()

        pad = self._pad_frame()
        self._section_header(pad, node.title, node.breadcrumb())

        for child in node.children:
            leaves = child.all_leaves()
            done_count = sum(
                1 for lf in leaves if self._is_section_done(lf.breadcrumb())
            )
            all_done = done_count == len(leaves)

            def _make_click(n):
                return lambda _: (
                    self._navigate_to(n.breadcrumb())
                    if n.is_leaf()
                    else self._show_branch(n)
                )

            # Button row
            btn = tk.Frame(
                pad, bg=C["card_bg"], cursor="hand2",
                highlightthickness=1,
                highlightbackground=C["green"] if all_done else C["border"],
            )
            btn.pack(fill="x", pady=3)

            inner = tk.Frame(btn, bg=C["card_bg"])
            inner.pack(fill="x", padx=16, pady=12)

            # Arrow / chevron on right
            arrow = tk.Label(
                inner,
                text="›" if not child.is_leaf() else "→",
                bg=C["card_bg"], fg=C["text_muted"],
                font=(FONT_FAMILY, 16),
            )
            arrow.pack(side="right", padx=(8, 0))

            # Progress or done badge
            if all_done:
                badge = tk.Label(
                    inner, text="done",
                    bg=C["green_lt"], fg="#065F46",
                    font=(FONT_FAMILY, 8, "bold"), padx=8, pady=2,
                )
            else:
                badge = tk.Label(
                    inner, text=f"{done_count}/{len(leaves)}",
                    bg=C["accent_lt"], fg=C["accent"],
                    font=(FONT_FAMILY, 8, "bold"), padx=8, pady=2,
                )
            badge.pack(side="right", padx=(0, 8))

            lbl = tk.Label(
                inner, text=child.title, bg=C["card_bg"],
                fg=C["text_primary"], font=FONT_BOLD, anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True)

            # Hover effects
            all_w = [btn, inner, lbl, arrow, badge]

            def _hover_on(_, b=btn, i=inner, l_=lbl, a=arrow, bg_=badge):
                b.config(highlightbackground=C["accent"])
                for w in (b, i, l_, a, bg_):
                    w.config(bg=C["accent_lt"])
                l_.config(fg=C["accent"])

            def _hover_off(_, b=btn, i=inner, l_=lbl, a=arrow, bg_=badge, done_=all_done):
                b.config(highlightbackground=C["green"] if done_ else C["border"])
                for w in (b, i, l_, a, bg_):
                    w.config(bg=C["card_bg"])
                l_.config(fg=C["text_primary"])

            for w in all_w:
                w.bind("<Button-1>", _make_click(child))
                w.bind("<Enter>",    _hover_on)
                w.bind("<Leave>",    _hover_off)

        # "Fill all" button
        btn_row = tk.Frame(pad, bg=C["bg"])
        btn_row.pack(fill="x", pady=(20, 0))
        leaves_here = node.all_leaves()
        if leaves_here:
            make_button(
                btn_row,
                "Fill all sub-sections in order",
                lambda: self._navigate_to(leaves_here[0].breadcrumb()),
            ).pack(side="left")

    # ── Leaf section form ──────────────────────────────────────────────────

    def _navigate_to(self, section_id: str):
        """Render the form for the leaf node identified by section_id."""
        node = self._find_node(section_id)
        if not node:
            return

        self._clear_content()
        self._current_id = section_id
        self._refresh_nav()

        saved = self.responses.get(section_id, {})

        # Determine prev / next leaves for navigation
        idx  = next((i for i, n in enumerate(self.all_leaves)
                     if n.breadcrumb() == section_id), -1)
        prev_id = self.all_leaves[idx - 1].breadcrumb() if idx > 0 else None
        next_id = (self.all_leaves[idx + 1].breadcrumb()
                   if idx < len(self.all_leaves) - 1 else None)

        pad = self._pad_frame()
        self._section_header(pad, node.title, node.breadcrumb())

        if not node.fields:
            tk.Label(
                pad, text="No input fields in this section.",
                bg=C["bg"], fg=C["text_muted"], font=FONT,
            ).pack(pady=20)
        else:
            self._build_form(pad, node, saved)

        # ── Navigation buttons ─────────────────────────────────────────
        btn_row = tk.Frame(pad, bg=C["bg"])
        btn_row.pack(fill="x", pady=(24, 0))

        def _save_and_go(next_dest):
            self._collect_and_save(section_id, node)
            if next_dest:
                self._navigate_to(next_dest)
            else:
                self._show_summary()

        make_button(
            btn_row,
            "Save & Next →" if next_id else "Save & Summary →",
            lambda nd=next_id: _save_and_go(nd),
        ).pack(side="left", padx=(0, 8))

        if prev_id:
            make_button(
                btn_row, "← Previous",
                lambda pid=prev_id: self._navigate_to(pid),
                primary=False,
            ).pack(side="left", padx=(0, 8))

        make_button(
            btn_row, "Home",
            self._show_home,
            primary=False,
        ).pack(side="left")

    def _build_form(self, parent: tk.Frame, node: Node, saved: dict):
        """
        Render all FormField widgets for a leaf node.
        Tk variables are stored in self._field_vars so we can read them
        back on save.
        """
        self._field_vars = []

        for field in node.fields:
            label_val = saved.get(field.label)

            # ── Section divider ──────────────────────────────────────────
            tk.Frame(parent, bg=C["divider"], height=1).pack(fill="x", pady=(14, 0))

            if field.ftype == "api_table":
                # Table gets its own header row; no extra label needed
                tbl_vars = self._build_api_table_field(parent, field, label_val)
                self._field_vars.append(("api_table", field.label, tbl_vars))
                continue

            # Field label
            lbl_text = textwrap.shorten(field.label, width=100, placeholder="…")
            tk.Label(
                parent, text=lbl_text, bg=C["bg"],
                fg=C["text_primary"], font=FONT_BOLD,
                anchor="w", wraplength=680, justify="left",
            ).pack(fill="x", pady=(10, 5))

            if field.ftype == "checkbox":
                var_list = self._build_checkbox_field(parent, field, label_val)
                self._field_vars.append(("checkbox", field.label, var_list))
            else:
                text_var = self._build_text_field(parent, field, label_val)
                self._field_vars.append(("text", field.label, text_var))

    def _build_text_field(
        self, parent: tk.Frame, field: FormField, saved_val
    ):
        """Render a single-line or multi-line text input and return a proxy with .get()."""
        is_long = len(field.label) > 70 or field.ftype == "table_row"
        ph = field.hint  # placeholder text from the original docx second column

        if is_long:
            frame = tk.Frame(parent, bg=C["card_bg"],
                             highlightthickness=1, highlightbackground=C["border"])
            frame.pack(fill="x", pady=(0, 4))

            has_saved = bool(saved_val and isinstance(saved_val, str))
            display_text = saved_val if has_saved else ph

            txt = tk.Text(
                frame, height=2, font=FONT,
                bg=C["card_bg"],
                fg=C["text_primary"] if has_saved else C["text_muted"],
                relief="flat", padx=8, pady=6, wrap="word",
                insertbackground=C["accent"],
                highlightthickness=0,
            )
            txt.pack(fill="x")
            if display_text:
                txt.insert("1.0", display_text)

            if ph:
                def _fi_long(_, t=txt, p=ph, fr=frame):
                    if t.get("1.0", "end-1c") == p:
                        t.delete("1.0", "end")
                        t.config(fg=C["text_primary"])
                    fr.config(highlightbackground=C["accent"])

                def _fo_long(_, t=txt, p=ph, fr=frame):
                    fr.config(highlightbackground=C["border"])
                    if not t.get("1.0", "end-1c").strip():
                        t.delete("1.0", "end")
                        t.insert("1.0", p)
                        t.config(fg=C["text_muted"])

                txt.bind("<FocusIn>",  _fi_long)
                txt.bind("<FocusOut>", _fo_long)
            else:
                def _fi_plain(_, fr=frame):
                    fr.config(highlightbackground=C["accent"])
                def _fo_plain(_, fr=frame):
                    fr.config(highlightbackground=C["border"])
                txt.bind("<FocusIn>",  _fi_plain)
                txt.bind("<FocusOut>", _fo_plain)

            class _TextProxy:
                def __init__(self_, t, p):
                    self_._t = t
                    self_._p = p
                def get(self_):
                    v = self_._t.get("1.0", "end-1c")
                    return "" if v == self_._p else v

            return _TextProxy(txt, ph)

        else:
            # Short single-line entry — use Entry with placeholder simulation
            entry_frame = tk.Frame(
                parent, bg=C["card_bg"],
                highlightthickness=1, highlightbackground=C["border"],
            )
            entry_frame.pack(fill="x", pady=(0, 4))

            has_saved = bool(saved_val and isinstance(saved_val, str))

            if ph:
                # Simulate placeholder via fg colour trick (Entry has no native placeholder)
                var = tk.StringVar(value=saved_val if has_saved else ph)
                entry = tk.Entry(
                    entry_frame, textvariable=var, font=FONT,
                    bg=C["card_bg"],
                    fg=C["text_primary"] if has_saved else C["text_muted"],
                    relief="flat", bd=0,
                    insertbackground=C["accent"],
                )
                entry.pack(fill="x", ipady=7, padx=8)

                def _fi_e(_, e=entry, v=var, p=ph, fr=entry_frame):
                    if v.get() == p:
                        v.set("")
                        e.config(fg=C["text_primary"])
                    fr.config(highlightbackground=C["accent"])

                def _fo_e(_, e=entry, v=var, p=ph, fr=entry_frame):
                    fr.config(highlightbackground=C["border"])
                    if not v.get().strip():
                        v.set(p)
                        e.config(fg=C["text_muted"])

                entry.bind("<FocusIn>",  _fi_e)
                entry.bind("<FocusOut>", _fo_e)

                class _EntryProxy:
                    def __init__(self_, v, p):
                        self_._v = v
                        self_._p = p
                    def get(self_):
                        v = self_._v.get()
                        return "" if v == self_._p else v

                return _EntryProxy(var, ph)

            else:
                var = tk.StringVar(value=saved_val if isinstance(saved_val, str) else "")
                entry = tk.Entry(
                    entry_frame, textvariable=var, font=FONT,
                    bg=C["card_bg"], fg=C["text_primary"],
                    relief="flat", bd=0,
                    insertbackground=C["accent"],
                )
                entry.pack(fill="x", ipady=7, padx=8)

                def _focus_in(_): entry_frame.config(highlightbackground=C["accent"])
                def _focus_out(_): entry_frame.config(highlightbackground=C["border"])
                entry.bind("<FocusIn>",  _focus_in)
                entry.bind("<FocusOut>", _focus_out)
                return var

    def _build_api_table_field(
        self, parent: tk.Frame, field: FormField, saved_val
    ) -> dict:
        """
        Render a multi-column API table with editable cells.

        Layout:
          ┌──────────────────┬───────────┬───────────┬──────────────────────┐
          │ (row label col)  │  Col 1    │  Col 2    │  Col N               │
          ├──────────────────┼───────────┼───────────┼──────────────────────┤
          │ Row A            │ [Text]    │ [Text]    │ [Text]               │
          │ Row B            │ [Text]    │ [Text]    │ [Text]               │
          └──────────────────┴───────────┴───────────┴──────────────────────┘

        Returns {row_label: {col_name: proxy}} where proxy.get() → str.
        """
        saved     = saved_val if isinstance(saved_val, dict) else {}
        col_names = field.options
        row_lbls  = field.rows
        n_cols    = len(col_names)

        result: dict = {}

        # ── Outer border frame ────────────────────────────────────────────
        outer = tk.Frame(parent, bg=C["border"])
        outer.pack(fill="x", pady=(8, 4))

        # tbl is the grid container; its background shows through cell gaps
        # creating 1-px grid lines automatically.
        tbl = tk.Frame(outer, bg=C["border"])
        tbl.pack(fill="x", padx=1, pady=1)

        # Column weight config: row-label col is fixed, data cols flex
        tbl.grid_columnconfigure(0, weight=0, minsize=170)
        for ci, cn in enumerate(col_names):
            cn_lo = cn.lower()
            if _is_yesno_col(cn):
                w = 1          # narrow — just fits two pill buttons
            elif any(k in cn_lo for k in ("response", "sample", "example", "output")):
                w = 5
            elif any(k in cn_lo for k in ("endpoint", "sdk", "url", "path", "method")):
                w = 3
            elif any(k in cn_lo for k in ("parameter", "param", "argument", "body")):
                w = 4
            else:
                w = 3
            tbl.grid_columnconfigure(ci + 1, weight=w)

        # ── Header row ───────────────────────────────────────────────────
        HDR_BG = C["accent_lt"]
        tk.Label(
            tbl, text="", bg=HDR_BG,
        ).grid(row=0, column=0, sticky="nsew",
               padx=(0, 1), pady=(0, 1), ipady=4)
        for ci, cn in enumerate(col_names):
            pad_r = 0 if ci == n_cols - 1 else 1
            tk.Label(
                tbl, text=cn, bg=HDR_BG,
                fg=C["accent"], font=FONT_BOLD,
                anchor="w", padx=10, pady=6,
            ).grid(row=0, column=ci + 1, sticky="nsew",
                   padx=(0, pad_r), pady=(0, 1))

        # ── Data rows ────────────────────────────────────────────────────
        for ri, row_lbl in enumerate(row_lbls):
            saved_row = saved.get(row_lbl, {}) if isinstance(saved, dict) else {}
            row_vars: dict = {}
            grid_row = ri + 1
            row_bg   = C["card_bg"] if ri % 2 == 0 else "#F9FAFB"
            pad_b    = 0 if ri == len(row_lbls) - 1 else 1

            # Row label cell
            tk.Label(
                tbl, text=row_lbl,
                bg=row_bg, fg=C["text_primary"],
                font=FONT_BOLD, anchor="nw",
                justify="left", wraplength=155,
                padx=10, pady=8,
            ).grid(row=grid_row, column=0, sticky="nsew",
                   padx=(0, 1), pady=(0, pad_b))

            # Input cells (one per column)
            for ci, col_name in enumerate(col_names):
                saved_cell = ""
                if isinstance(saved_row, dict):
                    saved_cell = str(saved_row.get(col_name, "") or "")

                pad_r = 0 if ci == n_cols - 1 else 1
                cell_frame = tk.Frame(tbl, bg=row_bg)
                cell_frame.grid(row=grid_row, column=ci + 1,
                                sticky="nsew", padx=(0, pad_r), pady=(0, pad_b))

                if _is_yesno_col(col_name):
                    # ── Yes / No pill toggle ──────────────────────────────
                    inner = tk.Frame(cell_frame, bg=row_bg)
                    inner.pack(fill="x", padx=8, pady=8)

                    yn_var = tk.StringVar(value=saved_cell or "")
                    yn_btns: dict = {}

                    _YN_STYLE = {
                        "Yes": {"sel": (C["green"],   "#FFFFFF"),
                                "off": ("#D1FAE5",    "#065F46")},
                        "No":  {"sel": (C["red"],     "#FFFFFF"),
                                "off": ("#FEE2E2",    "#991B1B")},
                    }

                    def _yn_refresh(v=yn_var, b=yn_btns):
                        for t_, btn_ in b.items():
                            bg_, fg_ = (
                                _YN_STYLE[t_]["sel"] if v.get() == t_
                                else _YN_STYLE[t_]["off"]
                            )
                            btn_.config(bg=bg_, fg=fg_)

                    # Capture b and rf as defaults so each row's click handler
                    # references its OWN dict and refresh function, not the
                    # last-assigned names in the enclosing loop scope.
                    def _yn_click(choice, v=yn_var, b=yn_btns, rf=_yn_refresh):
                        v.set("" if v.get() == choice else choice)
                        rf(v, b)

                    for choice in ("Yes", "No"):
                        bg0, fg0 = _YN_STYLE[choice]["off"]
                        btn = tk.Label(
                            inner, text=choice, cursor="hand2",
                            bg=bg0, fg=fg0, font=FONT_SMALL,
                            padx=10, pady=3, relief="flat",
                        )
                        btn.pack(side="left", padx=(0, 4))
                        # Capture _yn_click early via f= default arg
                        btn.bind("<Button-1>",
                                 lambda _, c=choice, f=_yn_click: f(c))
                        yn_btns[choice] = btn

                    _yn_refresh()

                    class _YNProxy:
                        def __init__(self_, v): self_._v = v
                        def get(self_): return self_._v.get()

                    row_vars[col_name] = _YNProxy(yn_var)

                else:
                    # ── Text cell with placeholder watermark ──────────────
                    cn_lo = col_name.lower()
                    is_tall = any(k in cn_lo for k in (
                        "response", "sample", "example", "output",
                        "parameter", "param", "argument", "body", "payload",
                    ))
                    cell_h = 4 if is_tall else 2
                    # Prefer the original docx cell text as placeholder; fall
                    # back to a generated hint if the cell was empty in the docx.
                    doc_hint = field.hints.get(row_lbl, {}).get(col_name, "")
                    ph = doc_hint if doc_hint else \
                         f"Enter {col_name.rstrip('?').strip().lower()}…"

                    has_saved = bool(saved_cell)
                    txt = tk.Text(
                        cell_frame, height=cell_h, font=FONT,
                        bg=row_bg,
                        fg=C["text_primary"] if has_saved else C["text_muted"],
                        relief="flat", padx=8, pady=6, wrap="word",
                        insertbackground=C["accent"],
                        highlightthickness=1,
                        highlightbackground=row_bg,
                        highlightcolor=C["accent"],
                    )
                    txt.pack(fill="both", expand=True)
                    txt.insert("1.0", saved_cell if has_saved else ph)

                    def _fi(_, t=txt, p=ph):
                        if t.get("1.0", "end-1c") == p:
                            t.delete("1.0", "end")
                            t.config(fg=C["text_primary"])
                        t.config(highlightbackground=C["accent"])

                    def _fo(_, t=txt, p=ph, bg=row_bg):
                        t.config(highlightbackground=bg)
                        if not t.get("1.0", "end-1c").strip():
                            t.delete("1.0", "end")
                            t.insert("1.0", p)
                            t.config(fg=C["text_muted"])

                    txt.bind("<FocusIn>",  _fi)
                    txt.bind("<FocusOut>", _fo)

                    def _make_proxy(t, p=ph):
                        class _P:
                            def get(self_):
                                v = t.get("1.0", "end-1c")
                                return "" if v == p else v
                        return _P()

                    row_vars[col_name] = _make_proxy(txt)

            result[row_lbl] = row_vars

        return result

    def _build_checkbox_field(
        self, parent: tk.Frame, field: FormField, saved_val
    ) -> list[tuple[str, tk.BooleanVar]]:
        """
        Render pill-style checkboxes for a multi-select field.
        Returns list of (option_label, BooleanVar) pairs.
        """
        selected_set = set(saved_val) if isinstance(saved_val, list) else set()
        var_pairs: list[tuple[str, tk.BooleanVar]] = []

        for opt in field.options:
            var = tk.BooleanVar(value=(opt in selected_set))

            pill = tk.Frame(
                parent, bg=C["check_on_bg"] if var.get() else C["card_bg"],
                highlightthickness=1,
                highlightbackground=C["check_on"] if var.get() else C["border"],
                cursor="hand2",
            )
            pill.pack(fill="x", pady=2)

            inner = tk.Frame(pill, bg=pill.cget("bg"))
            inner.pack(fill="x", padx=10, pady=6)

            # Custom checkbox square
            box_lbl = tk.Label(
                inner,
                text="■" if var.get() else "□",
                bg=inner.cget("bg"),
                fg=C["accent"] if var.get() else C["text_muted"],
                font=(FONT_FAMILY, 10),
            )
            box_lbl.pack(side="left", padx=(0, 8))

            opt_lbl = tk.Label(
                inner, text=opt, bg=inner.cget("bg"),
                fg=C["accent"] if var.get() else C["text_primary"],
                font=FONT, anchor="w", wraplength=580, justify="left",
            )
            opt_lbl.pack(side="left", fill="x", expand=True)

            # Toggle behaviour
            def _toggle(v=var, p=pill, il=inner, bl=box_lbl, ol=opt_lbl):
                v.set(not v.get())
                on = v.get()
                bg_ = C["check_on_bg"] if on else C["card_bg"]
                bo_ = C["check_on"]    if on else C["border"]
                tx_ = C["accent"]      if on else C["text_primary"]
                p.config(bg=bg_,  highlightbackground=bo_)
                il.config(bg=bg_)
                bl.config(bg=bg_, fg=C["accent"] if on else C["text_muted"],
                          text="■" if on else "□")
                ol.config(bg=bg_, fg=tx_)

            for w in (pill, inner, box_lbl, opt_lbl):
                w.bind("<Button-1>", lambda _, t=_toggle: t())

            var_pairs.append((opt, var))

        return var_pairs

    # ── Save logic ─────────────────────────────────────────────────────────

    def _collect_and_save(self, section_id: str, node: Node):
        """Read all current form widget values and store in self.responses."""
        data: dict[str, object] = {}
        for entry in self._field_vars:
            kind, label, payload = entry
            if kind == "checkbox":
                data[label] = [opt for opt, var in payload if var.get()]
            elif kind == "api_table":
                data[label] = {
                    row_lbl: {col: p.get() for col, p in cols.items()}
                    for row_lbl, cols in payload.items()
                }
            else:
                data[label] = payload.get()

        self.responses[section_id] = data
        self._update_progress()
        self._refresh_nav()

    # ── Summary & export ───────────────────────────────────────────────────

    def _show_summary(self):
        """Render the summary screen with totals and the Save HTML button."""
        self._clear_content()
        self._current_id = "__summary__"
        self._refresh_nav()

        pad = self._pad_frame()

        tk.Label(
            pad, text="Summary & Save",
            bg=C["bg"], fg=C["text_primary"], font=FONT_TITLE,
        ).pack(anchor="w")

        total   = len(self.all_leaves)
        done    = sum(1 for n in self.all_leaves
                      if self._is_section_done(n.breadcrumb()))
        pct     = int(done / total * 100) if total else 0

        # Stats row
        stats = tk.Frame(pad, bg=C["bg"])
        stats.pack(fill="x", pady=(18, 20))
        for label, value in [
            ("Total sections", str(total)),
            ("Answered",        str(done)),
            ("Completion",      f"{pct}%"),
        ]:
            card = tk.Frame(
                stats, bg=C["card_bg"],
                highlightthickness=1, highlightbackground=C["border"],
            )
            card.pack(side="left", padx=(0, 12), ipadx=16, ipady=10)
            tk.Label(card, text=value, bg=C["card_bg"],
                     fg=C["accent"], font=(FONT_FAMILY, 22, "bold")).pack()
            tk.Label(card, text=label, bg=C["card_bg"],
                     fg=C["text_muted"], font=FONT_SMALL).pack()

        # Progress bar (visual only — reflects the actual progress)
        pb_frame = tk.Frame(pad, bg=C["bg"])
        pb_frame.pack(fill="x", pady=(0, 20))
        ttk.Progressbar(
            pb_frame, value=pct, maximum=100, length=400,
            style="Survey.Horizontal.TProgressbar",
        ).pack(side="left")
        tk.Label(
            pb_frame, text=f"  {pct}% complete",
            bg=C["bg"], fg=C["accent"], font=FONT_BOLD,
        ).pack(side="left")

        tk.Frame(pad, bg=C["border"], height=1).pack(fill="x", pady=(0, 16))

        # Section-by-section preview
        if self.responses:
            for section_id, fields in self.responses.items():
                self._summary_card(pad, section_id, fields)
        else:
            tk.Label(
                pad, text="No answers recorded yet.",
                bg=C["bg"], fg=C["text_muted"], font=FONT,
            ).pack(pady=20)

        # Save button
        tk.Frame(pad, bg=C["border"], height=1).pack(fill="x", pady=(20, 0))
        save_row = tk.Frame(pad, bg=C["bg"])
        save_row.pack(fill="x", pady=(16, 0))

        make_button(
            save_row, "  Save as HTML  ", self._save_html
        ).pack(side="left", padx=(0, 12))

        make_button(
            save_row, "  Save as JSON  ", self._save_json,
            primary=False,
        ).pack(side="left")

    def _summary_card(self, parent: tk.Frame, section_id: str, fields: dict):
        """Render one collapsed section card in the summary view."""
        card = tk.Frame(
            parent, bg=C["card_bg"],
            highlightthickness=1, highlightbackground=C["border"],
        )
        card.pack(fill="x", pady=4)

        header = tk.Frame(card, bg=C["card_bg"])
        header.pack(fill="x", padx=14, pady=8)

        answered = sum(
            1 for v in fields.values()
            if (isinstance(v, list) and v) or (isinstance(v, str) and v.strip())
        )
        done = answered == len(fields)
        badge_bg = C["green_lt"] if done else C["accent_lt"]
        badge_fg = "#065F46"    if done else C["accent"]
        tk.Label(
            header, text=f"{answered}/{len(fields)}",
            bg=badge_bg, fg=badge_fg,
            font=(FONT_FAMILY, 8, "bold"), padx=6, pady=2,
        ).pack(side="right")

        short = section_id if len(section_id) <= 70 else section_id[:68] + "…"
        tk.Label(
            header, text=short, bg=C["card_bg"],
            fg=C["text_primary"], font=FONT_BOLD, anchor="w",
        ).pack(side="left", fill="x")

        # Show first few answers as a preview
        preview_count = 0
        for label, value in fields.items():
            if preview_count >= 3:
                break
            if isinstance(value, list):
                display = ", ".join(value) if value else "—"
            else:
                display = value.strip() if value else "—"
            if not display or display == "—":
                continue

            row = tk.Frame(card, bg=C["card_bg"])
            row.pack(fill="x", padx=14, pady=(0, 3))
            tk.Label(
                row,
                text=(label[:40] + "…" if len(label) > 40 else label) + ":",
                bg=C["card_bg"], fg=C["text_muted"], font=FONT_SMALL, anchor="w",
            ).pack(side="left")
            tk.Label(
                row,
                text=display[:60] + ("…" if len(display) > 60 else ""),
                bg=C["card_bg"], fg=C["text_primary"], font=FONT_SMALL, anchor="w",
            ).pack(side="left", padx=(4, 0))
            preview_count += 1

        if preview_count < answered:
            tk.Label(
                card, text=f"  … and {answered - preview_count} more",
                bg=C["card_bg"], fg=C["text_muted"], font=FONT_SMALL, anchor="w",
            ).pack(padx=14, pady=(0, 6))
        else:
            tk.Frame(card, bg=C["bg"], height=4).pack()

    # ── File export ────────────────────────────────────────────────────────

    def _save_html(self):
        """Write HTML report to a user-chosen path and show a success dialog."""
        if not self.responses:
            messagebox.showwarning(
                "No data", "Please fill in at least one section before saving."
            )
            return

        default_name = (
            Path(self.docx_path).stem + "_survey_results.html"
            if self.docx_path
            else "survey_results.html"
        )
        path = filedialog.asksaveasfilename(
            title="Save HTML report",
            defaultextension=".html",
            initialfile=default_name,
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
        )
        if not path:
            return

        docx_name = os.path.basename(self.docx_path) if self.docx_path else "Survey"
        html = build_html_report(
            docx_name=docx_name,
            responses=self.responses,
            total_leaves=len(self.all_leaves),
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)

        abs_path = os.path.abspath(path)
        messagebox.showinfo(
            "Saved",
            f"HTML report saved successfully.\n\nPath:\n{abs_path}",
        )
        self._set_status(f"Saved: {abs_path}")

    def _save_json(self):
        """Write raw JSON responses to a user-chosen path."""
        if not self.responses:
            messagebox.showwarning("No data", "No answers to export yet.")
            return

        default_name = (
            Path(self.docx_path).stem + "_survey_results.json"
            if self.docx_path
            else "survey_results.json"
        )
        path = filedialog.asksaveasfilename(
            title="Save JSON",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        payload = {
            "generated_at": datetime.now().isoformat(),
            "source_docx":  os.path.basename(self.docx_path),
            "responses":    self.responses,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

        abs_path = os.path.abspath(path)
        messagebox.showinfo(
            "Saved",
            f"JSON saved successfully.\n\nPath:\n{abs_path}",
        )
        self._set_status(f"Saved: {abs_path}")

    # ── Utility ────────────────────────────────────────────────────────────

    def _find_node(self, section_id: str) -> Node | None:
        """Locate a Node by its breadcrumb string."""
        def _search(node: Node) -> Node | None:
            if node.breadcrumb() == section_id:
                return node
            for child in node.children:
                found = _search(child)
                if found:
                    return found
            return None
        return _search(self.root_node) if self.root_node else None


# =============================================================================
# Entry point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Desktop survey tool — loads a .docx and presents a GUI form."
    )
    parser.add_argument(
        "--docx", default=None,
        help="Path to a .docx file to load on startup"
    )
    args = parser.parse_args()

    # Auto-detect a .docx in the current directory if none specified
    preload = args.docx
    if not preload:
        candidates = sorted(Path(".").glob("*.docx"))
        if candidates:
            preload = str(candidates[0])

    app = SurveyApp(preload_docx=preload)
    app.mainloop()


if __name__ == "__main__":
    main()
