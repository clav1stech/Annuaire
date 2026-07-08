"""I/O helpers for user files and local parquet sources."""

from __future__ import annotations

import glob
from io import BytesIO
from pathlib import Path

import pandas as pd

from .config import SUPPORTED_INPUT_EXTENSIONS


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
        parquet_files = list(path.rglob("*.parquet"))
        if not parquet_files:
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
