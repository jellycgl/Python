# Word Document Survey Tool

A command-line survey application that reads any hierarchically-structured
Word document (.docx) and turns its headings and tables into an interactive,
multi-level survey.

---

## Features

| Feature | Detail |
|---|---|
| **Hierarchical navigation** | Heading 1 → Heading 2 → … leaf menus, one level at a time |
| **Auto-detects field types** | Checkbox lists, free-text fields, and table rows |
| **Progress tracking** | Completed sections show a ✓ in the menu |
| **Interrupt-safe** | Ctrl-C saves whatever has been answered so far |
| **JSON output** | Timestamped output file with full answer tree |

---

## Installation

```bash
pip install python-docx rich
```

---

## Usage

```bash
# Auto-detect the first .docx in the current directory
python survey.py

# Specify the document explicitly
python survey.py --docx TechSpec_Support_Data_Collection_Guide.docx

# Custom output file
python survey.py --docx myfile.docx --output my_answers.json

# Show help
python survey.py --help
```

---

## Navigation during the survey

| Input | Action |
|---|---|
| `1`, `2`, … | Open that numbered sub-section |
| `A` | Fill in all sub-sections in order |
| `B` | Go back / mark section as done |
| Blank + Enter | Skip the current field |
| Ctrl-C | Exit and save progress |

---

## Output format

```json
{
  "generated_at": "2026-04-10T14:32:01.123456",
  "responses": {
    "1. Third-Party System Overview": {
      "System / Product Name": "Cisco Catalyst Center",
      "Deployment Model": ["On-premises", "Cloud-managed SaaS"],
      "API Interface Style": ["REST(JSON)"]
    },
    "2. Connectivity & Authentication > 2.1 Connection Parameters": {
      "Endpoint URL": "https://controller.example.com",
      "Port": "443"
    }
  }
}
```

---

## How it works

1. **Parse** – `python-docx` reads the document's XML.  Every `Heading N`
   paragraph becomes a tree node; body paragraphs and table rows become
   `FormField` objects attached to the nearest heading.

2. **Navigate** – The survey engine walks the tree top-down, showing a
   numbered menu at each branch node and collecting answers at leaf nodes.

3. **Save** – All answers are written to a JSON file at the end (or on
   Ctrl-C).

---

## Adapting to other documents

The tool works with **any** Word document that uses Word's built-in
`Heading 1` / `Heading 2` / … paragraph styles.  It does not depend on
any content specific to the NetBrain questionnaire.
