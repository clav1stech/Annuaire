"""Project export tool: AI handoff, architecture outline, and backup archive.

Three mutually exclusive profiles:
- ``--ai`` (default): one curated .txt with source code + structuring documentation,
  preceded by a manifest (git info, project version, file table, token estimate).
- ``--outline``: one compact .txt with documentation kept whole and code reduced to
  its structure (module docstring, imports, public constants, class/function
  signatures) so an AI can reason about architecture without any function body.
- ``--backup``: one restorable .zip with everything text-based, including internal
  tooling, with automatic rotation of the N most recent archives.

Scope can be narrowed with ``--only`` (paths) or ``--preset`` (named sub-module).
Outputs land in ./export, which is gitignored: no generated artefact is ever committed.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys
import zipfile


PROJECT_NAME_FALLBACK = "project"
VERSION_FALLBACK = "0.0.0"
EXPORT_DIRNAME = "export"
BACKUP_RETENTION = 5
CHARS_PER_TOKEN = 4
OUTLINE_MAX_LINE_CHARS = 120

# Version is read from these entry points in order; first match wins.
# The VERSION file is the project's single source of truth, the others are fallbacks
# in case the layout changes.
VERSION_ENTRY_POINTS: tuple[tuple[str, str], ...] = (
    ("VERSION", r"^\s*v?(\d+\.\d+\.\d+)\s*$"),
    ("pyproject.toml", r"^\s*version\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']"),
    ("src/config.py", r"__version__\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']"),
    ("src/__init__.py", r"__version__\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']"),
)

# Excluded at any depth: caches, environments, build artefacts, VCS internals.
EXCLUDED_DIRNAMES_ANY_DEPTH = {
    ".git",
    ".github_cache",
    ".venv",
    ".venv_annuaire_sirene",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
    ".idea",
    ".vscode",
    ".agents",
    ".claude",
    "node_modules",
    "build",
    "dist",
    "htmlcov",
    "site-packages",
    EXPORT_DIRNAME,
}
# Excluded only at the project root: "data" is a legitimate sub-package name, so
# matching it at any depth would silently drop source files such as src/data/*.py.
EXCLUDED_TOP_LEVEL_DIRNAMES = {
    "data",
    "datasets",
    "downloads",
    "tmp",
}
# Test reference folders are regenerated locally and carry no reviewable information.
EXCLUDED_RELATIVE_DIRS = {
    "tests/reference",
    "tests/baseline",
    "tests/snapshots",
    "tests/__snapshots__",
}

TEXT_EXTENSIONS = {
    ".py",
    ".txt",
    ".md",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".cfg",
    ".ini",
}
# Files without a real suffix that must still be treated as text.
TEXT_FILENAMES = {".gitignore", ".gitattributes", ".editorconfig", "VERSION", "LICENSE"}
# Launchers and shell glue: useful in a backup, pure noise in an AI context.
BACKUP_ONLY_EXTENSIONS = {".bat", ".command", ".sh", ".ps1", ".sql", ".csv"}

EXCLUDED_EXTENSIONS_ALWAYS = {".parquet", ".xlsx", ".xls", ".pyc", ".pyo", ".log"}

# Documentation-only profiles drop these: git metadata already covered by the docs.
GIT_METADATA_FILES = {
    ".gitignore",
    ".gitattributes",
    "CHANGELOG.md",
    ".github/pull_request_template.md",
}
# Internal tooling excluded from --ai / --outline unless explicitly scoped in.
TOOLING_DIRS = ("scripts",)
LAUNCHER_EXTENSIONS = {".bat", ".command", ".sh", ".ps1"}

# Always shipped, even in a narrowed export: without the code map and conventions,
# a partial export is not actionable by an AI.
ALWAYS_INCLUDED_PATHS = (
    "AGENTS.md",
    "docs/CODEMAP.md",
    "docs/CONVENTIONS.md",
    "docs/CLAUDE.md",
)

# Shared foundation added to every preset: config, packaging, CI and cross-cutting tests.
PRESET_COMMON_BASE = (
    "VERSION",
    "pyproject.toml",
    "src/__init__.py",
    "src/config.py",
    ".github/workflows/ci.yml",
    "tests",
)
PRESETS: dict[str, tuple[str, ...]] = {
    "data": ("src/io_utils.py", "src/sirene_queries.py", "src/sirene_schema.py"),
    "pipeline": ("src/pipeline.py", "src/siret_utils.py", "src/sirene_schema.py"),
    "ui": ("app.py", "src/ui_helpers.py", "src/version_check.py"),
    "export": ("src/export_utils.py", "src/io_utils.py"),
    "version": ("src/version_check.py", "src/updater.py", "VERSION", "CHANGELOG.md"),
    "tooling": ("scripts",),
    "dormant": ("dormant",),
}

OUTLINE_PURPOSE = """\
OBJECTIF DE CE DOCUMENT

Ce document est une CARTE D'ARCHITECTURE, pas un export de code.
Le corps des fonctions a ete volontairement retire : seules subsistent la
documentation, les signatures, les constantes publiques et les dependances entre
modules.

Utilise-le pour raisonner sur la structure, les responsabilites, les couches et
les impacts d'un changement. N'ecris PAS de code a partir de ce document et ne
suppose jamais le contenu d'une fonction : le corps complet est disponible dans
l'export `--ai` du meme projet, demande-le si tu en as besoin.
"""

YAML_STRUCTURAL_KEYS = {
    "name",
    "on",
    "jobs",
    "steps",
    "uses",
    "cron",
    "runs-on",
    "strategy",
    "matrix",
    "python-version",
    "with",
    "run",
    "env",
}


@dataclass(frozen=True)
class FileRecord:
    """One collected file, resolved against the project root."""

    relative_path: Path
    source_path: Path
    size_bytes: int
    line_count: int


@dataclass(frozen=True)
class GitInfo:
    """Git context of the export; fields fall back to "?" outside a repository."""

    branch: str = "?"
    short_hash: str = "?"
    subject: str = "?"


@dataclass
class Collection:
    """Result of a collection pass: kept files plus what the scope left out."""

    records: list[FileRecord] = field(default_factory=list)
    out_of_scope: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Project metadata
# ---------------------------------------------------------------------------


def read_project_version(project_dir: Path) -> str:
    """Extract the project version from the declared entry points, in order."""
    for relative_name, pattern in VERSION_ENTRY_POINTS:
        candidate = project_dir / relative_name
        if not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        match = re.search(pattern, content, flags=re.MULTILINE)
        if match:
            return match.group(1)
    return VERSION_FALLBACK


def read_git_info(project_dir: Path) -> GitInfo:
    """Return git branch/hash/subject, tolerating the absence of a repository."""

    def run(args: list[str]) -> str:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=project_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return "?"
        if completed.returncode != 0:
            return "?"
        return completed.stdout.strip() or "?"

    return GitInfo(
        branch=run(["rev-parse", "--abbrev-ref", "HEAD"]),
        short_hash=run(["rev-parse", "--short", "HEAD"]),
        subject=run(["log", "-1", "--pretty=%s"]),
    )


def export_sequence(export_root: Path, version_tag: str, increment: bool) -> int:
    """Return the rank of this export among the full exports of the same version.

    A narrowed export is not a new full snapshot of the project, so it reports the
    current rank instead of consuming a new one.
    """
    if not export_root.exists():
        return 1 if increment else 0

    marker = "_full_"
    done = sum(
        1
        for existing in export_root.iterdir()
        if marker in existing.name and version_tag in existing.name
    )
    return done + 1 if increment else done


# ---------------------------------------------------------------------------
# File selection
# ---------------------------------------------------------------------------


def is_excluded_directory(relative_path: Path) -> bool:
    """Decide if a path sits inside an always-excluded directory."""
    parts = relative_path.parts
    if any(part in EXCLUDED_DIRNAMES_ANY_DEPTH for part in parts[:-1]):
        return True
    if parts and parts[0] in EXCLUDED_TOP_LEVEL_DIRNAMES and len(parts) > 1:
        return True

    posix = relative_path.as_posix()
    return any(posix.startswith(f"{excluded}/") for excluded in EXCLUDED_RELATIVE_DIRS)


def is_text_file(relative_path: Path, backup: bool) -> bool:
    """Decide if a file's extension is exportable for the active profile."""
    suffix = relative_path.suffix.lower()
    if suffix in EXCLUDED_EXTENSIONS_ALWAYS:
        return False
    if relative_path.name in TEXT_FILENAMES:
        return True
    if suffix in TEXT_EXTENSIONS:
        return True
    return backup and suffix in BACKUP_ONLY_EXTENSIONS


def is_documentation_noise(relative_path: Path) -> bool:
    """Decide if a file is git plumbing already described by the documentation."""
    posix = relative_path.as_posix()
    return posix in GIT_METADATA_FILES or relative_path.name in GIT_METADATA_FILES


def is_internal_tooling(relative_path: Path) -> bool:
    """Decide if a file is internal tooling or a launcher script."""
    if relative_path.parts and relative_path.parts[0] in TOOLING_DIRS:
        return True
    return relative_path.suffix.lower() in LAUNCHER_EXTENSIONS


def normalize_scope(raw_values: list[str] | None) -> list[str]:
    """Flatten repeated and comma-separated --only values into posix path prefixes."""
    if not raw_values:
        return []
    scope: list[str] = []
    for raw in raw_values:
        for chunk in raw.split(","):
            cleaned = chunk.strip().replace("\\", "/").strip("/")
            if cleaned:
                scope.append(cleaned)
    return scope


def matches_scope(relative_path: Path, scope: list[str]) -> bool:
    """Decide if a file is inside the requested scope (file or directory prefix)."""
    posix = relative_path.as_posix()
    return any(posix == entry or posix.startswith(f"{entry}/") for entry in scope)


def collect_files(project_dir: Path, profile: str, scope: list[str]) -> Collection:
    """Walk the project and apply directory, extension, profile and scope filters."""
    backup = profile == "backup"
    always_included = set(ALWAYS_INCLUDED_PATHS)
    collection = Collection()

    for source_path in sorted(project_dir.rglob("*")):
        if not source_path.is_file():
            continue

        relative_path = source_path.relative_to(project_dir)
        if is_excluded_directory(relative_path):
            continue
        if not is_text_file(relative_path, backup):
            continue

        if not backup:
            posix = relative_path.as_posix()
            explicitly_scoped = bool(scope) and matches_scope(relative_path, scope)
            is_noise = is_documentation_noise(relative_path) or is_internal_tooling(relative_path)

            # Git plumbing and internal tooling are noise by default, but must come
            # through when the scope names them explicitly.
            if is_noise and not explicitly_scoped:
                continue
            if scope and not explicitly_scoped and posix not in always_included:
                # Only files the full profile would have exported are reported, so the
                # "out of scope" list stays a useful diff instead of a dump.
                collection.out_of_scope.append(relative_path)
                continue

        try:
            text = read_text(source_path)
        except OSError:
            continue

        collection.records.append(
            FileRecord(
                relative_path=relative_path,
                source_path=source_path,
                size_bytes=source_path.stat().st_size,
                line_count=text.count("\n") + 1 if text else 0,
            )
        )

    return collection


def read_text(path: Path) -> str:
    """Read a text file as UTF-8, never failing on a stray byte."""
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Outline rendering
# ---------------------------------------------------------------------------


def truncate(line: str, limit: int = OUTLINE_MAX_LINE_CHARS) -> str:
    """Shorten a line on a word boundary so the meaning survives the cut."""
    stripped = line.rstrip()
    if len(stripped) <= limit:
        return stripped
    cut = stripped[:limit]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip() + " ..."


def first_docstring_line(node: ast.AST) -> str:
    """Return the first line of a node's docstring, empty when undocumented."""
    if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    docstring = ast.get_docstring(node)
    if not docstring:
        return ""
    return truncate(docstring.strip().splitlines()[0])


def signature_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Rebuild a def line from the AST, without touching the body."""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return truncate(f"{prefix} {node.name}({args}){returns}:", OUTLINE_MAX_LINE_CHARS * 2)


def outline_python(text: str, relative_path: Path) -> list[str]:
    """Render a Python module as docstring + imports + public constants + signatures."""
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [f"[outline indisponible : erreur de syntaxe ligne {error.lineno}]"]

    lines: list[str] = []
    module_doc = first_docstring_line(tree)
    if module_doc:
        lines.append(f'"""{module_doc}"""')
        lines.append("")

    imports = [
        ast.unparse(node)
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    if imports:
        lines.extend(truncate(entry) for entry in imports)
        lines.append("")

    constants = [
        truncate(ast.unparse(node))
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id.isupper()
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    ]
    if constants:
        lines.extend(constants)
        lines.append("")

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(base) for base in node.bases)
            lines.append(f"class {node.name}({bases}):" if bases else f"class {node.name}:")
            class_doc = first_docstring_line(node)
            if class_doc:
                lines.append(f'    """{class_doc}"""')
            members = [
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if not members:
                lines.append("    ...")
            for child in members:
                lines.append(f"    {signature_of(child)}")
                child_doc = first_docstring_line(child)
                if child_doc:
                    lines.append(f'        """{child_doc}"""')
                lines.append("        ...")
            lines.append("")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(signature_of(node))
            func_doc = first_docstring_line(node)
            if func_doc:
                lines.append(f'    """{func_doc}"""')
            lines.append("    ...")
            lines.append("")

    if not lines:
        lines.append(f"[aucune structure exposee dans {relative_path.as_posix()}]")
    return lines


def outline_markdown(text: str) -> list[str]:
    """Keep only headings and bullets: the document's skeleton."""
    kept: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        is_heading = stripped.startswith("#")
        is_bullet = stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+[.)]\s", stripped)
        if is_heading or is_bullet:
            kept.append(truncate(raw))
    return kept or ["[document sans titre ni puce]"]


def outline_yaml(text: str) -> list[str]:
    """Keep top-level keys plus the keys that carry CI meaning."""
    kept: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        key_match = re.match(r"^-?\s*([A-Za-z0-9_.\-]+)\s*:", stripped)
        key = key_match.group(1) if key_match else ""
        # Depth <= 2 keeps the top-level blocks and the job/section names under them.
        if indent <= 2 or key in YAML_STRUCTURAL_KEYS:
            kept.append(truncate(raw))
    return kept or ["[aucune cle structurante]"]


def outline_rules(text: str) -> list[str]:
    """Condense rule/convention files line by line with a bounded truncation."""
    kept: list[str] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        kept.append(truncate(raw))
    return kept or ["[fichier vide]"]


DOC_SUFFIXES = {".md"}


def render_outline(record: FileRecord) -> list[str]:
    """Dispatch a file to the right outline renderer."""
    text = read_text(record.source_path)
    suffix = record.relative_path.suffix.lower()

    if suffix == ".py":
        return outline_python(text, record.relative_path)
    if suffix in DOC_SUFFIXES:
        return outline_markdown(text)
    if suffix in {".yml", ".yaml"}:
        return outline_yaml(text)
    return outline_rules(text)


# ---------------------------------------------------------------------------
# Document writing
# ---------------------------------------------------------------------------


def language_for(relative_path: Path) -> str:
    """Return the fenced-code language for a file."""
    by_suffix = {
        ".py": "python",
        ".md": "markdown",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".cfg": "ini",
        ".ini": "ini",
    }
    return by_suffix.get(relative_path.suffix.lower(), "text")


def build_manifest(
    project_name: str,
    project_version: str,
    sequence: int,
    timestamp: str,
    git: GitInfo,
    scope_label: str,
    is_full: bool,
    collection: Collection,
    document_chars: int,
    profile: str,
) -> list[str]:
    """Build the header manifest: provenance, inventory and token budget."""
    sequence_label = (
        f"export complet n°{sequence} pour cette version"
        if is_full
        else f"export partiel (n'incremente pas la sequence, {sequence} complet(s) a ce jour)"
    )
    lines = [
        f"# Export {profile} - {project_name}",
        "",
        "## Manifeste",
        "",
        f"- Profil            : {profile}",
        f"- Perimetre         : {scope_label}",
        f"- Version projet    : {project_version}",
        f"- Sequence          : {sequence_label}",
        f"- Horodatage        : {timestamp}",
        f"- Branche git       : {git.branch}",
        f"- Commit git        : {git.short_hash}",
        f"- Dernier commit    : {git.subject}",
        f"- Fichiers inclus   : {len(collection.records)}",
        f"- Caracteres        : {document_chars}",
        f"- Tokens estimes    : ~{document_chars // CHARS_PER_TOKEN} (~{CHARS_PER_TOKEN} car./token)",
        "",
        "## Sommaire des fichiers inclus",
        "",
        "| Fichier | Lignes | Taille (o) |",
        "| --- | ---: | ---: |",
    ]
    for record in collection.records:
        lines.append(
            f"| {record.relative_path.as_posix()} | {record.line_count} | {record.size_bytes} |"
        )
    lines.append("")

    if collection.out_of_scope:
        lines.append("## Fichiers hors perimetre (non inclus)")
        lines.append("")
        for relative_path in collection.out_of_scope:
            lines.append(f"- {relative_path.as_posix()}")
        lines.append("")

    return lines


def write_document(
    output_path: Path,
    manifest_lines: list[str],
    body_lines: list[str],
) -> None:
    """Write the export document as UTF-8."""
    output_path.write_text("\n".join([*manifest_lines, *body_lines]) + "\n", encoding="utf-8")


def build_ai_body(collection: Collection) -> list[str]:
    """Render every collected file in full, fenced by language."""
    lines = ["## Contenu des fichiers", ""]
    for record in collection.records:
        lines.append(f"===== FILE: {record.relative_path.as_posix()} =====")
        lines.append(f"```{language_for(record.relative_path)}")
        lines.append(read_text(record.source_path).rstrip("\n"))
        lines.append("```")
        lines.append("")
    return lines


def build_outline_body(collection: Collection) -> list[str]:
    """Render documentation whole and code as structure only."""
    lines = ["## Structure des fichiers", ""]
    for record in collection.records:
        suffix = record.relative_path.suffix.lower()
        marker = "DOC" if suffix in DOC_SUFFIXES else "OUTLINE"
        lines.append(f"===== {marker}: {record.relative_path.as_posix()} =====")
        lines.append(f"```{language_for(record.relative_path)}")
        if suffix in DOC_SUFFIXES and record.relative_path.as_posix() in ALWAYS_INCLUDED_PATHS:
            # Reference documents keep their full text: they are the architecture.
            lines.append(read_text(record.source_path).rstrip("\n"))
        else:
            lines.extend(render_outline(record))
        lines.append("```")
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Backup profile
# ---------------------------------------------------------------------------


def write_backup_archive(collection: Collection, zip_path: Path) -> None:
    """Write a restorable zip preserving the project-relative structure."""
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for record in collection.records:
            archive.write(record.source_path, arcname=record.relative_path.as_posix())


def rotate_backups(export_root: Path, keep: int) -> list[Path]:
    """Delete the oldest backup archives, keeping the N most recent."""
    # The name carries the export timestamp and breaks mtime ties (copied or
    # restored archives can share a modification time).
    archives = sorted(
        (path for path in export_root.glob("backup_*.zip") if path.is_file()),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    purged: list[Path] = []
    for stale in archives[keep:]:
        stale.unlink()
        purged.append(stale)
    return purged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments with mutually exclusive profile and scope groups."""
    parser = argparse.ArgumentParser(
        prog="export_project",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument(
        "--ai",
        dest="profile",
        action="store_const",
        const="ai",
        help="Contexte IA cure : code + documentation structurante (profil par defaut).",
    )
    profiles.add_argument(
        "--outline",
        dest="profile",
        action="store_const",
        const="outline",
        help="Carte d'architecture compacte, sans corps de fonctions.",
    )
    profiles.add_argument(
        "--backup",
        dest="profile",
        action="store_const",
        const="backup",
        help=f"Archive .zip restaurable, rotation des {BACKUP_RETENTION} plus recentes.",
    )
    parser.set_defaults(profile="ai")

    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--only",
        action="append",
        metavar="CHEMIN",
        help="Restreint la collecte a ces fichiers/dossiers (repetable ou separe par des virgules).",
    )
    scope.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="Preselection par sous-module (socle commun + fichiers du domaine).",
    )

    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Affiche les preselections disponibles et leur contenu, puis quitte.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=BACKUP_RETENTION,
        metavar="N",
        help=f"Nombre de sauvegardes conservees en mode --backup (defaut: {BACKUP_RETENTION}).",
    )

    args = parser.parse_args(argv)

    if args.profile == "backup" and (args.only or args.preset):
        parser.error(
            "--only et --preset sont reserves aux profils --ai et --outline : "
            "une sauvegarde partielle ne serait pas restaurable."
        )
    if args.keep < 1:
        parser.error("--keep doit valoir au moins 1.")

    return args


def print_presets() -> None:
    """Print available presets with their resolved content."""
    print("Socle commun ajoute a chaque preselection :")
    for entry in PRESET_COMMON_BASE:
        print(f"  - {entry}")
    print()
    for name, paths in sorted(PRESETS.items()):
        print(f"--preset {name}")
        for entry in paths:
            print(f"  - {entry}")
        print()


def resolve_scope(args: argparse.Namespace) -> tuple[list[str], str, bool]:
    """Return (scope prefixes, scope label, is_full_export)."""
    if args.preset:
        scope = list(dict.fromkeys([*PRESET_COMMON_BASE, *PRESETS[args.preset], *ALWAYS_INCLUDED_PATHS]))
        return scope, args.preset, False
    only = normalize_scope(args.only)
    if only:
        return [*only, *ALWAYS_INCLUDED_PATHS], "custom", False
    return [], "full", True


def run_export(args: argparse.Namespace) -> int:
    """Main routine; returns a process exit code."""
    # This script lives in scripts/; the project root is one level up.
    project_dir = Path(__file__).resolve().parent.parent
    export_root = project_dir / EXPORT_DIRNAME
    export_root.mkdir(parents=True, exist_ok=True)

    project_name = project_dir.name or PROJECT_NAME_FALLBACK
    project_version = read_project_version(project_dir)
    git = read_git_info(project_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    scope, scope_label, is_full = resolve_scope(args)
    version_tag = f"v{project_version}"
    # A partial export is not a new full snapshot: it must not consume a sequence number.
    sequence = export_sequence(export_root, version_tag, increment=is_full)

    collection = collect_files(project_dir, args.profile, scope)
    if not collection.records:
        print("Aucun fichier ne correspond aux regles d'export. Rien n'a ete genere.")
        return 1

    stem = f"{args.profile}_{project_name}_{scope_label}_{timestamp}_{version_tag}"

    if args.profile == "backup":
        zip_path = export_root / f"{stem}.zip"
        write_backup_archive(collection, zip_path)
        purged = rotate_backups(export_root, args.keep)
        print(f"Sauvegarde : {zip_path}")
        print(f"Fichiers archives : {len(collection.records)}")
        print(f"Rotation : {len(purged)} archive(s) supprimee(s), {args.keep} conservee(s).")
        return 0

    if args.profile == "outline":
        body = build_outline_body(collection)
        preface = [OUTLINE_PURPOSE, ""]
    else:
        body = build_ai_body(collection)
        preface = []

    # Counted on the rendered body, not on the source files: an outline is a
    # fraction of the code it describes, and the estimate must reflect what the
    # AI actually receives.
    document_chars = sum(len(line) + 1 for line in [*preface, *body])
    manifest = build_manifest(
        project_name=project_name,
        project_version=project_version,
        sequence=sequence,
        timestamp=timestamp,
        git=git,
        scope_label=scope_label,
        is_full=is_full,
        collection=collection,
        document_chars=document_chars,
        profile=args.profile,
    )

    output_path = export_root / f"{stem}.txt"
    write_document(output_path, [*preface, *manifest], body)

    print(f"Export : {output_path}")
    print(f"Profil : {args.profile} | perimetre : {scope_label} | tag : {version_tag}")
    print(f"Fichiers inclus : {len(collection.records)}")
    if collection.out_of_scope:
        print(f"Fichiers hors perimetre : {len(collection.out_of_scope)}")
    print(f"Tokens estimes : ~{document_chars // CHARS_PER_TOKEN}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    if args.list_presets:
        print_presets()
        return 0
    return run_export(args)


if __name__ == "__main__":
    sys.exit(main())
