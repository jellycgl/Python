"""
survey_ui/app.py  -  Web-based Survey UI powered by Flask
==========================================================
Run:
    python app.py                                  # auto-detect *.docx nearby
    python app.py --docx path/to/file.docx
    python app.py --port 5050                      # custom port

Then open  http://localhost:5000  in any browser.

Dependencies:  flask  python-docx   (both pure-Python, no C extensions needed)
"""

import argparse
import json
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Timer

try:
    from docx import Document
    from docx.text.paragraph import Paragraph as DocxPara
    from docx.table import Table as DocxTable
except ImportError:
    sys.exit("ERROR: python-docx not installed.  Run:  pip install python-docx")

try:
    from flask import Flask, jsonify, render_template_string, request
except ImportError:
    sys.exit("ERROR: flask not installed.  Run:  pip install flask")


# ---------------------------------------------------------------------------
# Document parser  (identical logic to the console version)
# ---------------------------------------------------------------------------

HEADING_STYLES = {"Heading 1": 1, "Heading 2": 2, "Heading 3": 3,
                  "Heading 4": 4, "Heading 5": 5}
CHECKBOX_RE = re.compile(r"☐\s*|□\s*|\[\s*\]\s*")


class Node:
    def __init__(self, level, title, parent=None):
        self.level = level
        self.title = title
        self.parent = parent
        self.children = []
        self.fields = []

    def is_leaf(self):
        return len(self.children) == 0

    def breadcrumb(self):
        parts, node = [], self
        while node and node.level > 0:
            parts.append(node.title)
            node = node.parent
        return " > ".join(reversed(parts))

    def to_dict(self):
        return {
            "id": self.breadcrumb(),
            "title": self.title,
            "level": self.level,
            "is_leaf": self.is_leaf(),
            "children": [c.to_dict() for c in self.children],
            "fields": [f.to_dict() for f in self.fields],
        }


class FormField:
    def __init__(self, ftype, label, options=None):
        self.ftype = ftype
        self.label = label
        self.options = options or []

    def to_dict(self):
        return {"type": self.ftype, "label": self.label, "options": self.options}


def _extract_checkboxes(text):
    if not CHECKBOX_RE.search(text):
        return []
    return [p.strip() for p in CHECKBOX_RE.split(text) if p.strip()]


def parse_document(docx_path):
    doc = Document(docx_path)
    root = Node(level=0, title="ROOT")
    stack = [root]

    def cur():
        return stack[-1]

    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

        if tag == "p":
            para = DocxPara(block, doc)
            style_name = para.style.name if para.style else ""
            level = HEADING_STYLES.get(style_name, 0)
            raw = "".join(r.text for r in para.runs).strip()
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
                        parent.fields.append(FormField("checkbox", "Select all that apply", cbs))
                elif len(raw) > 5 and not raw.startswith("*Note*"):
                    parent.fields.append(FormField("text", raw[:120]))

        elif tag == "tbl":
            tbl = DocxTable(block, doc)
            parent = cur()
            for i, row in enumerate(tbl.rows):
                cells = [c.text.strip() for c in row.cells]
                if not any(cells):
                    continue
                if i == 0 and all(c == c.upper() or not c for c in cells):
                    continue
                label = cells[0] if cells[0] else f"Row {i+1}"
                if len(label) < 3:
                    continue
                second = cells[1] if len(cells) > 1 else ""
                cbs = _extract_checkboxes(second)
                if cbs:
                    parent.fields.append(FormField("checkbox", label, cbs))
                else:
                    parent.fields.append(FormField("table_row", label))

    return root


# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["JSON_ENSURE_ASCII"] = False

# Global state (single-user desktop tool)
STATE = {
    "tree": None,         # Node root
    "docx_path": "",
    "responses": {},      # {breadcrumb: {label: answer}}
    "output_path": "",
}

# ---------------------------------------------------------------------------
# HTML template  (single-file SPA - no external files needed)
# ---------------------------------------------------------------------------

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetBrain Tech Spec Survey</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:15px;background:#f5f5f7;color:#1d1d1f;min-height:100vh}

/* ── layout ── */
.shell{display:flex;height:100vh;overflow:hidden}
.sidebar{width:280px;min-width:280px;background:#fff;border-right:1px solid #e0e0e0;display:flex;flex-direction:column;overflow:hidden}
.main{flex:1;overflow-y:auto;padding:0}

/* ── sidebar ── */
.sidebar-header{padding:18px 16px 14px;border-bottom:1px solid #e8e8e8}
.sidebar-header h1{font-size:15px;font-weight:600;color:#1d1d1f;line-height:1.3}
.sidebar-header p{font-size:12px;color:#6e6e73;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nav{flex:1;overflow-y:auto;padding:8px 0}
.nav-item{display:flex;align-items:center;gap:8px;padding:8px 16px;cursor:pointer;font-size:13px;color:#3c3c43;line-height:1.4;border-left:3px solid transparent;transition:background .12s}
.nav-item:hover{background:#f5f5f7}
.nav-item.active{background:#e8f0fe;border-left-color:#1a73e8;color:#1a73e8;font-weight:500}
.nav-item.done .dot{background:#34c759}
.nav-item .dot{width:7px;height:7px;border-radius:50%;background:#d1d1d6;flex-shrink:0;margin-left:auto}
.nav-indent-1{padding-left:28px}
.nav-indent-2{padding-left:44px}
.nav-indent-3{padding-left:60px}

/* ── main content ── */
.content{max-width:780px;margin:0 auto;padding:36px 32px 60px}
.page-header{margin-bottom:28px}
.page-header h2{font-size:22px;font-weight:600;color:#1d1d1f}
.breadcrumb{font-size:12px;color:#8e8e93;margin-top:6px}
.section-intro{font-size:14px;color:#6e6e73;margin-bottom:24px;line-height:1.6;background:#f9f9f9;padding:12px 14px;border-radius:8px;border-left:3px solid #d1d1d6}

/* ── upload screen ── */
.upload-screen{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;min-height:400px;text-align:center;padding:40px}
.upload-icon{width:64px;height:64px;background:#e8f0fe;border-radius:16px;display:flex;align-items:center;justify-content:center;margin:0 auto 20px}
.upload-screen h2{font-size:20px;font-weight:600;margin-bottom:8px}
.upload-screen p{font-size:14px;color:#6e6e73;margin-bottom:24px;max-width:360px;line-height:1.5}
.upload-zone{border:2px dashed #c5c5c7;border-radius:12px;padding:28px 40px;cursor:pointer;transition:border-color .15s,background .15s;margin-bottom:16px}
.upload-zone:hover{border-color:#1a73e8;background:#f0f6ff}
.upload-zone input{display:none}
.upload-zone label{cursor:pointer;font-size:14px;color:#1a73e8;font-weight:500}

/* ── fields ── */
.field-group{margin-bottom:22px}
.field-label{font-size:13px;font-weight:500;color:#3c3c43;margin-bottom:7px;line-height:1.4}
.field-label.required::after{content:" *";color:#e8441d}
input[type=text], textarea, select{
  width:100%;padding:9px 12px;border:1px solid #d1d1d6;border-radius:8px;
  font-size:14px;color:#1d1d1f;background:#fff;outline:none;transition:border-color .15s;
  font-family:inherit
}
input[type=text]:focus, textarea:focus{border-color:#1a73e8;box-shadow:0 0 0 3px rgba(26,115,232,.12)}
textarea{min-height:72px;resize:vertical;line-height:1.5}

/* ── checkbox options ── */
.options-grid{display:flex;flex-direction:column;gap:8px}
.option-pill{display:flex;align-items:center;gap:10px;padding:9px 14px;border:1px solid #d1d1d6;border-radius:8px;cursor:pointer;transition:background .12s,border-color .12s;user-select:none}
.option-pill:hover{background:#f5f5f7}
.option-pill.selected{background:#e8f0fe;border-color:#1a73e8}
.option-pill input[type=checkbox]{width:16px;height:16px;accent-color:#1a73e8;flex-shrink:0;cursor:pointer}
.option-pill span{font-size:14px;color:#3c3c43;line-height:1.4}
.option-pill.selected span{color:#1a73e8}
.other-input{margin-top:8px}

/* ── buttons ── */
.btn-row{display:flex;gap:10px;margin-top:32px;padding-top:20px;border-top:1px solid #e8e8e8}
.btn{padding:9px 20px;border-radius:8px;font-size:14px;font-weight:500;cursor:pointer;border:none;transition:background .12s,opacity .12s}
.btn-primary{background:#1a73e8;color:#fff}
.btn-primary:hover{background:#1557b0}
.btn-secondary{background:#f5f5f7;color:#3c3c43;border:1px solid #d1d1d6}
.btn-secondary:hover{background:#e8e8e8}
.btn-success{background:#34c759;color:#fff}
.btn-success:hover{background:#28a745}
.btn-danger{background:#e8441d;color:#fff}
.btn:disabled{opacity:.45;cursor:not-allowed}

/* ── progress bar ── */
.progress-bar-wrap{background:#e8e8e8;border-radius:4px;height:5px;margin-top:10px;overflow:hidden}
.progress-bar{height:5px;background:#1a73e8;border-radius:4px;transition:width .35s}

/* ── summary page ── */
.summary-card{background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:18px 20px;margin-bottom:14px}
.summary-card h3{font-size:14px;font-weight:600;color:#1d1d1f;margin-bottom:12px}
.summary-row{display:flex;gap:12px;padding:5px 0;border-bottom:1px solid #f0f0f0;font-size:13px}
.summary-row:last-child{border-bottom:none}
.summary-key{color:#6e6e73;flex:0 0 40%;min-width:0;overflow-wrap:break-word}
.summary-val{color:#1d1d1f;flex:1;min-width:0;overflow-wrap:break-word}
.stat-row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px}
.stat{background:#f5f5f7;border-radius:10px;padding:14px 16px;text-align:center}
.stat-num{font-size:26px;font-weight:600;color:#1a73e8}
.stat-label{font-size:12px;color:#6e6e73;margin-top:2px}

/* ── toast ── */
.toast{position:fixed;bottom:24px;right:24px;background:#1d1d1f;color:#fff;padding:11px 18px;border-radius:10px;font-size:13px;opacity:0;transition:opacity .25s;pointer-events:none;z-index:999}
.toast.show{opacity:1}

/* ── responsive ── */
@media(max-width:640px){
  .shell{flex-direction:column;height:auto}
  .sidebar{width:100%;height:auto;border-right:none;border-bottom:1px solid #e0e0e0}
  .nav{max-height:220px}
  .content{padding:20px 16px 40px}
}
</style>
</head>
<body>

<div class="shell">
  <!-- Sidebar navigation -->
  <div class="sidebar">
    <div class="sidebar-header">
      <h1>Tech Spec Survey</h1>
      <p id="doc-name" style="color:#8e8e93">No document loaded</p>
      <div class="progress-bar-wrap" style="margin-top:10px">
        <div class="progress-bar" id="progress-bar" style="width:0%"></div>
      </div>
    </div>
    <div class="nav" id="nav-tree"></div>
  </div>

  <!-- Main area -->
  <div class="main">
    <div id="app-root"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
/* ──────────────────────────────────────────────────────────────────────────
   State
   ────────────────────────────────────────────────────────────────────────── */
let TREE = null;          // full tree from server
let RESPONSES = {};       // {breadcrumb: {label: value}}
let CURRENT_ID = null;    // breadcrumb of section being edited

/* ──────────────────────────────────────────────────────────────────────────
   Boot - check if doc already loaded
   ────────────────────────────────────────────────────────────────────────── */
async function boot() {
  const res = await fetch('/api/state');
  const data = await res.json();
  if (data.tree) {
    TREE = data.tree;
    RESPONSES = data.responses || {};
    document.getElementById('doc-name').textContent = data.docx_name || '';
    buildNav();
    showWelcome();
  } else {
    showUpload();
  }
}

/* ──────────────────────────────────────────────────────────────────────────
   Upload screen
   ────────────────────────────────────────────────────────────────────────── */
function showUpload() {
  document.getElementById('nav-tree').innerHTML = '';
  document.getElementById('app-root').innerHTML = `
    <div class="upload-screen">
      <div class="upload-icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#1a73e8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <line x1="9" y1="15" x2="15" y2="15"/>
        </svg>
      </div>
      <h2>Load a Word document</h2>
      <p>Select a .docx questionnaire file. The app will parse its heading structure into an interactive survey.</p>
      <div class="upload-zone" onclick="document.getElementById('file-pick').click()">
        <input type="file" id="file-pick" accept=".docx" onchange="handleUpload(event)">
        <label>Click to choose a .docx file</label>
      </div>
      <p id="upload-status" style="font-size:13px;color:#6e6e73"></p>
    </div>`;
}

async function handleUpload(evt) {
  const file = evt.target.files[0];
  if (!file) return;
  document.getElementById('upload-status').textContent = 'Parsing document...';
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/load', {method:'POST', body: fd});
  const data = await res.json();
  if (data.ok) {
    TREE = data.tree;
    RESPONSES = {};
    document.getElementById('doc-name').textContent = file.name;
    buildNav();
    showWelcome();
    toast('Document loaded successfully');
  } else {
    document.getElementById('upload-status').textContent = 'Error: ' + data.error;
  }
}

/* ──────────────────────────────────────────────────────────────────────────
   Sidebar nav
   ────────────────────────────────────────────────────────────────────────── */
function buildNav() {
  const nav = document.getElementById('nav-tree');
  nav.innerHTML = '';

  // Summary link
  const sumLink = document.createElement('div');
  sumLink.className = 'nav-item';
  sumLink.style.fontWeight = '600';
  sumLink.innerHTML = `<span>Summary &amp; Export</span>`;
  sumLink.onclick = showSummary;
  nav.appendChild(sumLink);

  function addNode(node, depth) {
    if (!node.id) return; // skip root
    const el = document.createElement('div');
    el.className = `nav-item nav-indent-${Math.min(depth, 3)}`;
    el.dataset.id = node.id;

    const dot = document.createElement('span');
    dot.className = 'dot';
    const label = document.createElement('span');
    label.textContent = node.title;
    el.appendChild(label);
    el.appendChild(dot);

    el.onclick = () => {
      if (node.is_leaf) navigateTo(node.id);
      else showBranch(node);
    };
    nav.appendChild(el);

    if (node.children) node.children.forEach(c => addNode(c, depth + 1));
  }

  if (TREE && TREE.children) TREE.children.forEach(c => addNode(c, 1));
  updateNav();
}

function updateNav() {
  if (!TREE) return;
  let total = 0, done = 0;

  function countLeaves(node) {
    if (node.is_leaf && node.id) {
      total++;
      if (RESPONSES[node.id] && Object.keys(RESPONSES[node.id]).length > 0) done++;
    }
    if (node.children) node.children.forEach(countLeaves);
  }
  countLeaves(TREE);

  const pct = total > 0 ? Math.round(done / total * 100) : 0;
  const bar = document.getElementById('progress-bar');
  if (bar) bar.style.width = pct + '%';

  document.querySelectorAll('.nav-item[data-id]').forEach(el => {
    const id = el.dataset.id;
    el.classList.toggle('active', id === CURRENT_ID);
    const answered = RESPONSES[id] && Object.values(RESPONSES[id]).some(v =>
      Array.isArray(v) ? v.length > 0 : v && v.trim() !== '');
    el.classList.toggle('done', !!answered);
    const dot = el.querySelector('.dot');
    if (dot) dot.style.background = answered ? '#34c759' : (id === CURRENT_ID ? '#1a73e8' : '#d1d1d6');
  });
}

/* ──────────────────────────────────────────────────────────────────────────
   Welcome / branch screens
   ────────────────────────────────────────────────────────────────────────── */
function showWelcome() {
  CURRENT_ID = null;
  updateNav();
  const children = TREE ? TREE.children : [];
  const html = `
    <div class="content">
      <div class="page-header">
        <h2>Welcome</h2>
        <div class="breadcrumb">Select any section from the sidebar, or start from the top</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">
        ${children.map(c => `
          <div onclick="${c.is_leaf ? `navigateTo('${esc(c.id)}')` : `showBranch_byId('${esc(c.id)}')`}"
               style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:16px 18px;cursor:pointer;transition:box-shadow .15s"
               onmouseover="this.style.boxShadow='0 2px 12px rgba(0,0,0,.08)'" onmouseout="this.style.boxShadow=''">
            <div style="font-weight:600;font-size:14px;margin-bottom:4px">${esc(c.title)}</div>
            <div style="font-size:12px;color:#8e8e93">${c.children ? c.children.length + ' sub-sections' : c.fields.length + ' fields'}</div>
          </div>`).join('')}
      </div>
    </div>`;
  document.getElementById('app-root').innerHTML = html;
}

function showBranch(node) {
  CURRENT_ID = null;
  updateNav();
  const html = `
    <div class="content">
      <div class="page-header">
        <h2>${esc(node.title)}</h2>
        <div class="breadcrumb">${esc(node.id)}</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">
        ${node.children.map(c => {
          const done = RESPONSES[c.id] && Object.values(RESPONSES[c.id]).some(v =>
            Array.isArray(v) ? v.length > 0 : v && v.trim() !== '');
          return `
          <div onclick="${c.is_leaf ? `navigateTo('${esc(c.id)}')` : `showBranch_byId('${esc(c.id)}')`}"
               style="background:#fff;border:1px solid ${done ? '#34c759' : '#e0e0e0'};border-radius:10px;padding:16px 18px;cursor:pointer;transition:box-shadow .15s"
               onmouseover="this.style.boxShadow='0 2px 12px rgba(0,0,0,.08)'" onmouseout="this.style.boxShadow=''">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
              <div style="font-weight:600;font-size:14px">${esc(c.title)}</div>
              ${done ? '<span style="font-size:11px;background:#e8f8ed;color:#1a7a35;padding:2px 8px;border-radius:20px">done</span>' : ''}
            </div>
            <div style="font-size:12px;color:#8e8e93">${c.children ? c.children.length + ' sub-sections' : c.fields.length + ' fields'}</div>
          </div>`;
        }).join('')}
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="fillAllChildren('${esc(node.id)}')">Fill all sections in order</button>
      </div>
    </div>`;
  document.getElementById('app-root').innerHTML = html;
}

function showBranch_byId(id) {
  const node = findNode(id);
  if (node) showBranch(node);
}

/* ──────────────────────────────────────────────────────────────────────────
   Leaf form
   ────────────────────────────────────────────────────────────────────────── */
function navigateTo(id) {
  const node = findNode(id);
  if (!node) return;
  CURRENT_ID = id;
  updateNav();

  const saved = RESPONSES[id] || {};

  const fieldsHtml = node.fields.map((f, fi) => {
    const savedVal = saved[f.label];
    if (f.type === 'checkbox') {
      const selectedSet = new Set(Array.isArray(savedVal) ? savedVal : []);
      const optHtml = f.options.map((opt, oi) => {
        const checked = selectedSet.has(opt);
        return `
          <div class="option-pill ${checked ? 'selected' : ''}" id="pill-${fi}-${oi}" onclick="togglePill(${fi},${oi})">
            <input type="checkbox" id="cb-${fi}-${oi}" ${checked ? 'checked' : ''} onclick="event.stopPropagation();togglePill(${fi},${oi})">
            <span>${esc(opt)}</span>
          </div>`;
      }).join('');
      return `
        <div class="field-group" data-fi="${fi}" data-type="checkbox" data-label="${esc(f.label)}">
          <div class="field-label">${esc(f.label)}</div>
          <div class="options-grid">${optHtml}</div>
        </div>`;
    } else {
      const val = typeof savedVal === 'string' ? savedVal : '';
      const isLong = f.label.length > 60;
      return `
        <div class="field-group" data-fi="${fi}" data-type="text" data-label="${esc(f.label)}">
          <div class="field-label">${esc(f.label)}</div>
          ${isLong
            ? `<textarea id="input-${fi}" rows="2">${esc(val)}</textarea>`
            : `<input type="text" id="input-${fi}" value="${esc(val)}" placeholder="Enter your answer...">`}
        </div>`;
    }
  }).join('');

  // Prev / Next sibling navigation
  const siblings = getSiblings(id);
  const idx = siblings.findIndex(s => s.id === id);
  const prevId = idx > 0 ? siblings[idx-1].id : null;
  const nextId = idx < siblings.length - 1 ? siblings[idx+1].id : null;

  document.getElementById('app-root').innerHTML = `
    <div class="content">
      <div class="page-header">
        <h2>${esc(node.title)}</h2>
        <div class="breadcrumb">${esc(node.id)}</div>
      </div>
      ${fieldsHtml || '<p style="color:#8e8e93;font-size:14px">No input fields in this section.</p>'}
      <div class="btn-row">
        <button class="btn btn-primary" onclick="saveSection('${esc(id)}', ${nextId ? `'${esc(nextId)}'` : 'null'})">
          ${nextId ? 'Save &amp; Next' : 'Save'}
        </button>
        ${prevId ? `<button class="btn btn-secondary" onclick="navigateTo('${esc(prevId)}')">Previous</button>` : ''}
        <button class="btn btn-secondary" onclick="showWelcome()">Back to menu</button>
      </div>
    </div>`;
}

/* ──────────────────────────────────────────────────────────────────────────
   Toggle checkbox pills
   ────────────────────────────────────────────────────────────────────────── */
function togglePill(fi, oi) {
  const pill = document.getElementById(`pill-${fi}-${oi}`);
  const cb   = document.getElementById(`cb-${fi}-${oi}`);
  if (!pill || !cb) return;
  cb.checked = !cb.checked;
  pill.classList.toggle('selected', cb.checked);
}

/* ──────────────────────────────────────────────────────────────────────────
   Save section
   ────────────────────────────────────────────────────────────────────────── */
async function saveSection(id, nextId) {
  const data = {};
  document.querySelectorAll('.field-group').forEach(fg => {
    const label = fg.dataset.label;
    const type  = fg.dataset.type;
    const fi    = fg.dataset.fi;
    if (type === 'checkbox') {
      const vals = [];
      fg.querySelectorAll('input[type=checkbox]:checked').forEach(cb => {
        const span = cb.closest('.option-pill').querySelector('span');
        if (span) vals.push(span.textContent);
      });
      data[label] = vals;
    } else {
      const inp = document.getElementById(`input-${fi}`);
      data[label] = inp ? inp.value.trim() : '';
    }
  });

  const res = await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id, data})
  });
  const result = await res.json();
  if (result.ok) {
    RESPONSES[id] = data;
    updateNav();
    toast('Section saved');
    if (nextId) navigateTo(nextId);
  }
}

/* ──────────────────────────────────────────────────────────────────────────
   Fill all children in order
   ────────────────────────────────────────────────────────────────────────── */
function fillAllChildren(branchId) {
  const node = findNode(branchId);
  if (!node) return;
  const leaves = [];
  function collect(n) {
    if (n.is_leaf && n.id) leaves.push(n.id);
    if (n.children) n.children.forEach(collect);
  }
  collect(node);
  if (leaves.length) navigateTo(leaves[0]);
}

/* ──────────────────────────────────────────────────────────────────────────
   Summary & Export
   ────────────────────────────────────────────────────────────────────────── */
function showSummary() {
  CURRENT_ID = null;
  updateNav();

  let totalSections = 0, totalFields = 0, answeredFields = 0;
  const cardsHtml = Object.entries(RESPONSES).map(([sec, fields]) => {
    totalSections++;
    const rows = Object.entries(fields).map(([k, v]) => {
      totalFields++;
      const isEmpty = Array.isArray(v) ? v.length === 0 : !v;
      if (!isEmpty) answeredFields++;
      const display = Array.isArray(v) ? v.join(', ') : v;
      return `<div class="summary-row">
        <div class="summary-key">${esc(k)}</div>
        <div class="summary-val" style="color:${isEmpty ? '#c7c7cc' : '#1d1d1f'}">${isEmpty ? 'not answered' : esc(display)}</div>
      </div>`;
    }).join('');
    return `<div class="summary-card"><h3>${esc(sec)}</h3>${rows}</div>`;
  }).join('');

  const pct = totalFields > 0 ? Math.round(answeredFields / totalFields * 100) : 0;

  document.getElementById('app-root').innerHTML = `
    <div class="content">
      <div class="page-header"><h2>Summary &amp; Export</h2></div>
      <div class="stat-row">
        <div class="stat"><div class="stat-num">${totalSections}</div><div class="stat-label">sections visited</div></div>
        <div class="stat"><div class="stat-num">${answeredFields}/${totalFields}</div><div class="stat-label">fields answered</div></div>
        <div class="stat"><div class="stat-num">${pct}%</div><div class="stat-label">completion</div></div>
      </div>
      ${cardsHtml || '<p style="color:#8e8e93">No answers recorded yet.</p>'}
      <div class="btn-row">
        <button class="btn btn-success" onclick="exportJSON()">Export JSON</button>
        <button class="btn btn-secondary" onclick="exportCSV()">Export CSV</button>
      </div>
    </div>`;
}

async function exportJSON() {
  const res = await fetch('/api/export/json');
  const blob = await res.blob();
  triggerDownload(blob, 'survey_responses.json');
  toast('JSON exported');
}

async function exportCSV() {
  const res = await fetch('/api/export/csv');
  const blob = await res.blob();
  triggerDownload(blob, 'survey_responses.csv');
  toast('CSV exported');
}

function triggerDownload(blob, filename) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

/* ──────────────────────────────────────────────────────────────────────────
   Utilities
   ────────────────────────────────────────────────────────────────────────── */
function findNode(id) {
  function search(node) {
    if (node.id === id) return node;
    for (const c of (node.children || [])) {
      const found = search(c);
      if (found) return found;
    }
    return null;
  }
  return TREE ? search(TREE) : null;
}

function getSiblings(id) {
  // Collect all leaves in document order
  const leaves = [];
  function collect(node) {
    if (node.is_leaf && node.id) leaves.push(node);
    if (node.children) node.children.forEach(collect);
  }
  if (TREE) collect(TREE);
  return leaves;
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

let toastTimer;
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
}

/* ── Boot ── */
boot();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/state")
def api_state():
    """Return current app state (tree + saved responses)."""
    if STATE["tree"] is None:
        return jsonify({"tree": None, "responses": {}})
    return jsonify({
        "tree": STATE["tree"].to_dict(),
        "docx_name": os.path.basename(STATE["docx_path"]),
        "responses": STATE["responses"],
        "ok": True,
    })


@app.route("/api/load", methods=["POST"])
def api_load():
    """Receive an uploaded .docx file, parse it, and store the tree."""
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "No file received"}), 400

    tmp_path = f"/tmp/survey_upload_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    f.save(tmp_path)

    try:
        root = parse_document(tmp_path)
        STATE["tree"] = root
        STATE["docx_path"] = tmp_path
        STATE["responses"] = {}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        STATE["output_path"] = f"survey_responses_{ts}.json"
        return jsonify({"ok": True, "tree": root.to_dict()})
    except Exception as exc:
        import traceback
        return jsonify({"ok": False, "error": str(exc),
                        "traceback": traceback.format_exc()}), 500


@app.route("/api/save", methods=["POST"])
def api_save():
    """Save answers for one section."""
    body = request.get_json()
    section_id = body.get("id", "")
    data = body.get("data", {})
    STATE["responses"][section_id] = data
    # Auto-persist to disk
    _write_json()
    return jsonify({"ok": True})


def _write_json():
    path = STATE["output_path"]
    if not path:
        return
    payload = {
        "generated_at": datetime.now().isoformat(),
        "source": "survey_ui",
        "docx": os.path.basename(STATE["docx_path"]),
        "responses": STATE["responses"],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


@app.route("/api/export/json")
def api_export_json():
    """Download the full responses as JSON."""
    payload = {
        "generated_at": datetime.now().isoformat(),
        "responses": STATE["responses"],
    }
    from flask import Response
    return Response(
        json.dumps(payload, indent=2, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=survey_responses.json"},
    )


@app.route("/api/export/csv")
def api_export_csv():
    """Download a flat CSV of all answers."""
    import csv, io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Section", "Field", "Answer"])
    for section, fields in STATE["responses"].items():
        for label, value in fields.items():
            if isinstance(value, list):
                value = "; ".join(value)
            writer.writerow([section, label, value])
    from flask import Response
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=survey_responses.csv"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Web-based survey UI for Word documents"
    )
    parser.add_argument("--docx", default=None, help="Pre-load a .docx file")
    parser.add_argument("--port", type=int, default=5000, help="HTTP port (default 5000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args()

    # Pre-load a docx if specified on the command line
    if args.docx:
        docx_path = args.docx
        if not os.path.exists(docx_path):
            sys.exit(f"File not found: {docx_path}")
        root = parse_document(docx_path)
        STATE["tree"] = root
        STATE["docx_path"] = docx_path
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        STATE["output_path"] = f"survey_responses_{ts}.json"
        print(f"Loaded: {docx_path}  ({len(root.children)} top-level sections)")
    else:
        # Auto-detect
        candidates = sorted(Path(".").glob("*.docx"))
        if candidates:
            docx_path = str(candidates[0])
            root = parse_document(docx_path)
            STATE["tree"] = root
            STATE["docx_path"] = docx_path
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            STATE["output_path"] = f"survey_responses_{ts}.json"
            print(f"Auto-loaded: {docx_path}")

    url = f"http://localhost:{args.port}"
    print(f"\n  Survey UI running at  {url}")
    print("  Press Ctrl-C to stop.\n")

    if not args.no_browser:
        Timer(0.8, lambda: webbrowser.open(url)).start()

    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
