"""
File Collector — PySide6 GUI (v2 — file-level selection)
========================================================
- Red/Black theme
- SQLite storage for projects, folder + file decisions, per-project options
- Cascade checkbox tree (parent <-> children, partial-aware)
- Per-file selection + per-extension selection
- .gitignore awareness
- Output formats: compact (AI-friendly), minimal, verbose
- Live token estimate
"""

import os
import sys
import re
import json
import sqlite3
import platform
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QColor, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QStatusBar, QFrame, QProgressBar, QAbstractItemView,
    QPlainTextEdit, QComboBox, QCheckBox, QGroupBox, QSpinBox, QGridLayout,
    QScrollArea, QToolButton,
)

# ============================================================
# CONSTANTS
# ============================================================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects.db")

SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env",
    "node_modules", ".idea", ".vscode", "build", "dist",
    ".mypy_cache", ".pytest_cache", ".tox", "site-packages",
}

FILE_TYPE_GROUPS = [
    ("Python",          [(".py", True), (".pyi", True), (".pyx", False)]),
    ("Web / JS / TS",   [(".js", True), (".jsx", True), (".ts", True),
                         (".tsx", True), (".mjs", False), (".cjs", False),
                         (".vue", False), (".svelte", False)]),
    ("Markup / Styles", [(".html", True), (".htm", True), (".css", True),
                         (".scss", True), (".sass", False), (".less", False)]),
    ("Data / Config",   [(".json", True), (".yaml", True), (".yml", True),
                         (".toml", True), (".ini", True), (".cfg", True),
                         (".env", False)]),
    ("Docs / Text",     [(".md", True), (".rst", False), (".txt", True)]),
    ("Shell / Build",   [(".sh", True), (".bash", False), (".zsh", False),
                         (".ps1", False), (".bat", False), (".cmd", False)]),
    ("C / C++ / ObjC",  [(".c", True), (".h", True), (".cpp", True),
                         (".hpp", True), (".cc", False), (".hh", False),
                         (".m", False), (".mm", False)]),
    ("JVM / Kotlin",    [(".java", True), (".kt", True), (".kts", False),
                         (".scala", False), (".groovy", False)]),
    ("C# / .NET",       [(".cs", True), (".fs", False), (".vb", False)]),
    ("Go / Rust / Zig", [(".go", True), (".rs", True), (".zig", False)]),
    ("Ruby / PHP",      [(".rb", False), (".php", False)]),
    ("SQL",             [(".sql", True)]),
]

DEFAULT_EXTENSIONS = [e for _, items in FILE_TYPE_GROUPS for e, on in items if on]

DEFAULT_OPTIONS = {
    "format_mode": "compact",
    "skip_empty_init": True,
    "collapse_blank": True,
    "strip_docstrings": False,
    "respect_gitignore": True,
    "max_file_kb": 0,
    "skip_common_files": True,
    "extensions": list(DEFAULT_EXTENSIONS),
    "show_all_files": False,   # اگر True: همه فایل‌ها در درخت نمایش داده شوند
}

DARK_QSS = """
* { font-family: 'Segoe UI', 'Inter', 'Noto Sans', sans-serif; font-size: 10pt; }
QMainWindow, QWidget { background-color: #0d0d0f; color: #e8e8ea; }

QFrame#Card { background-color: #16161a; border: 1px solid #2a2a30; border-radius: 10px; }

QLabel#Title { font-size: 13pt; font-weight: 700; color: #ffffff; }
QLabel#Subtitle { color: #8a8a92; }
QLabel#SectionTitle { font-weight: 600; color: #d8d8dc; }

QPushButton {
    background-color: #1f1f24; color: #e8e8ea;
    border: 1px solid #34343c; border-radius: 8px; padding: 7px 14px;
}
QPushButton:hover { background-color: #2a2a31; border-color: #d7263d; }
QPushButton:pressed { background-color: #1a1a1f; }
QPushButton:disabled { color: #55555c; background-color: #141418; border-color: #26262c; }

QPushButton#Primary {
    background-color: #d7263d; color: #ffffff; border: 1px solid #d7263d; font-weight: 700;
}
QPushButton#Primary:hover { background-color: #e33b52; border-color: #e33b52; }
QPushButton#Primary:pressed { background-color: #b51e32; }
QPushButton#Primary:disabled { background-color: #4a1a22; border-color: #4a1a22; color: #8a8a92; }

QPushButton#Danger { color: #ff6b7a; border-color: #4a1f25; }
QPushButton#Danger:hover { background-color: #2e1418; border-color: #ff6b7a; }

QPushButton#Success {
    background-color: #1e7a3f; color: #ffffff; border: 1px solid #1e7a3f; font-weight: 600;
}
QPushButton#Success:hover { background-color: #248f4a; border-color: #248f4a; }
QPushButton#Success:disabled { background-color: #1a3a24; border-color: #1a3a24; color: #6a8a72; }

QPushButton#Mini { padding: 3px 10px; font-size: 9pt; border-radius: 6px; }

QLineEdit, QSpinBox, QComboBox {
    background-color: #0d0d0f; border: 1px solid #34343c; border-radius: 8px;
    padding: 6px 10px; selection-background-color: #d7263d;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #d7263d; }
QLineEdit:read-only { color: #8a8a92; background-color: #121216; }

QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: #16161a; border: 1px solid #34343c;
    selection-background-color: #d7263d; outline: 0;
}

QListWidget {
    background-color: #0d0d0f; border: 1px solid #2a2a30; border-radius: 8px;
    padding: 4px; outline: 0;
}
QListWidget::item { padding: 8px 10px; border-radius: 6px; margin: 1px 2px; }
QListWidget::item:hover { background-color: #1f1f24; }
QListWidget::item:selected { background-color: #d7263d; color: #ffffff; }

QTreeWidget {
    background-color: #0d0d0f; border: 1px solid #2a2a30; border-radius: 8px; outline: 0;
}
QTreeWidget::item { padding: 3px 2px; }
QTreeWidget::item:hover { background-color: #1a1a1f; }
QTreeWidget::item:selected { background-color: #3a1418; }
QTreeWidget::branch { background: transparent; }
QHeaderView::section {
    background-color: #16161a; color: #8a8a92;
    border: none; border-bottom: 1px solid #2a2a30;
    padding: 6px 8px; font-weight: 600;
}

QTreeView::indicator { width: 16px; height: 16px; }
QTreeView::indicator:unchecked {
    background-color: #0d0d0f; border: 1px solid #34343c; border-radius: 3px;
}
QTreeView::indicator:unchecked:hover { border-color: #d7263d; }
QTreeView::indicator:checked {
    background-color: #d7263d; border: 1px solid #d7263d; border-radius: 3px;
}
QTreeView::indicator:indeterminate {
    background-color: #6b1a26; border: 1px solid #d7263d; border-radius: 3px;
}

QCheckBox { spacing: 8px; color: #d8d8dc; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; }
QCheckBox::indicator:unchecked { background-color: #0d0d0f; border: 1px solid #34343c; }
QCheckBox::indicator:unchecked:hover { border-color: #d7263d; }
QCheckBox::indicator:checked { background-color: #d7263d; border: 1px solid #d7263d; }
QCheckBox::indicator:indeterminate { background-color: #6b1a26; border: 1px solid #d7263d; }

QGroupBox {
    border: 1px solid #2a2a30; border-radius: 8px;
    margin-top: 12px; padding: 10px 8px 8px 8px;
    font-weight: 600; color: #d8d8dc;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 10px; padding: 0 6px; color: #d7263d;
}

QScrollBar:vertical { background: #0d0d0f; width: 10px; margin: 0; border-radius: 5px; }
QScrollBar::handle:vertical { background: #34343c; border-radius: 5px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #d7263d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #0d0d0f; height: 10px; border-radius: 5px; }
QScrollBar::handle:horizontal { background: #34343c; border-radius: 5px; min-width: 20px; }
QScrollBar::handle:horizontal:hover { background: #d7263d; }

QStatusBar { background-color: #0a0a0c; color: #8a8a92; border-top: 1px solid #2a2a30; }

QProgressBar { background-color: #1f1f24; border: none; border-radius: 4px; height: 6px; }
QProgressBar::chunk { background-color: #d7263d; border-radius: 4px; }

QDialog { background-color: #0d0d0f; }
QSplitter::handle { background-color: #0d0d0f; }
QSplitter::handle:hover { background-color: #d7263d; }

QPlainTextEdit, QTextEdit {
    background-color: #0d0d0f; color: #e8e8ea;
    border: 1px solid #2a2a30; border-radius: 8px;
    selection-background-color: #d7263d;
}
"""

# ============================================================
# HELPERS
# ============================================================


def _matches_ext(fname: str, extensions: set) -> bool:
    """True if fname matches one of the selected extensions.
    Handles exact names too (e.g. 'dockerfile', 'makefile')."""
    name = fname.lower()
    if name in extensions:
        return True
    _, ext = os.path.splitext(name)
    return ext in extensions


# ============================================================
# GITIGNORE PARSER
# ============================================================


class GitIgnoreMatcher:
    def __init__(self):
        self.patterns = []

    @classmethod
    def load(cls, root_dir):
        path = os.path.join(root_dir, ".gitignore")
        if not os.path.isfile(path):
            return None
        m = cls()
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.rstrip("\n").rstrip("\r")
                if not s or s.lstrip().startswith("#"):
                    continue
                negated = s.startswith("!")
                if negated:
                    s = s[1:]
                dir_only = s.endswith("/")
                if dir_only:
                    s = s.rstrip("/")
                if not s:
                    continue
                regex = cls._pattern_to_regex(s)
                m.patterns.append((re.compile(regex), negated, dir_only))
        return m

    @staticmethod
    def _pattern_to_regex(pat):
        anchored = pat.startswith("/")
        if anchored:
            pat = pat[1:]
        parts = []
        i = 0
        while i < len(pat):
            c = pat[i]
            if c == "*":
                if i + 1 < len(pat) and pat[i + 1] == "*":
                    parts.append(".*")
                    i += 2
                    if i < len(pat) and pat[i] == "/":
                        i += 1
                else:
                    parts.append("[^/]*")
                    i += 1
            elif c == "?":
                parts.append("[^/]")
                i += 1
            else:
                parts.append(re.escape(c))
                i += 1
        body = "".join(parts)
        if anchored:
            return "^" + body + "(/.*)?$"
        else:
            return "(^|/)" + body + "(/.*)?$"

    def is_ignored(self, rel_path):
        rel_path = rel_path.replace(os.sep, "/").strip("/")
        if not rel_path:
            return False
        ignored = False
        for regex, negated, dir_only in self.patterns:
            if regex.search(rel_path) or (dir_only and regex.search(rel_path + "/")):
                ignored = not negated
        return ignored


# ============================================================
# DATABASE
# ============================================================


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    root_path TEXT NOT NULL,
                    output_file TEXT,
                    options_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS folder_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    folder_path TEXT NOT NULL,
                    include INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(project_id, folder_path)
                );

                CREATE TABLE IF NOT EXISTS file_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    include INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(project_id, file_path)
                );
            """)

    def create_project(self, name, root_path, output_file="", options=None):
        options = options or DEFAULT_OPTIONS.copy()
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects (name, root_path, output_file, options_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, root_path, output_file, json.dumps(options), now, now),
            )
            return cur.lastrowid

    def update_project(self, project_id, name=None, root_path=None, output_file=None, options=None):
        now = datetime.now().isoformat(timespec="seconds")
        fields, values = ["updated_at = ?"], [now]
        if name is not None:
            fields.append("name = ?"); values.append(name)
        if root_path is not None:
            fields.append("root_path = ?"); values.append(root_path)
        if output_file is not None:
            fields.append("output_file = ?"); values.append(output_file)
        if options is not None:
            fields.append("options_json = ?"); values.append(json.dumps(options))
        values.append(project_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", values)

    def delete_project(self, project_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM file_decisions WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM folder_decisions WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def get_project(self, project_id):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["options"] = self._parse_options(d.get("options_json"))
            return d

    def list_projects(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["options"] = self._parse_options(d.get("options_json"))
                result.append(d)
            return result

    @staticmethod
    def _parse_options(s):
        opts = DEFAULT_OPTIONS.copy()
        if s:
            try:
                opts.update(json.loads(s))
            except Exception:
                pass
        for k, v in DEFAULT_OPTIONS.items():
            opts.setdefault(k, v)
        return opts

    def set_folder_decision(self, project_id, folder_path, include):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO folder_decisions (project_id, folder_path, include) VALUES (?, ?, ?) "
                "ON CONFLICT(project_id, folder_path) DO UPDATE SET include = excluded.include",
                (project_id, folder_path, 1 if include else 0),
            )

    def get_folder_decisions(self, project_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT folder_path, include FROM folder_decisions WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            return {r["folder_path"]: bool(r["include"]) for r in rows}

    def set_file_decision(self, project_id, file_path, include):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO file_decisions (project_id, file_path, include) VALUES (?, ?, ?) "
                "ON CONFLICT(project_id, file_path) DO UPDATE SET include = excluded.include",
                (project_id, file_path, 1 if include else 0),
            )

    def get_file_decisions(self, project_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT file_path, include FROM file_decisions WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            return {r["file_path"]: bool(r["include"]) for r in rows}

    def export_project_json(self, project_id, json_path):
        p = self.get_project(project_id)
        p["folders"] = self.get_folder_decisions(project_id)
        p["files"] = self.get_file_decisions(project_id)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)

    def import_project_json(self, json_path):
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        base_name = data.get("name", "imported")
        name = base_name
        i = 2
        while True:
            try:
                pid = self.create_project(
                    name, data["root_path"],
                    data.get("output_file", ""),
                    data.get("options") or DEFAULT_OPTIONS,
                )
                break
            except sqlite3.IntegrityError:
                name = f"{base_name} ({i})"; i += 1
        for rel, inc in data.get("folders", {}).items():
            self.set_folder_decision(pid, rel, inc)
        for rel, inc in data.get("files", {}).items():
            self.set_file_decision(pid, rel, inc)
        return pid


# ============================================================
# COLLECTOR
# ============================================================


def scan_tree_entries(root_dir, extensions, show_all_files=False):
    """Return ordered list of (rel_path, is_dir).
    Files are included if extension matches (or show_all_files=True)."""
    root_dir = os.path.abspath(root_dir)
    exts = {e.lower() for e in extensions}
    result = []
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        rel = os.path.relpath(dirpath, root_dir)
        rel_norm = "." if rel == "." else rel.replace(os.sep, "/")
        result.append((rel_norm, True))
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)

        for fname in sorted(filenames):
            if show_all_files or _matches_ext(fname, exts):
                frel = fname if rel_norm == "." else f"{rel_norm}/{fname}"
                result.append((frel, False))
    return result


def count_selected_files(root_dir, include_map, options=None, file_map=None):
    options = options or DEFAULT_OPTIONS
    file_map = file_map or {}
    root_dir = os.path.abspath(root_dir)
    exts = {e.lower() for e in options.get("extensions", DEFAULT_EXTENSIONS)}
    counter = 0
    max_kb = options.get("max_file_kb", 0) or 0
    skip_empty_init = options.get("skip_empty_init", True)

    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        rel = os.path.relpath(dirpath, root_dir)
        rel_norm = "." if rel == "." else rel.replace(os.sep, "/")
        if rel_norm != "." and include_map.get(rel_norm, True) is False:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in filenames:
            if not _matches_ext(fname, exts):
                continue
            frel = fname if rel_norm == "." else f"{rel_norm}/{fname}"
            if file_map.get(frel, True) is False:
                continue
            fpath = os.path.join(dirpath, fname)
            if max_kb:
                try:
                    if os.path.getsize(fpath) > max_kb * 1024:
                        continue
                except OSError:
                    continue
            if skip_empty_init and fname == "__init__.py":
                try:
                    if os.path.getsize(fpath) == 0:
                        continue
                except OSError:
                    pass
            counter += 1
    return counter


def _strip_docstrings(source):
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    try:
        return ast.unparse(tree)
    except Exception:
        return source


def collect_python_files(root_dir, output_file, include_map, progress_cb=None,
                         options=None, file_map=None):
    options = options or DEFAULT_OPTIONS
    file_map = file_map or {}
    root_dir = os.path.abspath(root_dir)
    output_file = os.path.abspath(output_file)

    format_mode = options.get("format_mode", "compact")
    skip_empty_init = options.get("skip_empty_init", True)
    collapse_blank = options.get("collapse_blank", True)
    strip_docstrings = options.get("strip_docstrings", False)
    max_kb = options.get("max_file_kb", 0) or 0
    exts = {e.lower() for e in options.get("extensions", DEFAULT_EXTENSIONS)}

    py_files = []
    skipped_dirs = []

    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        rel = os.path.relpath(dirpath, root_dir)
        rel_norm = "." if rel == "." else rel.replace(os.sep, "/")
        if rel_norm != "." and include_map.get(rel_norm, True) is False:
            skipped_dirs.append(rel_norm)
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if _matches_ext(fname, exts):
                frel = fname if rel_norm == "." else f"{rel_norm}/{fname}"
                if file_map.get(frel, True) is False:
                    continue
                py_files.append(os.path.join(dirpath, fname))

    py_files.sort()
    if not py_files:
        return 0, 0, skipped_dirs

    total_bytes = 0
    included = 0
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as out:
        if format_mode == "verbose":
            out.write("=" * 80 + "\n")
            out.write("Aggregated Source Files\n")
            out.write(f"Root : {root_dir}\n")
            out.write(f"Files: {len(py_files)}\n")
            out.write(f"Types: {', '.join(sorted(exts))}\n")
            out.write(f"Time : {datetime.now().isoformat(timespec='seconds')}\n")
            out.write("=" * 80 + "\n\n")
        elif format_mode == "compact":
            out.write(f"# Project — {len(py_files)} files\n\n")
        else:
            out.write(f"# {len(py_files)} files\n\n")

        for i, path in enumerate(py_files):
            rel_path = os.path.relpath(path, root_dir).replace(os.sep, "/")

            if max_kb:
                try:
                    if os.path.getsize(path) > max_kb * 1024:
                        out.write(f"### {rel_path}\n[SKIPPED: > {max_kb} KB]\n\n")
                        continue
                except OSError:
                    pass

            if skip_empty_init and os.path.basename(path) == "__init__.py":
                try:
                    if os.path.getsize(path) == 0:
                        continue
                except OSError:
                    pass

            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(path, "r", encoding="latin-1") as f:
                        content = f.read()
                except Exception as e:
                    out.write(f"### {rel_path}\n[ERROR: {e}]\n\n")
                    continue

            if strip_docstrings and path.lower().endswith((".py", ".pyi")):
                content = _strip_docstrings(content)

            if collapse_blank:
                content = re.sub(r"\n{3,}", "\n\n", content)

            total_bytes += len(content.encode("utf-8"))
            included += 1

            if format_mode == "verbose":
                out.write(f"\n{'=' * 80}\nFile : {path}\nRel  : {rel_path}\n"
                          f"Size : {len(content)} chars\n{'=' * 80}\n")
            elif format_mode == "compact":
                out.write(f"### {rel_path}\n")
            else:
                out.write(f"# {rel_path}\n")

            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")
            out.write("\n")

            if progress_cb:
                progress_cb(i + 1, len(py_files))

    return included, total_bytes, skipped_dirs


# ============================================================
# DIALOGS
# ============================================================


class NewProjectDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.result_project = None
        self.setWindowTitle("New Project")
        self.setMinimumWidth(520)
        self.setStyleSheet(DARK_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Create a new project")
        title.setObjectName("Title")
        layout.addWidget(title)

        sub = QLabel("Point to a folder — its files can then be aggregated.")
        sub.setObjectName("Subtitle")
        layout.addWidget(sub)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My Project")
        form.addRow("Name:", self.name_edit)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/path/to/code")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_btn)
        path_wrap = QWidget(); path_wrap.setLayout(path_row)
        form.addRow("Root folder:", path_wrap)

        layout.addLayout(form)

        btns = QDialogButtonBox()
        create_btn = btns.addButton("Create", QDialogButtonBox.AcceptRole)
        create_btn.setObjectName("Primary")
        btns.addButton("Cancel", QDialogButtonBox.RejectRole)
        btns.accepted.connect(self._create)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select root folder")
        if path:
            self.path_edit.setText(path)
            if not self.name_edit.text().strip():
                self.name_edit.setText(os.path.basename(path) or "project")

    def _create(self):
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing", "Please enter a project name.")
            return
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "Missing", "Please choose a valid root folder.")
            return
        try:
            pid = self.db.create_project(
                name, path,
                os.path.join(os.path.dirname(path), "all_files.txt"),
                DEFAULT_OPTIONS.copy(),
            )
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", "A project with that name already exists.")
            return
        self.result_project = self.db.get_project(pid)
        self.accept()


class TextViewerDialog(QDialog):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Output — {os.path.basename(file_path)}")
        self.resize(1000, 720)
        self.setStyleSheet(DARK_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("📄  Generated Output")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch()
        self.info_lbl = QLabel("")
        self.info_lbl.setObjectName("Subtitle")
        header.addWidget(self.info_lbl)
        layout.addLayout(header)

        path_row = QHBoxLayout()
        path_lbl = QLabel("Path:")
        path_lbl.setObjectName("Subtitle")
        path_lbl.setFixedWidth(40)
        path_edit = QLineEdit(file_path)
        path_edit.setReadOnly(True)
        path_row.addWidget(path_lbl)
        path_row.addWidget(path_edit, 1)
        layout.addLayout(path_row)

        search_row = QHBoxLayout()
        search_lbl = QLabel("🔍")
        search_lbl.setFixedWidth(24)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search in file… (Enter for next)")
        self.search_edit.returnPressed.connect(self._on_search)
        self.match_lbl = QLabel("")
        self.match_lbl.setObjectName("Subtitle")
        self.match_lbl.setFixedWidth(90)
        search_row.addWidget(search_lbl)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.match_lbl)
        layout.addLayout(search_row)

        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        mono = QFont("Consolas", 10)
        mono.setStyleHint(QFont.Monospace)
        self.text_view.setFont(mono)
        layout.addWidget(self.text_view, 1)

        btns = QHBoxLayout()
        open_btn = QPushButton("📂  Open in Default App")
        open_btn.clicked.connect(self._open_external)
        copy_btn = QPushButton("📋  Copy Path")
        copy_btn.clicked.connect(self._copy_path)
        refresh_btn = QPushButton("🔄  Reload")
        refresh_btn.clicked.connect(self._reload)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("Primary")
        close_btn.clicked.connect(self.accept)

        btns.addWidget(open_btn)
        btns.addWidget(copy_btn)
        btns.addWidget(refresh_btn)
        btns.addStretch()
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        self._matches = []
        self._match_idx = -1
        self._reload()

        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

    def _reload(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            self.text_view.setPlainText(text)
            size = len(text.encode("utf-8"))
            n_lines = self.text_view.blockCount()
            tokens_est = max(1, size // 4)
            self.info_lbl.setText(
                f"{size/1024:.1f} KB  ·  {n_lines} lines  ·  ~{tokens_est:,} tokens"
            )
        except Exception as e:
            QMessageBox.critical(self, "Reload failed", str(e))

    def _copy_path(self):
        QApplication.clipboard().setText(self.file_path)
        self.match_lbl.setText("Copied ✓")

    def _open_external(self):
        try:
            if platform.system() == "Windows":
                os.startfile(self.file_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.file_path])
            else:
                subprocess.Popen(["xdg-open", self.file_path])
        except Exception as e:
            QMessageBox.warning(self, "Could not open", str(e))

    def _on_search(self):
        term = self.search_edit.text()
        if not term:
            self._matches = []
            self.match_lbl.setText("")
            return
        text = self.text_view.toPlainText()
        low_text, low_term = text.lower(), term.lower()
        self._matches = []
        start = 0
        while True:
            i = low_text.find(low_term, start)
            if i < 0:
                break
            self._matches.append(i)
            start = i + 1
        if not self._matches:
            self.match_lbl.setText("0 matches")
            return
        self._match_idx = (self._match_idx + 1) % len(self._matches)
        pos = self._matches[self._match_idx]
        cursor = self.text_view.textCursor()
        cursor.setPosition(pos)
        cursor.setPosition(pos + len(term), cursor.MoveMode.KeepAnchor)
        self.text_view.setTextCursor(cursor)
        self.text_view.centerCursor()
        self.match_lbl.setText(f"{self._match_idx + 1}/{len(self._matches)}")


# ============================================================
# HELP DIALOG
# ============================================================

FAQ_ITEMS = [
    ("این برنامه چه کاری انجام می‌دهد؟",
     "فایل‌های یک پروژه‌ی کدنویسی را در یک <b>فایل متنی واحد</b> جمع می‌کند تا به AI بدهید."),
    ("چطور فقط یک فایل خاص را انتخاب کنم؟",
     "در درخت <b>Folders</b>، پوشه‌ها را باز کنید تا فایل‌ها نمایان شوند؛ "
     "سپس تیک فایل مورد نظر را بردارید/بزنید. والدها به‌صورت خودکار "
     "وضعیت <b>➖ (partial)</b> می‌گیرند."),
    ("منظور از تیک‌های درخت چیست؟",
     "✅ = شامل شود · ⬜ = حذف شود · ➖ = برخی فرزندان شامل هستند.<br>"
     "تیک زدن/برداشتن روی همه‌ی زیرشاخه‌ها (پوشه و فایل) اعمال می‌شود."),
    ("چرا بعضی فایل‌ها در درخت نیستند؟",
     "فقط فایل‌هایی نمایش داده می‌شوند که پسوندشان در بخش <b>File types</b> فعال است. "
     "برای دیدن همه‌ی فایل‌ها گزینه‌ی <b>Show all files</b> را در تنظیمات روشن کنید."),
    ("دکمه‌ی Expand / Collapse چه می‌کند؟",
     "همه‌ی پوشه‌ها را باز یا بسته می‌کند تا سریع‌تر فایل مورد نظر را پیدا کنید."),
    ("تفاوت Compact / Minimal / Verbose چیست؟",
     "<b>Compact</b> (پیشنهادی): سرتیتر <code>### path</code>.<br>"
     "<b>Minimal</b>: فقط <code># path</code>.<br>"
     "<b>Verbose</b>: مسیر کامل + اندازه."),
    ("Respect .gitignore چیست؟",
     "پوشه‌های ذکرشده در <code>.gitignore</code> خودکار غیرفعال و با 🚫 علامت می‌خورند."),
    ("چرا خروجی خالی است؟",
     "• حداقل یک پسوند فعال باشد.<br>"
     "• حداقل یک فایل تیک داشته باشد.<br>"
     "• Respect .gitignore همه را حذف نکرده باشد.<br>"
     "• Max file size خیلی کوچک نباشد."),
    ("چطور تنظیمات را منتقل کنم؟",
     "دکمه‌ی <b>⬇ Export</b> یک فایل JSON می‌سازد و <b>⬆ Import</b> آن را وارد می‌کند."),
]


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("راهنما — سؤالات متداول")
        self.resize(980, 720)
        self.setStyleSheet(DARK_QSS + HELP_QSS)
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("📖  راهنمای برنامه")
        title.setObjectName("Title")
        head.addWidget(title)
        head.addStretch()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جستجو در راهنما…")
        self.search_edit.setFixedWidth(340)
        self.search_edit.textChanged.connect(self._filter)
        head.addWidget(self.search_edit)
        layout.addLayout(head)

        subtitle = QLabel(
            "این برنامه فایل‌های پروژه را در یک فایل متنی جمع می‌کند تا به هوش مصنوعی بدهید."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        self.faq_layout = QVBoxLayout(container)
        self.faq_layout.setContentsMargins(0, 0, 0, 0)
        self.faq_layout.setSpacing(6)
        self.faq_layout.addStretch()

        self._faq_widgets = []
        for q, a in FAQ_ITEMS:
            btn, body = self._make_faq_item(q, a)
            self._faq_widgets.append((q.lower(), btn, body))
            self.faq_layout.addWidget(btn)
            self.faq_layout.addWidget(body)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        foot = QHBoxLayout()
        self.count_lbl = QLabel(f"{len(FAQ_ITEMS)} سؤال")
        self.count_lbl.setObjectName("Subtitle")
        foot.addWidget(self.count_lbl)
        foot.addStretch()
        expand_all = QPushButton("باز کردن همه")
        expand_all.clicked.connect(lambda: self._set_all(True))
        collapse_all = QPushButton("بستن همه")
        collapse_all.clicked.connect(lambda: self._set_all(False))
        close_btn = QPushButton("بستن")
        close_btn.setObjectName("Primary")
        close_btn.clicked.connect(self.accept)
        foot.addWidget(expand_all)
        foot.addWidget(collapse_all)
        foot.addWidget(close_btn)
        layout.addLayout(foot)

    def _make_faq_item(self, question, answer_html):
        btn = QPushButton(("▸  " + question))
        btn.setObjectName("FaqQuestion")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        body = QLabel(answer_html)
        body.setObjectName("FaqAnswer")
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setVisible(False)

        def toggle(checked):
            body.setVisible(checked)
            btn.setText(("▾  " if checked else "▸  ") + question)

        btn.toggled.connect(toggle)
        return btn, body

    def _filter(self, text):
        text = text.strip().lower()
        visible = 0
        for q_lower, btn, body in self._faq_widgets:
            if not text or text in q_lower or text in body.text().lower():
                btn.setVisible(True)
                body.setVisible(btn.isChecked())
                visible += 1
            else:
                btn.setVisible(False)
                body.setVisible(False)
        self.count_lbl.setText(f"{visible} سؤال")

    def _set_all(self, on):
        for _, btn, _ in self._faq_widgets:
            if btn.isVisible():
                btn.setChecked(on)


HELP_QSS = """
QScrollArea { background: transparent; }
QPushButton#FaqQuestion {
    text-align: right;
    background-color: #16161a;
    border: 1px solid #2a2a30;
    border-radius: 8px;
    padding: 10px 14px;
    color: #e8e8ea;
    font-weight: 600;
}
QPushButton#FaqQuestion:hover {
    border-color: #d7263d;
    background-color: #1f1f24;
}
QPushButton#FaqQuestion:checked {
    border-color: #d7263d;
    background-color: #24141a;
    color: #ffffff;
}
QLabel#FaqAnswer {
    background-color: #0d0d0f;
    border: 1px solid #1c1c22;
    border-radius: 8px;
    padding: 12px 16px;
    color: #d0d0d6;
    margin: 0 0 6px 0;
}
"""


# ============================================================
# DARK TITLE BAR
# ============================================================


class DarkTitleBar(QWidget):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self._win = parent_window
        self._drag_pos = None
        self.setFixedHeight(38)
        self.setStyleSheet("""
            DarkTitleBar { background-color: #0a0a0c; border-bottom: 1px solid #2a2a30; }
            QLabel { color: #e8e8ea; font-weight: 600; padding-left: 6px; }
            QPushButton {
                background: transparent; color: #e8e8ea;
                border: none; padding: 0 12px; font-size: 13pt;
            }
            QPushButton:hover { background-color: #1f1f24; }
            QPushButton#CloseBtn:hover { background-color: #d7263d; color: white; }
        """)

        h = QHBoxLayout(self)
        h.setContentsMargins(8, 0, 0, 0)
        h.setSpacing(0)

        title = QLabel(f"📦  {parent_window.windowTitle()}")
        h.addWidget(title)
        h.addStretch()

        min_btn = QPushButton("—")
        min_btn.setFixedSize(46, 38)
        min_btn.clicked.connect(self._win.showMinimized)
        h.addWidget(min_btn)

        max_btn = QPushButton("□")
        max_btn.setFixedSize(46, 38)
        max_btn.clicked.connect(self._toggle_max)
        h.addWidget(max_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(46, 38)
        close_btn.clicked.connect(self._win.close)
        h.addWidget(close_btn)

    def _toggle_max(self):
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self._win.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        e.accept()

    def mouseDoubleClickEvent(self, e):
        self._toggle_max()
        e.accept()


# ============================================================
# MAIN WINDOW
# ============================================================


class CollectorWindow(QMainWindow):
    status_msg = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Collector For AI")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.resize(1360, 900)
        self.setMinimumSize(1100, 720)

        self.db = Database()
        self.projects = []
        self.current_project = None
        self.folder_decisions = {}
        self.file_decisions = {}
        self.gitignored = set()
        self.items = {}         # rel_path -> QTreeWidgetItem (folders)
        self.file_items = {}    # rel_path -> QTreeWidgetItem (files)
        self._updating_tree = False
        self._loading_options = False
        self.git_matcher = None

        self.ext_checks = {}

        self._build_ui()
        self._refresh_projects()
        self.status_msg.connect(lambda m: self.statusBar().showMessage(m))
        self._build_frameless_layout()

    # ---------------- UI ----------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 10)
        root.setSpacing(10)

        # Header
        header = QHBoxLayout()
        logo_lbl = QLabel()
        if os.path.isfile(ICON_PATH):
            logo_lbl.setPixmap(QIcon(ICON_PATH).pixmap(24, 24))
            logo_lbl.setFixedSize(24, 24)
        header.addWidget(logo_lbl)

        title = QLabel("File Collector For AI")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch()

        self.btn_help = QPushButton("HELP ❓")
        self.btn_help.setToolTip("راهنمای برنامه و سؤالات متداول")
        self.btn_help.setCursor(Qt.PointingHandCursor)
        self.btn_help.clicked.connect(self._open_help)
        header.addWidget(self.btn_help)
        header.addSpacing(12)

        self.header_sub = QLabel("Select a project on the left, or create one.")
        self.header_sub.setObjectName("Subtitle")
        header.addWidget(self.header_sub)
        root.addLayout(header)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        # ---- Column 1: Projects ----
        col_projects = QFrame(); col_projects.setObjectName("Card")
        col_projects.setMinimumWidth(220)
        col_projects.setMaximumWidth(360)
        p_l = QVBoxLayout(col_projects)
        p_l.setContentsMargins(12, 12, 12, 12)
        p_l.setSpacing(8)

        lbl = QLabel("Projects"); lbl.setObjectName("SectionTitle")
        p_l.addWidget(lbl)

        self.project_list = QListWidget()
        self.project_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.project_list.currentRowChanged.connect(self._on_project_row_changed)
        p_l.addWidget(self.project_list, 1)

        row1 = QHBoxLayout()
        self.btn_new = QPushButton("➕  New")
        self.btn_new.clicked.connect(self._new_project)
        self.btn_del = QPushButton("🗑  Delete")
        self.btn_del.setObjectName("Danger")
        self.btn_del.clicked.connect(self._delete_project)
        row1.addWidget(self.btn_new); row1.addWidget(self.btn_del)
        p_l.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_import = QPushButton("⬆  Import")
        self.btn_import.clicked.connect(self._import_json)
        self.btn_export = QPushButton("⬇  Export")
        self.btn_export.clicked.connect(self._export_json)
        row2.addWidget(self.btn_import); row2.addWidget(self.btn_export)
        p_l.addLayout(row2)

        splitter.addWidget(col_projects)
        splitter.setStretchFactor(0, 0)

        # ---- Column 2: Tree (folders + files) ----
        col_tree = QFrame(); col_tree.setObjectName("Card")
        col_tree.setMinimumWidth(360)
        t_l = QVBoxLayout(col_tree)
        t_l.setContentsMargins(12, 12, 12, 12)
        t_l.setSpacing(8)

        tree_header = QHBoxLayout()
        tree_title = QLabel("Files & Folders")
        tree_title.setObjectName("SectionTitle")
        tree_header.addWidget(tree_title)
        tree_header.addStretch()
        self.lbl_stats = QLabel("")
        self.lbl_stats.setObjectName("Subtitle")
        tree_header.addWidget(self.lbl_stats)
        t_l.addLayout(tree_header)

        # quick tree action bar
        tree_tools = QHBoxLayout()
        self.btn_expand = QPushButton("⊞  Expand")
        self.btn_collapse = QPushButton("⊟  Collapse")
        self.btn_check_all = QPushButton("✓  All")
        self.btn_check_none = QPushButton("✗  None")
        for b in (self.btn_expand, self.btn_collapse,
                  self.btn_check_all, self.btn_check_none):
            b.setObjectName("Mini")
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        self.btn_check_all.clicked.connect(lambda: self._set_all_tree(True))
        self.btn_check_none.clicked.connect(lambda: self._set_all_tree(False))
        tree_tools.addWidget(self.btn_expand)
        tree_tools.addWidget(self.btn_collapse)
        tree_tools.addSpacing(12)
        tree_tools.addWidget(self.btn_check_all)
        tree_tools.addWidget(self.btn_check_none)
        tree_tools.addStretch()
        t_l.addLayout(tree_tools)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Sel", "gitignore"])
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 46)
        self.tree.setColumnWidth(2, 90)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.tree.itemChanged.connect(self._on_tree_item_changed)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        t_l.addWidget(self.tree, 1)

        tree_actions = QHBoxLayout()
        self.btn_rescan = QPushButton("🔄  Rescan")
        self.btn_rescan.clicked.connect(lambda: self._rescan_tree())
        self.btn_save = QPushButton("💾  Save")
        self.btn_save.clicked.connect(self._save_settings)
        tree_actions.addWidget(self.btn_rescan)
        tree_actions.addWidget(self.btn_save)
        tree_actions.addStretch()
        t_l.addLayout(tree_actions)

        splitter.addWidget(col_tree)
        splitter.setStretchFactor(1, 2)

        # ---- Column 3: Settings ----
        col_settings = QFrame(); col_settings.setObjectName("Card")
        col_settings.setMinimumWidth(420)
        s_l = QVBoxLayout(col_settings)
        s_l.setContentsMargins(14, 14, 14, 14)
        s_l.setSpacing(10)

        info = QFrame()
        info_l = QVBoxLayout(info)
        info_l.setContentsMargins(0, 0, 0, 0)
        info_l.setSpacing(6)
        self.lbl_name = self._info_row(info_l, "Name", editable=True)
        self.lbl_root = self._info_row(info_l, "Root", editable=False)
        self.lbl_out = self._info_row(info_l, "Output", editable=True, with_browse=True)
        s_l.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        sc_l = QVBoxLayout(scroll_content)
        sc_l.setContentsMargins(0, 0, 0, 0)
        sc_l.setSpacing(10)

        # output options
        opts_box = QGroupBox("Output options")
        opts_l = QVBoxLayout(opts_box)
        opts_l.setSpacing(6)

        row_fmt = QHBoxLayout()
        fmt_lbl = QLabel("Format:")
        fmt_lbl.setObjectName("Subtitle")
        self.format_combo = QComboBox()
        self.format_combo.addItem("Compact (recommended for AI)", "compact")
        self.format_combo.addItem("Minimal (smallest)", "minimal")
        self.format_combo.addItem("Verbose (old style)", "verbose")
        self.format_combo.currentIndexChanged.connect(self._on_option_changed)
        row_fmt.addWidget(fmt_lbl)
        row_fmt.addWidget(self.format_combo, 1)
        opts_l.addLayout(row_fmt)

        row_kb = QHBoxLayout()
        kb_lbl = QLabel("Max file size:")
        kb_lbl.setObjectName("Subtitle")
        self.max_kb_spin = QSpinBox()
        self.max_kb_spin.setRange(0, 10000)
        self.max_kb_spin.setSingleStep(50)
        self.max_kb_spin.setSuffix(" KB")
        self.max_kb_spin.setSpecialValueText("no limit")
        self.max_kb_spin.valueChanged.connect(self._on_option_changed)
        row_kb.addWidget(kb_lbl)
        row_kb.addWidget(self.max_kb_spin, 1)
        opts_l.addLayout(row_kb)

        self.chk_skip_init = QCheckBox("Skip empty __init__.py")
        self.chk_skip_init.stateChanged.connect(self._on_option_changed)
        self.chk_collapse = QCheckBox("Collapse extra blank lines")
        self.chk_collapse.stateChanged.connect(self._on_option_changed)
        self.chk_strip_doc = QCheckBox("Strip docstrings")
        self.chk_strip_doc.stateChanged.connect(self._on_option_changed)
        opts_l.addWidget(self.chk_skip_init)
        opts_l.addWidget(self.chk_collapse)
        opts_l.addWidget(self.chk_strip_doc)

        self.chk_gitignore = QCheckBox("Respect .gitignore")
        self.chk_gitignore.stateChanged.connect(self._on_gitignore_toggled)
        opts_l.addWidget(self.chk_gitignore)

        self.chk_show_all = QCheckBox("Show all files (ignore extension filter in tree)")
        self.chk_show_all.stateChanged.connect(self._on_show_all_toggled)
        opts_l.addWidget(self.chk_show_all)

        self.gitignore_status = QLabel("")
        self.gitignore_status.setObjectName("Subtitle")
        self.gitignore_status.setWordWrap(True)
        opts_l.addWidget(self.gitignore_status)

        sc_l.addWidget(opts_box)

        # file types
        types_box = QGroupBox("File types")
        types_l = QVBoxLayout(types_box)
        types_l.setSpacing(6)

        quick_row = QHBoxLayout()
        self.btn_types_all = QPushButton("All")
        self.btn_types_none = QPushButton("None")
        self.btn_types_py = QPushButton("Python")
        self.btn_types_web = QPushButton("Web")
        self.btn_types_web_tsx = QPushButton("TSX")
        self.btn_types_all.clicked.connect(lambda: self._set_all_types(True))
        self.btn_types_none.clicked.connect(lambda: self._set_all_types(False))
        self.btn_types_py.clicked.connect(lambda: self._select_only([".py", ".pyi", ".pyx"]))
        self.btn_types_web.clicked.connect(lambda: self._select_only(
            [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
             ".html", ".htm", ".css", ".scss"]))
        self.btn_types_web_tsx.clicked.connect(lambda: self._select_only([".tsx"]))
        for b in (self.btn_types_all, self.btn_types_none,
                  self.btn_types_py, self.btn_types_web, self.btn_types_web_tsx):
            b.setObjectName("Mini")
            quick_row.addWidget(b)
        quick_row.addStretch()
        types_l.addLayout(quick_row)

        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)

        row_i = 0
        for group_name, exts in FILE_TYPE_GROUPS:
            g_lbl = QLabel(group_name)
            g_lbl.setStyleSheet("color: #d7263d; font-weight: 600; margin-top: 6px;")
            grid.addWidget(g_lbl, row_i, 0, 1, 4)
            row_i += 1
            col_i = 0
            for ext, _ in exts:
                cb = QCheckBox(ext)
                cb.stateChanged.connect(self._on_ext_option_changed)
                self.ext_checks[ext] = cb
                grid.addWidget(cb, row_i, col_i)
                col_i += 1
                if col_i >= 4:
                    col_i = 0
                    row_i += 1
            if col_i != 0:
                row_i += 1
        types_l.addWidget(grid_wrap)

        custom_row = QHBoxLayout()
        custom_lbl = QLabel("Custom:")
        custom_lbl.setObjectName("Subtitle")
        self.custom_ext_edit = QLineEdit()
        self.custom_ext_edit.setPlaceholderText(".proto, .graphql, .wgsl")
        self.custom_ext_edit.textChanged.connect(self._on_ext_option_changed)
        self.btn_apply_custom = QPushButton("Apply")
        self.btn_apply_custom.setObjectName("Mini")
        self.btn_apply_custom.clicked.connect(self._apply_custom_extensions)
        custom_row.addWidget(custom_lbl)
        custom_row.addWidget(self.custom_ext_edit, 1)
        custom_row.addWidget(self.btn_apply_custom)
        types_l.addLayout(custom_row)

        self.ext_summary_lbl = QLabel("")
        self.ext_summary_lbl.setObjectName("Subtitle")
        self.ext_summary_lbl.setWordWrap(True)
        types_l.addWidget(self.ext_summary_lbl)

        sc_l.addWidget(types_box)
        sc_l.addStretch()

        scroll.setWidget(scroll_content)
        s_l.addWidget(scroll, 1)

        actions = QHBoxLayout()
        self.btn_view = QPushButton("👁  View Output")
        self.btn_view.setObjectName("Success")
        self.btn_view.clicked.connect(self._view_output)
        self.btn_view.setEnabled(False)

        self.btn_generate = QPushButton("📦  Generate Text File")
        self.btn_generate.setObjectName("Primary")
        self.btn_generate.clicked.connect(self._generate)

        actions.addWidget(self.btn_view)
        actions.addWidget(self.btn_generate, 1)
        s_l.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        s_l.addWidget(self.progress)

        splitter.addWidget(col_settings)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([260, 500, 600])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")
        self._set_enabled_for_project(False)

    def _info_row(self, parent_layout, label_text, editable=False, with_browse=False):
        row = QHBoxLayout()
        lbl = QLabel(label_text + ":")
        lbl.setFixedWidth(60)
        lbl.setObjectName("Subtitle")
        edit = QLineEdit()
        edit.setReadOnly(not editable)
        row.addWidget(lbl)
        row.addWidget(edit, 1)
        if with_browse:
            btn = QPushButton("Browse…")
            btn.clicked.connect(self._pick_output)
            row.addWidget(btn)
        w = QWidget(); w.setLayout(row)
        parent_layout.addWidget(w)
        return edit

    def _build_frameless_layout(self):
        central = self.centralWidget()
        old_layout = central.layout()
        new_outer = QVBoxLayout()
        new_outer.setContentsMargins(0, 0, 0, 0)
        new_outer.setSpacing(0)

        self.title_bar = DarkTitleBar(self)
        new_outer.addWidget(self.title_bar)

        content = QWidget()
        content.setLayout(old_layout)
        new_outer.addWidget(content, 1)

        central.setLayout(new_outer)

    def _open_help(self):
        HelpDialog(self).exec()

    def _set_enabled_for_project(self, enabled):
        for w in (self.tree, self.btn_rescan, self.btn_save, self.btn_generate,
                  self.lbl_out, self.btn_export, self.format_combo, self.max_kb_spin,
                  self.chk_skip_init, self.chk_collapse, self.chk_strip_doc,
                  self.chk_gitignore, self.chk_show_all, self.custom_ext_edit,
                  self.btn_apply_custom, self.btn_types_all, self.btn_types_none,
                  self.btn_types_py, self.btn_types_web, self.btn_types_web_tsx,
                  self.btn_expand, self.btn_collapse,
                  self.btn_check_all, self.btn_check_none):
            w.setEnabled(enabled)
        for cb in self.ext_checks.values():
            cb.setEnabled(enabled)
        if enabled:
            out = self.lbl_out.text().strip()
            self.btn_view.setEnabled(bool(out and os.path.isfile(out)))
        else:
            self.btn_view.setEnabled(False)

    # ---------------- EXTENSIONS ----------------
    def _normalize_ext(self, s):
        s = s.strip().lower()
        if not s:
            return ""
        if not s.startswith("."):
            s = "." + s
        return s

    def _current_extensions(self):
        exts = set()
        for ext, cb in self.ext_checks.items():
            if cb.isChecked():
                exts.add(ext.lower())
        for raw in self.custom_ext_edit.text().split(","):
            e = self._normalize_ext(raw)
            if e:
                exts.add(e)
        return sorted(exts)

    def _apply_extensions_to_ui(self, extensions):
        ext_set = {e.lower() for e in (extensions or [])}
        for ext, cb in self.ext_checks.items():
            cb.blockSignals(True)
            cb.setChecked(ext.lower() in ext_set)
            cb.blockSignals(False)
        known = {e.lower() for e in self.ext_checks}
        leftovers = sorted(ext_set - known)
        self.custom_ext_edit.blockSignals(True)
        self.custom_ext_edit.setText(", ".join(leftovers))
        self.custom_ext_edit.blockSignals(False)
        self._update_ext_summary()

    def _update_ext_summary(self):
        exts = self._current_extensions()
        if not exts:
            self.ext_summary_lbl.setText("⚠️  no extensions selected — nothing will be collected")
            self.ext_summary_lbl.setStyleSheet("color: #ff6b7a;")
        else:
            preview = ", ".join(exts[:16])
            more = "" if len(exts) <= 16 else f"  (+{len(exts) - 16} more)"
            self.ext_summary_lbl.setText(
                f"✅ {len(exts)} extension(s) selected: {preview}{more}"
            )
            self.ext_summary_lbl.setStyleSheet("color: #8a8a92;")

    def _on_ext_option_changed(self, *args):
        if self._loading_options:
            return
        self._update_ext_summary()
        self._persist_options()
        # Rebuild tree since visible files depend on extensions
        if self.current_project:
            self._rescan_tree(silent=True)

    def _apply_custom_extensions(self):
        raw = self.custom_ext_edit.text()
        wanted = {self._normalize_ext(p) for p in raw.split(",") if p.strip()}
        wanted.discard("")
        for ext in wanted:
            if ext in self.ext_checks:
                self.ext_checks[ext].blockSignals(True)
                self.ext_checks[ext].setChecked(True)
                self.ext_checks[ext].blockSignals(False)
        self._on_ext_option_changed()

    def _set_all_types(self, on):
        self._loading_options = True
        for cb in self.ext_checks.values():
            cb.blockSignals(True)
            cb.setChecked(on)
            cb.blockSignals(False)
        self._loading_options = False
        self._on_ext_option_changed()

    def _select_only(self, exts):
        wanted = {e.lower() for e in exts}
        self._loading_options = True
        for ext, cb in self.ext_checks.items():
            cb.blockSignals(True)
            cb.setChecked(ext.lower() in wanted)
            cb.blockSignals(False)
        self._loading_options = False
        known = {e.lower() for e in self.ext_checks}
        leftovers = sorted(wanted - known)
        self.custom_ext_edit.blockSignals(True)
        self.custom_ext_edit.setText(", ".join(leftovers))
        self.custom_ext_edit.blockSignals(False)
        self._on_ext_option_changed()

    # ---------------- PROJECT LIST ----------------
    def _refresh_projects(self):
        self.projects = self.db.list_projects()
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for p in self.projects:
            item = QListWidgetItem(f"📁  {p['name']}")
            item.setData(Qt.UserRole, p["id"])
            self.project_list.addItem(item)
        self.project_list.blockSignals(False)

    def _on_project_row_changed(self, row):
        if row < 0 or row >= len(self.projects):
            return
        self._load_project(self.projects[row])

    def _load_project(self, project):
        self.current_project = project
        self.lbl_name.setText(project["name"])
        self.lbl_root.setText(project["root_path"])
        out = project["output_file"] or os.path.join(
            os.path.dirname(os.path.abspath(project["root_path"])), "all_files.txt"
        )
        self.lbl_out.setText(out)
        self.folder_decisions = self.db.get_folder_decisions(project["id"])
        self.file_decisions = self.db.get_file_decisions(project["id"])

        self._loading_options = True
        opts = project.get("options") or DEFAULT_OPTIONS.copy()
        idx = self.format_combo.findData(opts.get("format_mode", "compact"))
        self.format_combo.setCurrentIndex(max(0, idx))
        self.max_kb_spin.setValue(int(opts.get("max_file_kb", 0) or 0))
        self.chk_skip_init.setChecked(bool(opts.get("skip_empty_init", True)))
        self.chk_collapse.setChecked(bool(opts.get("collapse_blank", True)))
        self.chk_strip_doc.setChecked(bool(opts.get("strip_docstrings", False)))
        self.chk_gitignore.setChecked(bool(opts.get("respect_gitignore", True)))
        self.chk_show_all.setChecked(bool(opts.get("show_all_files", False)))
        saved_exts = opts.get("extensions")
        if saved_exts is None or not isinstance(saved_exts, list):
            saved_exts = DEFAULT_EXTENSIONS
        self._apply_extensions_to_ui(saved_exts)
        self._loading_options = False

        self._set_enabled_for_project(True)
        self.header_sub.setText(f"Root: {project['root_path']}")
        self._rescan_tree(silent=True)

    def _new_project(self):
        dlg = NewProjectDialog(self.db, self)
        if dlg.exec() == QDialog.Accepted and dlg.result_project:
            self._refresh_projects()
            pid = dlg.result_project["id"]
            for i, p in enumerate(self.projects):
                if p["id"] == pid:
                    self.project_list.setCurrentRow(i)
                    break
            self.statusBar().showMessage(f"Created project '{dlg.result_project['name']}'.")

    def _delete_project(self):
        if not self.current_project:
            return
        r = QMessageBox.question(
            self, "Delete project",
            f"Delete project '{self.current_project['name']}'?\nThis cannot be undone.",
        )
        if r != QMessageBox.Yes:
            return
        self.db.delete_project(self.current_project["id"])
        self.current_project = None
        self.folder_decisions.clear()
        self.file_decisions.clear()
        self.gitignored.clear()
        self.tree.clear()
        self.items.clear()
        self.file_items.clear()
        self.lbl_name.clear(); self.lbl_root.clear(); self.lbl_out.clear()
        self._set_enabled_for_project(False)
        self._refresh_projects()
        self.header_sub.setText("Select a project on the left, or create one.")
        self.statusBar().showMessage("Project deleted.")

    def _export_json(self):
        if not self.current_project:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export project", f"{self.current_project['name']}.json",
            "JSON (*.json)"
        )
        if not path:
            return
        self.db.export_project_json(self.current_project["id"], path)
        self.statusBar().showMessage(f"Exported to {path}")

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import project", "", "JSON (*.json)")
        if not path:
            return
        try:
            pid = self.db.import_project_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        self._refresh_projects()
        for i, p in enumerate(self.projects):
            if p["id"] == pid:
                self.project_list.setCurrentRow(i)
                break
        self.statusBar().showMessage(f"Imported '{path}'")

    # ---------------- OPTIONS ----------------
    def _current_options(self):
        return {
            "format_mode": self.format_combo.currentData(),
            "skip_empty_init": self.chk_skip_init.isChecked(),
            "collapse_blank": self.chk_collapse.isChecked(),
            "strip_docstrings": self.chk_strip_doc.isChecked(),
            "respect_gitignore": self.chk_gitignore.isChecked(),
            "max_file_kb": self.max_kb_spin.value(),
            "skip_common_files": True,
            "show_all_files": self.chk_show_all.isChecked(),
            "extensions": self._current_extensions(),
        }

    def _on_option_changed(self, *args):
        if self._loading_options:
            return
        self._persist_options()
        self._apply_gitignore_to_tree()
        self._update_stats()

    def _on_show_all_toggled(self, *args):
        if self._loading_options:
            return
        self._persist_options()
        if self.current_project:
            self._rescan_tree(silent=True)

    def _on_gitignore_toggled(self, *args):
        if self._loading_options:
            return
        if not self.chk_gitignore.isChecked():
            self.gitignored.clear()
            if self.current_project:
                self.folder_decisions = self.db.get_folder_decisions(self.current_project["id"])
                self.file_decisions = self.db.get_file_decisions(self.current_project["id"])
        self._apply_gitignore_to_tree()
        self._persist_options()
        self._update_stats()

    def _persist_options(self):
        if not self.current_project:
            return
        opts = self._current_options()
        self.db.update_project(self.current_project["id"], options=opts)
        self.current_project["options"] = opts

    # ---------------- GITIGNORE ----------------
    def _load_gitignore(self):
        self.gitignored.clear()
        self.git_matcher = None
        if not self.current_project:
            self.gitignore_status.setText("")
            return
        root = self.current_project["root_path"]
        path = os.path.join(root, ".gitignore")
        if not os.path.isfile(path):
            self.gitignore_status.setText("⚠️  no .gitignore in project root")
            return
        try:
            self.git_matcher = GitIgnoreMatcher.load(root)
        except Exception as e:
            self.gitignore_status.setText(f"⚠️  error reading .gitignore: {e}")
            return
        if self.git_matcher is None or not self.git_matcher.patterns:
            self.gitignore_status.setText("⚠️  .gitignore is empty")
            return

        root_abs = os.path.abspath(root)
        for dirpath, dirnames, filenames in os.walk(root_abs, topdown=True):
            rel = os.path.relpath(dirpath, root_abs)
            rel_norm = "." if rel == "." else rel.replace(os.sep, "/")
            if rel_norm != "." and self.git_matcher.is_ignored(rel_norm):
                self.gitignored.add(rel_norm)

        if self.gitignored:
            self.gitignore_status.setText(f"✅ {len(self.gitignored)} folder(s) gitignored")
        else:
            self.gitignore_status.setText("✅ .gitignore loaded (nothing ignored)")

    def _apply_gitignore_to_tree(self):
        if not self.current_project:
            return
        respect = self.chk_gitignore.isChecked()

        # combine DB + gitignore override (in memory only)
        base_dirs = self.db.get_folder_decisions(self.current_project["id"])
        base_files = self.db.get_file_decisions(self.current_project["id"])
        eff_dirs = dict(base_dirs)
        eff_files = dict(base_files)
        for rel in self.gitignored:
            if respect:
                eff_dirs[rel] = False

        self.folder_decisions = eff_dirs
        self.file_decisions = eff_files

        self._updating_tree = True
        for rel, item in self.items.items():
            if respect and rel in self.gitignored:
                item.setCheckState(0, Qt.Unchecked)
                item.setText(1, "🚫")
                item.setForeground(2, QBrush(QColor("#ff6b7a")))
                item.setText(2, "🚫 ignored")
            else:
                inc = eff_dirs.get(rel, True)
                item.setCheckState(0, Qt.Checked if inc else Qt.Unchecked)
                item.setForeground(2, QBrush(QColor("#8a8a92")))
                item.setText(2, "")
        for rel, item in self.file_items.items():
            if respect and rel in self.gitignored:
                item.setCheckState(0, Qt.Unchecked)
            else:
                inc = eff_files.get(rel, True)
                item.setCheckState(0, Qt.Checked if inc else Qt.Unchecked)
        self._updating_tree = False

        # recompute partials bottom-up
        self._updating_tree = True
        for rel in sorted(self.items.keys(), reverse=True):
            item = self.items[rel]
            if item.childCount() > 0:
                self._propagate_upwards(item)
        self._updating_tree = False

        self._refresh_check_states_display()
        self._update_stats()

    # ---------------- TREE ----------------
    def _rescan_tree(self, silent=False):
        if not self.current_project:
            return
        root = self.current_project["root_path"]
        if not os.path.isdir(root):
            if not silent:
                QMessageBox.critical(self, "Error", f"Root folder not found:\n{root}")
            return
        if not silent:
            self.statusBar().showMessage("Scanning tree…")
        QApplication.processEvents()

        self._load_gitignore()
        exts = self._current_extensions()
        show_all = self.chk_show_all.isChecked()
        entries = scan_tree_entries(root, exts, show_all_files=show_all)

        # preserve expansion state
        expanded = {rel for rel, item in self.items.items() if item.isExpanded()}

        self.tree.blockSignals(True)
        self.tree.clear()
        self.items.clear()
        self.file_items.clear()
        self._updating_tree = True

        for rel, is_dir in entries:
            if rel == ".":
                parent = None
                label = os.path.basename(root) or "(root)"
            else:
                parent_rel = "/".join(rel.split("/")[:-1]) or "."
                parent = self.items.get(parent_rel)
                label = rel.split("/")[-1]

            if is_dir:
                item = QTreeWidgetItem([f"📁 {label}", "", ""])
                item.setData(0, Qt.UserRole, rel)
                item.setData(0, Qt.UserRole + 1, "dir")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                include = self.folder_decisions.get(rel, True)
                item.setCheckState(0, Qt.Checked if include else Qt.Unchecked)
                if parent is not None:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                self.items[rel] = item
                # expand if root, previously expanded, or (no expansion state yet)
                if rel == "." or rel in expanded or not expanded:
                    item.setExpanded(True)
            else:
                item = QTreeWidgetItem([f"📄 {label}", "", ""])
                item.setData(0, Qt.UserRole, rel)
                item.setData(0, Qt.UserRole + 1, "file")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                include = self.file_decisions.get(rel, True)
                item.setCheckState(0, Qt.Checked if include else Qt.Unchecked)
                item.setForeground(0, QBrush(QColor("#c8c8d0")))
                if parent is not None:
                    parent.addChild(item)
                self.file_items[rel] = item

        self.tree.blockSignals(False)
        self._updating_tree = False

        self._apply_gitignore_to_tree()

        self._updating_tree = True
        for rel in sorted(self.items.keys(), reverse=True):
            item = self.items[rel]
            if item.childCount() > 0:
                self._propagate_upwards(item)
        self._updating_tree = False

        self._refresh_check_states_display()
        if not silent:
            n_files = len(self.file_items)
            self.statusBar().showMessage(
                f"Scanned {len(self.items)} folders, {n_files} files."
            )

    def _on_item_expanded(self, item):
        # اینجا کاری لازم نیست اما اگر lazy-load خواستید می‌توانید اینجا اضافه کنید
        pass

    def _refresh_check_states_display(self):
        for rel, item in self.items.items():
            state = item.checkState(0)
            if state == Qt.Checked:
                item.setText(1, "✅")
            elif state == Qt.Unchecked:
                item.setText(1, "⬜")
            else:
                item.setText(1, "➖")
        for rel, item in self.file_items.items():
            state = item.checkState(0)
            if state == Qt.Checked:
                item.setText(1, "✅")
            elif state == Qt.Unchecked:
                item.setText(1, "⬜")
            else:
                item.setText(1, "➖")

    def _set_all_tree(self, on):
        if not self.current_project:
            return
        self._updating_tree = True
        for rel, item in self.items.items():
            if on and self.chk_gitignore.isChecked() and rel in self.gitignored:
                item.setCheckState(0, Qt.Unchecked)
                self.folder_decisions[rel] = False
            else:
                item.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
                self.folder_decisions[rel] = bool(on)
        for rel, item in self.file_items.items():
            item.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
            self.file_decisions[rel] = bool(on)
        self._updating_tree = False
        self._refresh_check_states_display()
        self._update_stats()

    def _on_tree_item_changed(self, item, column):
        if self._updating_tree or column != 0:
            return
        rel = item.data(0, Qt.UserRole)
        kind = item.data(0, Qt.UserRole + 1)
        state = item.checkState(0)

        if self.chk_gitignore.isChecked() and rel in self.gitignored:
            if state != Qt.Unchecked:
                self._updating_tree = True
                item.setCheckState(0, Qt.Unchecked)
                self._updating_tree = False
            return

        self._updating_tree = True
        if kind == "file":
            self.file_decisions[rel] = (state == Qt.Checked)
            self._propagate_upwards(item.parent())
        else:
            self.folder_decisions[rel] = (state != Qt.Unchecked)
            self._set_children_state(item, state)
            self._propagate_upwards(item.parent())
        self._updating_tree = False

        self._refresh_check_states_display()
        self._update_stats()

    def _set_children_state(self, item, state):
        if state == Qt.PartiallyChecked:
            return
        for i in range(item.childCount()):
            child = item.child(i)
            crel = child.data(0, Qt.UserRole)
            kind = child.data(0, Qt.UserRole + 1)

            if self.chk_gitignore.isChecked() and crel in self.gitignored:
                child.setCheckState(0, Qt.Unchecked)
                if kind == "dir":
                    self.folder_decisions[crel] = False
                else:
                    self.file_decisions[crel] = False
            else:
                child.setCheckState(0, state)
                if kind == "dir":
                    self.folder_decisions[crel] = (state == Qt.Checked)
                else:
                    self.file_decisions[crel] = (state == Qt.Checked)
            if kind == "dir":
                self._set_children_state(child, state)

    def _propagate_upwards(self, item):
        while item is not None:
            n = item.childCount()
            if n == 0:
                item = item.parent()
                continue
            states = [item.child(i).checkState(0) for i in range(n)]
            rel = item.data(0, Qt.UserRole)
            if all(s == Qt.Unchecked for s in states):
                item.setCheckState(0, Qt.Unchecked)
                self.folder_decisions[rel] = False
            elif all(s == Qt.Checked for s in states):
                item.setCheckState(0, Qt.Checked)
                self.folder_decisions[rel] = True
            else:
                item.setCheckState(0, Qt.PartiallyChecked)
                self.folder_decisions[rel] = True  # keep walking in
            item = item.parent()

    def _update_stats(self):
        if not self.current_project:
            return
        opts = self._current_options()
        n = count_selected_files(
            self.current_project["root_path"], self.folder_decisions, opts,
            file_map=self.file_decisions,
        )
        n_folders = len(self.items)
        n_files = len(self.file_items)
        self.lbl_stats.setText(f"{n} selected · {n_folders} folders · {n_files} files shown")
        self.btn_view.setEnabled(
            bool(self.lbl_out.text() and os.path.isfile(self.lbl_out.text()))
        )

    # ---------------- OUTPUT ----------------
    def _pick_output(self):
        if not self.current_project:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Choose output file", self.lbl_out.text(),
            "Text file (*.txt);;All files (*)"
        )
        if path:
            self.lbl_out.setText(path)
            self.db.update_project(self.current_project["id"], output_file=path)
            self.btn_view.setEnabled(os.path.isfile(path))

    def _save_settings(self):
        if not self.current_project:
            return
        for rel, inc in self.folder_decisions.items():
            self.db.set_folder_decision(self.current_project["id"], rel, inc)
        for rel, inc in self.file_decisions.items():
            self.db.set_file_decision(self.current_project["id"], rel, inc)
        self.db.update_project(
            self.current_project["id"],
            output_file=self.lbl_out.text(),
            options=self._current_options(),
        )
        self._refresh_projects()
        for i, p in enumerate(self.projects):
            if p["id"] == self.current_project["id"]:
                self.project_list.blockSignals(True)
                self.project_list.setCurrentRow(i)
                self.project_list.blockSignals(False)
                self.current_project = p
                break
        self.statusBar().showMessage("Settings saved.")
        QMessageBox.information(self, "Saved", "Folder/file decisions and options saved.")

    def _generate(self):
        if not self.current_project:
            return
        out = self.lbl_out.text().strip()
        if not out:
            QMessageBox.warning(self, "Missing", "Please set an output path.")
            return

        opts = self._current_options()
        if not opts.get("extensions"):
            QMessageBox.warning(self, "Missing", "Please select at least one file type.")
            return

        for rel, inc in self.folder_decisions.items():
            self.db.set_folder_decision(self.current_project["id"], rel, inc)
        for rel, inc in self.file_decisions.items():
            self.db.set_file_decision(self.current_project["id"], rel, inc)
        self.db.update_project(self.current_project["id"], output_file=out, options=opts)

        self.progress.setVisible(True)
        self.progress.setValue(0)

        def cb(i, total):
            self.progress.setMaximum(total)
            self.progress.setValue(i)
            self.statusBar().showMessage(f"Processing {i}/{total}…")
            QApplication.processEvents()

        try:
            n, size, skipped = collect_python_files(
                self.current_project["root_path"], out, self.folder_decisions,
                progress_cb=cb, options=opts, file_map=self.file_decisions,
            )
        except Exception as e:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Failed", str(e))
            return
        finally:
            self.progress.setVisible(False)

        if n == 0:
            QMessageBox.warning(self, "Empty", "No files matched your selection.")
            self.statusBar().showMessage("No files collected.")
            return

        self.btn_view.setEnabled(True)
        tokens = max(1, size // 4)
        self.statusBar().showMessage(
            f"✅ {n} files · {size/1024:.1f} KB · ~{tokens:,} tokens → {out}"
        )
        QMessageBox.information(
            self, "Done",
            f"Collected {n} files.\n"
            f"Size: {size/1024:.1f} KB\n"
            f"Estimated tokens: ~{tokens:,}\n"
            + (f"Skipped {len(skipped)} folders.\n" if skipped else "")
            + f"\nSaved to:\n{out}"
        )

    def _view_output(self):
        path = self.lbl_out.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "Missing",
                                "No output file yet. Please generate it first.")
            return
        TextViewerDialog(path, self).exec()


# ============================================================
# ENTRY
# ============================================================


def resource_path(rel_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)


ICON_PATH = resource_path("logo.ico")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    win = CollectorWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "MyCompany.FileCollector.1"
            )
        except Exception:
            pass
    main()