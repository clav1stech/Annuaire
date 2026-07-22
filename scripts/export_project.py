"""Project export/versioning helper for backup and AI handoff.

This script exports only source/documentation files that matter for code review:
- included: .py, .bat, .sh, .md, .txt
- excluded: parquet data, virtual envs, caches, export outputs, requirements.txt

Outputs are created in ./export with automatic semantic patch increment (vX.Y.Z):
- one snapshot folder with copied files
- one manifest file with hashes/sizes
- one consolidated AI context text file
- one zip archive of the snapshot folder (optional)
- one zip archive of "extra important items" like venv/dependency files (optional)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re
import shutil
import zipfile


VERSION_X = 1
VERSION_Y = 2
ENABLE_ZIP_EXPORT = False
ENABLE_EXTRA_ARCHIVE_EXPORT = False

INCLUDED_EXTENSIONS = {".py", ".bat", ".sh", ".md", ".txt"}
EXCLUDED_FILENAMES = {"requirements.txt"}
EXCLUDED_DIRNAMES = {
    ".git",
    ".venv",
    ".venv_annuaire_sirene",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "export",
}
EXTRA_ARCHIVE_EXCLUDED_DIRNAMES = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "export",
}
EXTRA_ARCHIVE_INCLUDED_TOP_LEVEL_DIRS = {
    ".venv",
    ".venv_annuaire_sirene",
    "venv",
    "env",
}
EXTRA_ARCHIVE_INCLUDED_TOP_LEVEL_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
}


@dataclass(frozen=True)
class FileRecord:
    relative_path: Path
    source_path: Path
    size_bytes: int
    sha256: str


def get_next_patch_version(export_dir: Path) -> int:
    """Return next patch number for current major/minor version."""
    if not export_dir.exists():
        return 0

    pattern = re.compile(rf"_v{VERSION_X}\.{VERSION_Y}\.(\d+)")
    max_patch = -1

    for existing in export_dir.iterdir():
        match = pattern.search(existing.name)
        if match:
            max_patch = max(max_patch, int(match.group(1)))

    return max_patch + 1


_SELF_NAME = Path(__file__).name


def should_export(relative_path: Path) -> bool:
    """Decide if a file should be exported."""
    lowered_name = relative_path.name.lower()
    lowered_suffix = relative_path.suffix.lower()

    if relative_path.name == _SELF_NAME:
        return False

    if lowered_name in EXCLUDED_FILENAMES:
        return False

    if lowered_suffix == ".parquet":
        return False

    if lowered_suffix not in INCLUDED_EXTENSIONS:
        return False

    for part in relative_path.parts:
        if part in EXCLUDED_DIRNAMES:
            return False

    return True


def sha256_of(path: Path) -> str:
    """Compute SHA256 digest for file."""
    hasher = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_files(project_dir: Path) -> list[FileRecord]:
    """Collect files that match export rules."""
    records: list[FileRecord] = []
    for source_path in sorted(project_dir.rglob("*")):
        if not source_path.is_file():
            continue

        relative_path = source_path.relative_to(project_dir)
        if not should_export(relative_path):
            continue

        records.append(
            FileRecord(
                relative_path=relative_path,
                source_path=source_path,
                size_bytes=source_path.stat().st_size,
                sha256=sha256_of(source_path),
            )
        )

    return records


def copy_snapshot(records: list[FileRecord], target_files_dir: Path) -> None:
    """Copy selected files to snapshot directory."""
    for record in records:
        destination = target_files_dir / record.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(record.source_path, destination)


def write_manifest(
    manifest_path: Path,
    project_name: str,
    version_tag: str,
    timestamp: str,
    records: list[FileRecord],
) -> None:
    """Write manifest with metadata and checksums."""
    lines = [
        f"project={project_name}",
        f"version={version_tag}",
        f"timestamp={timestamp}",
        f"included_extensions={','.join(sorted(INCLUDED_EXTENSIONS))}",
        f"excluded_filenames={','.join(sorted(EXCLUDED_FILENAMES))}",
        f"excluded_dirs={','.join(sorted(EXCLUDED_DIRNAMES))}",
        f"file_count={len(records)}",
        "",
        "relative_path|size_bytes|sha256",
    ]

    for record in records:
        lines.append(f"{record.relative_path.as_posix()}|{record.size_bytes}|{record.sha256}")

    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def language_for_suffix(suffix: str) -> str:
    """Return fenced-code language for a given suffix."""
    by_suffix = {
        ".py": "python",
        ".bat": "bat",
        ".md": "markdown",
        ".txt": "text",
    }
    return by_suffix.get(suffix.lower(), "text")


def write_ai_context(
    ai_context_path: Path,
    project_name: str,
    version_tag: str,
    timestamp: str,
    records: list[FileRecord],
) -> None:
    """Write one AI-ready file with tree + all relevant file contents."""
    lines: list[str] = []
    lines.append(f"# Project export for AI - {project_name}")
    lines.append("")
    lines.append(f"- Version: {version_tag}")
    lines.append(f"- Timestamp: {timestamp}")
    lines.append(f"- File count: {len(records)}")
    lines.append(f"- Included extensions: {', '.join(sorted(INCLUDED_EXTENSIONS))}")
    lines.append("- Excluded by rule: parquet, venv folders, caches, export folder, requirements.txt")
    lines.append("")
    lines.append("## Exported paths")
    lines.append("")
    for record in records:
        lines.append(f"- {record.relative_path.as_posix()}")
    lines.append("")
    lines.append("## File contents")
    lines.append("")

    for record in records:
        lines.append(f"===== FILE: {record.relative_path.as_posix()} =====")
        language = language_for_suffix(record.relative_path.suffix)
        lines.append(f"```{language}")
        try:
            lines.append(record.source_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            lines.append(record.source_path.read_text(encoding="utf-8", errors="replace"))
        lines.append("```")
        lines.append("")

    ai_context_path.write_text("\n".join(lines), encoding="utf-8")


def write_zip(snapshot_dir: Path, zip_path: Path) -> None:
    """Zip snapshot directory with relative structure."""
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in snapshot_dir.rglob("*"):
            if file_path.is_file():
                arcname = snapshot_dir.name + "/" + file_path.relative_to(snapshot_dir).as_posix()
                archive.write(file_path, arcname=arcname)


def str_to_bool(value: str) -> bool:
    """Parse explicit true/false-like strings from CLI."""
    normalized = value.strip().lower()
    truthy = {"true", "1", "yes", "y", "on"}
    falsy = {"false", "0", "no", "n", "off"}
    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    raise argparse.ArgumentTypeError("Expected true/false (also accepts 1/0, yes/no, on/off).")


def should_include_in_extra_archive(relative_path: Path) -> bool:
    """Decide if a file should be included in the optional extra archive."""
    if relative_path.suffix.lower() == ".parquet":
        return False

    for part in relative_path.parts:
        if part in EXTRA_ARCHIVE_EXCLUDED_DIRNAMES:
            return False

    top_level = relative_path.parts[0] if relative_path.parts else ""
    if top_level in EXTRA_ARCHIVE_INCLUDED_TOP_LEVEL_DIRS:
        return True

    if relative_path.name in EXTRA_ARCHIVE_INCLUDED_TOP_LEVEL_FILES:
        return True

    return False


def collect_extra_archive_files(project_dir: Path) -> list[Path]:
    """Collect optional extra files to zip (venv + dependency definition files)."""
    extra_files: list[Path] = []
    for source_path in sorted(project_dir.rglob("*")):
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(project_dir)
        if should_include_in_extra_archive(relative_path):
            extra_files.append(source_path)
    return extra_files


def write_extra_archive(project_dir: Path, extra_files: list[Path], zip_path: Path) -> None:
    """Write zip archive containing project extra files with project-relative structure."""
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source_path in extra_files:
            archive.write(source_path, arcname=source_path.relative_to(project_dir).as_posix())


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Export project snapshot and optional extra archive.")
    parser.add_argument(
        "--enable-zip-export",
        type=str_to_bool,
        default=ENABLE_ZIP_EXPORT,
        metavar="true|false",
        help=f"Create snapshot zip archive (default: {str(ENABLE_ZIP_EXPORT).lower()}).",
    )
    parser.add_argument(
        "--include-extra-items",
        type=str_to_bool,
        default=ENABLE_EXTRA_ARCHIVE_EXPORT,
        metavar="true|false",
        help=(
            "Create an additional zip with extra important items (venv folders + dependency files). "
            f"Default: {str(ENABLE_EXTRA_ARCHIVE_EXPORT).lower()}."
        ),
    )
    return parser.parse_args()


def run_export(enable_zip_export: bool, include_extra_items: bool) -> None:
    """Main routine."""
    # This script lives in scripts/; the project root is one level up.
    project_dir = Path(__file__).resolve().parent.parent
    export_root = project_dir / "export"
    export_root.mkdir(parents=True, exist_ok=True)

    patch = get_next_patch_version(export_root)
    project_name = project_dir.name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_tag = f"v{VERSION_X}.{VERSION_Y}.{patch}"
    export_stem = f"export_{project_name}_{timestamp}_{version_tag}"

    records = collect_files(project_dir)
    if not records:
        print("No file matched export rules. Nothing exported.")
        return

    snapshot_dir = export_root / export_stem
    snapshot_files_dir = snapshot_dir / "files"
    snapshot_files_dir.mkdir(parents=True, exist_ok=True)

    copy_snapshot(records, snapshot_files_dir)

    manifest_path = snapshot_dir / "manifest.txt"
    ai_context_path = snapshot_dir / f"{export_stem}_ai_context.txt"
    write_manifest(manifest_path, project_name, version_tag, timestamp, records)
    write_ai_context(ai_context_path, project_name, version_tag, timestamp, records)

    zip_path = export_root / f"{export_stem}.zip"
    if enable_zip_export:
        write_zip(snapshot_dir, zip_path)

    extra_zip_path = export_root / f"{export_stem}_extra_items.zip"
    extra_files: list[Path] = []
    if include_extra_items:
        extra_files = collect_extra_archive_files(project_dir)
        if extra_files:
            write_extra_archive(project_dir, extra_files, extra_zip_path)

    print("Export done.")
    print(f"Version: {version_tag}")
    print(f"Snapshot folder: {snapshot_dir}")
    print(f"AI context file: {ai_context_path}")
    print(f"Manifest file: {manifest_path}")
    if enable_zip_export:
        print(f"Zip archive: {zip_path}")
    if include_extra_items:
        if extra_files:
            print(f"Extra items zip archive: {extra_zip_path}")
            print(f"Extra items count: {len(extra_files)}")
        else:
            print("Extra items zip archive: skipped (no matching files found).")
    print(f"Exported files count: {len(records)}")


if __name__ == "__main__":
    args = parse_args()
    run_export(
        enable_zip_export=args.enable_zip_export,
        include_extra_items=args.include_extra_items,
    )
