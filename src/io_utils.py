"""I/O helpers for user files and local parquet sources."""

from __future__ import annotations

import glob
import re
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Literal, overload

import pandas as pd

from .config import SUPPORTED_INPUT_EXTENSIONS

# Category keys map to the SIRENE stock file each Parquet source represents.
# Order matters: more specific keywords (historique, succession) must be
# checked before the generic "etablissement" keyword, since filenames such as
# "StockEtablissementHistorique" or "stock-stocketablissementlienssuccession-parquet"
# also contain "etablissement" as a substring.
_SIRENE_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("stocketablissementhistorique", ("historique",)),
    ("stocketablissementlienssuccession", ("lienssuccession", "succession")),
    ("stockunitelegale", ("unitelegale",)),
    ("stocketablissement", ("etablissement",)),
]

SIRENE_REQUIRED_CATEGORIES = ("stocketablissement", "stockunitelegale")
SIRENE_OPTIONAL_CATEGORIES = ("stocketablissementlienssuccession", "stocketablissementhistorique")


def _normalize_filename_token(name: str) -> str:
    """Lowercase, strip accents and non-alphanumeric characters from a filename."""
    normalized = unicodedata.normalize("NFKD", name.lower())
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", ascii_only)


def _classify_parquet_filename(filename: str) -> str | None:
    """Return the SIRENE category matching a parquet filename, if any."""
    token = _normalize_filename_token(Path(filename).stem)
    for category, keywords in _SIRENE_CATEGORY_KEYWORDS:
        if any(keyword in token for keyword in keywords):
            return category
    return None


@dataclass
class SireneAutoDetection:
    """Result of scanning a directory for SIRENE Parquet stock files."""

    paths: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def detect_sirene_parquet_files(root_dir: str | Path) -> SireneAutoDetection:
    """
    Scan ``root_dir`` for SIRENE Parquet stock files and classify them.

    Matching is keyword-based on the normalized filename (accents/punctuation
    stripped), so it tolerates naming variations such as
    ``stock-stocketablissement-parquet.parquet`` in addition to the official
    ``StockEtablissement_utf8.parquet`` convention. Returns the best path found
    per category plus human-readable warnings for anything ambiguous or missing.
    """
    root = Path(root_dir)
    result = SireneAutoDetection()
    if not root.is_dir():
        return result

    matches: dict[str, list[Path]] = {}
    unrecognized: list[Path] = []
    for file_path in sorted(root.glob("*.parquet")):
        category = _classify_parquet_filename(file_path.name)
        if category is None:
            unrecognized.append(file_path)
            continue
        matches.setdefault(category, []).append(file_path)

    for category, candidates in matches.items():
        result.paths[category] = str(candidates[0])
        if len(candidates) > 1:
            names = ", ".join(p.name for p in candidates)
            result.warnings.append(
                f"Plusieurs fichiers correspondent à '{category}' ({names}) — "
                f"vérifiez que '{candidates[0].name}' est bien le bon fichier."
            )

    for category in SIRENE_REQUIRED_CATEGORIES:
        if category not in matches:
            result.warnings.append(
                f"Aucun fichier Parquet détecté pour '{category}' (obligatoire) "
                "à la racine du dossier — renseignez le chemin manuellement."
            )

    if unrecognized:
        names = ", ".join(p.name for p in unrecognized)
        result.warnings.append(
            f"Fichier(s) Parquet non reconnus, ignorés (nom ne correspond à aucun "
            f"type SIRENE connu) : {names}"
        )

    return result


def _to_bytes_buffer(file_obj: object) -> BytesIO:
    """Convert a file-like object into an in-memory binary buffer."""
    if hasattr(file_obj, "getvalue"):
        return BytesIO(file_obj.getvalue())  # Streamlit UploadedFile
    if hasattr(file_obj, "read"):
        raw = file_obj.read()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        return BytesIO(raw)
    raise ValueError("Unsupported input file object.")


def get_input_file_extension(file_obj: object) -> str:
    """Return lowercase file extension from uploaded file name."""
    name = getattr(file_obj, "name", "")
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_INPUT_EXTENSIONS:
        raise ValueError(
            f"Unsupported input extension '{suffix}'. Supported: {sorted(SUPPORTED_INPUT_EXTENSIONS)}"
        )
    return suffix


def list_excel_sheets(file_obj: object) -> list[str]:
    """List available sheets from an uploaded Excel file."""
    buffer = _to_bytes_buffer(file_obj)
    workbook = pd.ExcelFile(buffer)
    return [str(name) for name in workbook.sheet_names]


def _drop_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that are fully empty or whitespace-only."""
    cleaned = df.replace(r"^\s*$", pd.NA, regex=True)
    cleaned = cleaned.dropna(axis=0, how="all")
    cleaned = cleaned.reset_index(drop=True)
    return cleaned


def _normalize_columns(df: pd.DataFrame, has_header: bool) -> pd.DataFrame:
    """Normalize output columns according to header mode."""
    out = df.copy()
    if has_header:
        out.columns = [str(col) for col in out.columns]
    else:
        out.columns = [f"column_{idx + 1}" for idx in range(len(out.columns))]
    return out


def read_user_input_file(
    file_obj: object,
    *,
    sheet_name: str | None = None,
    has_header: bool = True,
    ignore_empty_rows: bool = True,
) -> pd.DataFrame:
    """Read user file (xlsx, csv, parquet) with configurable parsing."""
    suffix = get_input_file_extension(file_obj)

    buffer = _to_bytes_buffer(file_obj)
    if suffix == ".xlsx":
        read_sheet = sheet_name if sheet_name else 0
        header = 0 if has_header else None
        df = pd.read_excel(buffer, dtype=str, sheet_name=read_sheet, header=header)
    elif suffix == ".csv":
        header = 0 if has_header else None
        try:
            df = pd.read_csv(
                buffer,
                dtype=str,
                sep=None,
                engine="python",
                header=header,
                skip_blank_lines=ignore_empty_rows,
            )
        except Exception:
            buffer.seek(0)
            df = pd.read_csv(
                buffer,
                dtype=str,
                sep=",",
                header=header,
                skip_blank_lines=ignore_empty_rows,
            )
    else:
        df = pd.read_parquet(buffer, engine="pyarrow")
        df = df.astype("string")

    df = _normalize_columns(df, has_header=has_header if suffix in {".xlsx", ".csv"} else True)
    if ignore_empty_rows:
        df = _drop_empty_rows(df)

    if df.empty:
        raise ValueError("The input file is empty after filtering blank rows.")

    return df


def normalize_path_text(path_text: str) -> str:
    """Normalize user-entered path text."""
    return path_text.strip().strip('"').strip("'")


# Une source obligatoire ne peut pas etre absente : le chemin manquant leve, la valeur de
# retour n'est donc jamais None. Les surcharges evitent aux appelants d'avoir a s'en assurer.
@overload
def resolve_parquet_source(
    path_text: str, label: str, required: Literal[True] = ...
) -> str: ...


@overload
def resolve_parquet_source(
    path_text: str, label: str, required: Literal[False]
) -> str | None: ...


@overload
def resolve_parquet_source(path_text: str, label: str, required: bool) -> str | None: ...


def resolve_parquet_source(path_text: str, label: str, required: bool = True) -> str | None:
    """
    Resolve a parquet source path for DuckDB.

    Accepted forms:
    - single parquet file
    - directory containing parquet files (recursive glob generated)
    - explicit wildcard path
    """
    clean_text = normalize_path_text(path_text)
    if not clean_text:
        if required:
            raise ValueError(f"Missing required path for '{label}'.")
        return None

    if "*" in clean_text or "?" in clean_text:
        matches = glob.glob(clean_text, recursive=True)
        if not matches:
            raise ValueError(f"No parquet files matched wildcard for '{label}': {clean_text}")
        return clean_text.replace("\\", "/")

    path = Path(clean_text)
    if not path.exists():
        raise ValueError(f"Path does not exist for '{label}': {path}")

    if path.is_dir():
        # Short-circuit on the first match instead of listing the whole subtree: a directory
        # that turns out to hold no parquet file (wrong folder, still-empty download...) would
        # otherwise force a full recursive walk just to conclude there is nothing to find.
        if next(path.rglob("*.parquet"), None) is None:
            raise ValueError(f"No .parquet file found in directory for '{label}': {path}")
        return str(path / "**/*.parquet").replace("\\", "/")

    if path.suffix.lower() != ".parquet":
        raise ValueError(f"Path for '{label}' must be a parquet file or directory: {path}")

    return str(path)


def resolve_output_excel_path(path_text: str) -> Path | None:
    """Resolve optional output path for exported workbook."""
    clean_text = normalize_path_text(path_text)
    if not clean_text:
        return None
    output_path = Path(clean_text)
    if output_path.suffix.lower() != ".xlsx":
        output_path = output_path.with_suffix(".xlsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path
