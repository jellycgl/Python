"""
survey.py - Hierarchical Survey Tool for Word Documents
========================================================
Reads a .docx file, parses its heading structure into a multi-level
menu tree, then presents each level one at a time (Level-1 -> Level-2 ->
... -> leaf questions).  All responses are saved to a timestamped JSON file.

Usage:
    python survey.py                              # auto-detect .docx in current folder
    python survey.py --docx path/to/file.docx
    python survey.py --output results.json
    python survey.py --docx file.docx --output out.json

Dependencies:
    pip install python-docx          (only required external package)
    'rich' is used automatically when installed, but is optional.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ── python-docx (required) ───────────────────────────────────────────────────
try:
    from docx import Document
    from docx.text.paragraph import Paragraph as DocxPara
    from docx.table import Table as DocxTable
except ImportError:
    print("ERROR: python-docx is not installed.  Run:  pip install python-docx")
    sys.exit(1)

# ── rich (optional - prettier output) ───────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table as RichTable
    from rich.rule import Rule
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False


# ---------------------------------------------------------------------------
# Minimal terminal helpers used when rich is NOT installed
# ---------------------------------------------------------------------------

def _strip_markup(text: str) -> str:
    """Remove simple [tag] / [/tag] rich markup so plain print looks clean."""
    return re.sub(r"\[/?[a-zA-Z _/]+\]", "", text)


def _plain_print(text: str = "", end: str = "\n") -> None:
    print(_strip_markup(text), end=end)


def _plain_rule(title: str = "") -> None:
    width = 70
    if title:
        pad = max(0, (width - len(title) - 2) // 2)
        print("-" * pad + " " + title + " " + "-" * pad)
    else:
        print("-" * width)


def _plain_panel(body: str, subtitle: str = "") -> None:
    _plain_rule()
    print(_strip_markup(body))
    if subtitle:
        print(subtitle)
    _plain_rule()


def _plain_prompt(question: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    return input(f"{_strip_markup(question)}{hint}: ").strip() or default


# ---------------------------------------------------------------------------
# Unified UI wrappers - same call site regardless of whether rich is present
# ---------------------------------------------------------------------------

def ui_print(text: str = "", end: str = "\n") -> None:
    if _RICH:
        console.print(text, end=end)
    else:
        _plain_print(text, end=end)


def ui_rule(title: str = "") -> None:
    if _RICH:
        console.print(Rule(f"[bold]{title}[/bold]") if title else Rule())
    else:
        _plain_rule(title)


def ui_panel(body: str, subtitle: str = "") -> None:
    if _RICH:
        console.print(Panel(body, subtitle=subtitle, border_style="blue"))
    else:
        _plain_panel(body, subtitle)


def ui_prompt(question: str, default: str = "") -> str:
    if _RICH:
        return Prompt.ask(question, default=default).strip()
    else:
        return _plain_prompt(question, default)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maps Word heading style names to numeric depth
HEADING_STYLES = {
    "Heading 1": 1,
    "Heading 2": 2,
    "Heading 3": 3,
    "Heading 4": 4,
    "Heading 5": 5,
}

# Checkbox Unicode and ASCII variants found in the source document
CHECKBOX_RE = re.compile(r"☐\s*|□\s*|\[\s*\]\s*")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Node:
    """
    One node in the document heading hierarchy.

    Attributes
    ----------
    level    : int   - heading depth (0 = invisible root, 1 = H1, 2 = H2 ...)
    title    : str   - heading text, cleaned of markup
    parent   : Node  - parent node (None for root)
    children : list  - child Nodes (sub-sections discovered below this heading)
    fields   : list  - FormField objects for all answerable items in this section
    """

    def __init__(self, level: int, title: str, parent=None):
        self.level = level
        self.title = title
        self.parent = parent
        self.children = []   # list[Node]
        self.fields = []     # list[FormField]

    def is_leaf(self) -> bool:
        """True when this section contains no sub-sections."""
        return len(self.children) == 0

    def breadcrumb(self) -> str:
        """Return the full path from root, e.g. '1. Overview > 1.1 Auth'."""
        parts = []
        node = self
        while node and node.level > 0:
            parts.append(node.title)
            node = node.parent
        return " > ".join(reversed(parts))

    def __repr__(self):
        return (
            f"Node(L{self.level} {self.title!r}, "
            f"children={len(self.children)}, fields={len(self.fields)})"
        )


class FormField:
    """
    One answerable item extracted from the document body.

    Types
    -----
    text      : open free-text answer
    checkbox  : pick one or more options from a predefined list
    table_row : key / value row originating from a document table
    """

    def __init__(self, ftype: str, label: str, options=None):
        self.ftype = ftype          # "text" | "checkbox" | "table_row"
        self.label = label          # the question or field label shown to the user
        self.options = options or []  # choices (checkbox type only)
        self.answer = None          # filled in during the survey session

    def __repr__(self):
        return f"FormField({self.ftype!r}, {self.label[:50]!r})"


# ---------------------------------------------------------------------------
# Document parser
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Remove markdown decoration and strip surrounding whitespace."""
    return text.strip().strip("*_").strip()


def _extract_checkboxes(text: str) -> list:
    """
    Split *text* on checkbox markers and return the option labels.
    Returns an empty list when no checkbox marker is found.
    """
    if not CHECKBOX_RE.search(text):
        return []
    parts = CHECKBOX_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _para_heading_level(para) -> int:
    """
    Return the numeric heading level of a paragraph object,
    or 0 if it is not a heading.
    """
    style_name = para.style.name if para.style else ""
    return HEADING_STYLES.get(style_name, 0)


def _para_full_text(para) -> str:
    """Concatenate text from all runs inside a paragraph."""
    return "".join(run.text for run in para.runs)


def parse_document(docx_path: str) -> Node:
    """
    Parse the .docx file and return the invisible root Node of the
    heading/content tree.

    Strategy
    --------
    1. Walk every XML block element in document.body sequentially.
    2. Heading paragraphs push/pop a depth stack to maintain the current
       parent node.
    3. Body paragraphs and table rows are attached as FormField objects
       to the node currently at the top of the stack.
    """
    doc = Document(docx_path)
    root = Node(level=0, title="ROOT")
    # stack[-1] is always the "current parent" for new content
    stack = [root]

    def current_parent():
        return stack[-1]

    for block in doc.element.body:
        # Determine the local XML tag name (strip the namespace URI)
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

        # ── Paragraph ────────────────────────────────────────────────────────
        if tag == "p":
            para = DocxPara(block, doc)
            level = _para_heading_level(para)
            raw = _para_full_text(para).strip()

            if not raw:
                continue

            if level:
                # Heading: pop the stack until the parent is shallower
                while len(stack) > 1 and stack[-1].level >= level:
                    stack.pop()

                node = Node(level=level, title=_clean(raw), parent=stack[-1])
                stack[-1].children.append(node)
                stack.append(node)

            else:
                # Body paragraph: decide field type from content
                parent_node = current_parent()
                checkboxes = _extract_checkboxes(raw)

                if checkboxes:
                    # Merge into the preceding checkbox field if it exists;
                    # this handles one-option-per-line layouts.
                    if (parent_node.fields
                            and parent_node.fields[-1].ftype == "checkbox"):
                        parent_node.fields[-1].options.extend(checkboxes)
                    else:
                        parent_node.fields.append(
                            FormField("checkbox", "Select all that apply", checkboxes)
                        )
                else:
                    # Plain body text becomes a free-text field if long enough
                    if len(raw) > 5 and not raw.startswith("*Note*"):
                        parent_node.fields.append(
                            FormField("text", raw[:120])
                        )

        # ── Table ─────────────────────────────────────────────────────────────
        elif tag == "tbl":
            tbl = DocxTable(block, doc)
            parent_node = current_parent()

            for row_idx, row in enumerate(tbl.rows):
                cells = [c.text.strip() for c in row.cells]

                # Skip empty rows
                if not any(cells):
                    continue

                # Skip all-uppercase header rows (e.g. "ITEM | DESCRIPTION")
                if row_idx == 0 and all(c == c.upper() or not c for c in cells):
                    continue

                label = cells[0] if cells[0] else f"Row {row_idx + 1}"
                if len(label) < 3:
                    continue

                # Check the second cell for checkbox options
                second = cells[1] if len(cells) > 1 else ""
                checkboxes = _extract_checkboxes(second)

                if checkboxes:
                    parent_node.fields.append(
                        FormField("checkbox", label, checkboxes)
                    )
                else:
                    parent_node.fields.append(
                        FormField("table_row", label)
                    )

    return root


# ---------------------------------------------------------------------------
# Survey engine - prompting functions
# ---------------------------------------------------------------------------

def prompt_text_field(field: FormField) -> str:
    """
    Display the field label and collect a free-text answer.
    Returns "" if the user presses Enter without typing.
    """
    ui_print(f"  [cyan]>[/cyan] {field.label}")
    return ui_prompt("    Answer (Enter to skip)", default="")


def prompt_checkbox_field(field: FormField) -> list:
    """
    Show numbered options and collect the user's selections.

    Input rules:
    - Comma-separated numbers:  1,3
    - Numbers and free text:    1, My custom option
    - Just Enter:               skip (returns empty list)

    Returns a list of selected label strings.
    """
    if not field.options:
        return []

    ui_print(f"  [cyan]>[/cyan] {field.label}")
    for idx, opt in enumerate(field.options, 1):
        ui_print(f"    [bold]{idx}.[/bold] {opt}")

    while True:
        raw = ui_prompt(
            "    Numbers (comma-separated) or type custom text  [Enter=skip]",
            default=""
        )
        if not raw:
            return []

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        selected = []
        valid = True

        for part in parts:
            if part.isdigit():
                n = int(part)
                if 1 <= n <= len(field.options):
                    selected.append(field.options[n - 1])
                else:
                    ui_print(
                        f"    [red]'{n}' is out of range "
                        f"(1-{len(field.options)}).  Try again.[/red]"
                    )
                    valid = False
                    break
            else:
                # Treat non-numeric input as a custom "Other:" entry
                selected.append(f"Other: {part}")

        if valid:
            return selected


def conduct_leaf_survey(node: Node, responses: dict) -> None:
    """
    Iterate through all FormFields of a leaf node and record answers.

    Stored as:  responses[section_breadcrumb][field_label] = answer_value
    """
    if not node.fields:
        ui_print("[dim]  (no input fields in this section)[/dim]")
        return

    key = node.breadcrumb()
    responses.setdefault(key, {})

    for field in node.fields:
        if field.ftype in ("text", "table_row"):
            answer = prompt_text_field(field)
            responses[key][field.label] = answer
        elif field.ftype == "checkbox":
            answer = prompt_checkbox_field(field)
            responses[key][field.label] = answer
        ui_print()  # blank line between fields


# ---------------------------------------------------------------------------
# Survey engine - navigation
# ---------------------------------------------------------------------------

def _node_is_done(node: Node, responses: dict) -> bool:
    """Return True if any response has been recorded under this subtree."""
    bc = node.breadcrumb()
    return any(k == bc or k.startswith(bc + " > ") for k in responses)


def navigate_tree(node: Node, responses: dict) -> None:
    """
    Recursively navigate the heading tree.

    - Leaf node  ->  collect answers directly via conduct_leaf_survey().
    - Branch node -> show a numbered menu of child sections and loop until
                     the user selects 'B' (back) or 'A' (all sections).
    """
    # ── Leaf: collect answers ────────────────────────────────────────────────
    if node.is_leaf():
        ui_rule(node.breadcrumb())
        conduct_leaf_survey(node, responses)
        return

    # ── Branch: show menu ────────────────────────────────────────────────────
    while True:
        ui_print()
        ui_panel(
            f"[bold]{node.title}[/bold]",
            subtitle="Select a section to fill in"
        )

        if _RICH:
            # Rich table with status column
            tbl = RichTable(show_header=False, box=None, padding=(0, 1))
            tbl.add_column("Num", style="bold yellow", width=5)
            tbl.add_column("Section")
            tbl.add_column("Status", style="dim", width=10)
            for idx, child in enumerate(node.children, 1):
                done = _node_is_done(child, responses)
                status_str = "[green]done[/green]" if done else "[dim]pending[/dim]"
                tbl.add_row(str(idx), child.title, status_str)
            tbl.add_row("A", "Fill all sections in order", "")
            tbl.add_row("B", "Done / go back", "")
            console.print(tbl)
        else:
            # Plain text list
            for idx, child in enumerate(node.children, 1):
                done = _node_is_done(child, responses)
                status_str = "[done]" if done else "[pending]"
                print(f"  {idx:>3}. {child.title}  {status_str}")
            print("    A. Fill all sections in order")
            print("    B. Done / go back")

        ui_print()
        choice = ui_prompt("[bold]Enter choice[/bold]").strip().upper()

        if choice == "B":
            # Return to the parent menu
            return

        if choice == "A":
            # Walk every child in document order
            for child in node.children:
                navigate_tree(child, responses)
            return

        if choice.isdigit():
            n = int(choice)
            if 1 <= n <= len(node.children):
                navigate_tree(node.children[n - 1], responses)
            else:
                ui_print(
                    f"[red]Please enter a number between 1 and {len(node.children)}.[/red]"
                )
        else:
            ui_print("[red]Invalid input - please try again.[/red]")


# ---------------------------------------------------------------------------
# Persist and summarise
# ---------------------------------------------------------------------------

def save_responses(responses: dict, output_path: str) -> None:
    """Write the collected answers to a JSON file."""
    payload = {
        "generated_at": datetime.now().isoformat(),
        "source": "survey.py",
        "responses": responses,
    }
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    ui_print(f"\n[green]Responses saved to:[/green] [bold]{output_path}[/bold]")


def show_summary(responses: dict) -> None:
    """Print a completion table to the terminal."""
    ui_print()
    ui_rule("Survey Summary")
    total_sections = len(responses)
    total_fields = sum(len(v) for v in responses.values())
    answered = sum(
        sum(1 for v in sec.values() if v not in ("", [], None))
        for sec in responses.values()
    )
    ui_print(f"  Sections visited : {total_sections}")
    ui_print(f"  Fields answered  : {answered} / {total_fields}")
    ui_print()
    for section, fields in responses.items():
        n = sum(1 for v in fields.values() if v not in ("", [], None))
        ui_print(f"  {section}  ({n}/{len(fields)} filled)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Interactive hierarchical survey from a Word (.docx) document."
    )
    parser.add_argument(
        "--docx",
        default=None,
        help="Path to the .docx input file  "
             "(default: first .docx found in current directory)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path  "
             "(default: survey_responses_<YYYYMMDD_HHMMSS>.json)"
    )
    args = parser.parse_args()

    # ── Locate the .docx ────────────────────────────────────────────────────
    if args.docx:
        docx_path = args.docx
    else:
        candidates = sorted(Path(".").glob("*.docx"))
        if not candidates:
            ui_print(
                "[red]No .docx file found in the current directory.  "
                "Use --docx to specify the path.[/red]"
            )
            sys.exit(1)
        docx_path = str(candidates[0])
        ui_print(f"[dim]Auto-detected document:[/dim] {docx_path}")

    if not os.path.exists(docx_path):
        ui_print(f"[red]File not found:[/red] {docx_path}")
        sys.exit(1)

    # ── Build the output path ────────────────────────────────────────────────
    if args.output:
        output_path = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"survey_responses_{ts}.json"

    # ── Welcome banner ───────────────────────────────────────────────────────
    ui_print()
    ui_panel(
        "[bold blue]Hierarchical Document Survey[/bold blue]\n"
        "[dim]Navigate with numbers | A = fill all | B = back | Ctrl-C = save & exit[/dim]"
    )

    # ── Parse document into a tree ───────────────────────────────────────────
    ui_print(f"\n[dim]Parsing:[/dim] {docx_path} ...")
    try:
        root = parse_document(docx_path)
    except Exception as exc:
        ui_print(f"[red]Failed to parse document:[/red] {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if not root.children:
        ui_print("[red]No heading sections found in the document.[/red]")
        sys.exit(1)

    ui_print(f"[green]Loaded[/green] {len(root.children)} top-level section(s).\n")

    # ── Run the interactive survey ───────────────────────────────────────────
    responses: dict = {}
    try:
        navigate_tree(root, responses)
    except KeyboardInterrupt:
        ui_print("\n[yellow]Survey interrupted - saving progress ...[/yellow]")

    # ── Save results and show summary ────────────────────────────────────────
    if responses:
        save_responses(responses, output_path)
        show_summary(responses)
    else:
        ui_print("[yellow]No answers were recorded.[/yellow]")

    ui_print("\n[bold green]Done.[/bold green]\n")


if __name__ == "__main__":
    main()
