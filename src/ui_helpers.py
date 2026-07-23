"""UI helper functions for Streamlit rendering."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from .config import (
    DATA_STATUS_ABSENT,
    DATA_STATUS_OUTDATED,
    DATA_STATUS_UNKNOWN,
    DATA_STATUS_UP_TO_DATE,
)
from .data_manifest import DataFreshnessStatus, format_publication_date, format_size_mo

# Pastille et couleur par statut. Le vert n'est jamais utilisé pour un fichier à
# télécharger : la couleur doit dire au premier coup d'œil s'il reste une action à faire.
# "version inconnue" (fichier installé à la main) reste neutre en bleu : ni une alerte
# (orange/rouge, qui affirmerait à tort une version périmée) ni un feu vert.
_DATA_STATUS_BADGES = {
    DATA_STATUS_UP_TO_DATE: ("✅", "green"),
    DATA_STATUS_OUTDATED: ("🔄", "orange"),
    DATA_STATUS_ABSENT: ("⬇️", "red"),
    DATA_STATUS_UNKNOWN: ("❔", "blue"),
}


def step_header(step_number: int, title: str) -> None:
    """Render a compact step header."""
    st.markdown(f"### {step_number}. {title}")


def show_dataframe_preview(df: pd.DataFrame, label: str, nrows: int = 8) -> None:
    """Render a dataframe preview with metadata."""
    st.caption(f"{label} - {len(df):,} rows x {len(df.columns)} columns")
    st.dataframe(df.head(nrows), width="stretch")


def show_metrics(metrics: dict[str, int]) -> None:
    """Render the required top metrics."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Identifiants fournis", metrics.get("total_input_siret", 0))
    c2.metric("Formats valides (SIRET/SIREN)", metrics.get("valid_siret_format", 0))
    c3.metric("Trouvés SIRENE", metrics.get("found_in_sirene", 0))
    c4.metric("Non trouvés", metrics.get("not_found", 0))

    c5, c6, c7, c8, c9 = st.columns(5)
    c5.metric("Actifs", metrics.get("active", 0))
    c6.metric("Fermés", metrics.get("closed", 0))
    c7.metric("Format invalide", metrics.get("invalid_format", 0))
    c8.metric("Fermés à investiguer", metrics.get("move_candidates", 0))
    c9.metric("SIREN valides distincts en doublon", metrics.get("duplicate_siren", 0))


def default_output_filename() -> str:
    """Return timestamped default file name."""
    return f"Annuaire_SIRENE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"


def show_warnings(warnings: list[str]) -> None:
    """Render pipeline warnings."""
    if not warnings:
        return
    for warning in warnings:
        st.warning(warning)


def browse_save_excel_path(current_path: str) -> str | None:
    """Open a native save dialog and return selected path when available."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    suggested = Path(current_path).expanduser() if current_path else Path.home() / "Downloads"
    initial_dir = suggested.parent if suggested.suffix else suggested
    initial_file = suggested.name if suggested.suffix else default_output_filename()

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.asksaveasfilename(
            title="Choisir le fichier de sortie Excel",
            initialdir=str(initial_dir),
            initialfile=initial_file,
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        root.destroy()
    except Exception:
        return None

    if not selected:
        return None
    return selected


def render_progress_metrics(
    *,
    progress_percent: int,
    processed: int,
    total: int,
    success: int,
    failed: int,
    candidates_found: int = 0,
    elapsed_seconds: float | None = None,
) -> None:
    """Render execution progress metrics under progress bar."""
    speed_delta: str | None = None
    if elapsed_seconds and elapsed_seconds > 0 and processed > 0:
        rate = processed / elapsed_seconds
        speed_delta = f"{rate:.1f} lig/s"

    pct_success = f"{success / processed * 100:.0f} %" if processed else None
    pct_failed  = f"{failed  / processed * 100:.0f} %" if processed else None
    avg_cands   = f"moy. {candidates_found / success:.1f}" if success else None

    if candidates_found > 0:
        c1, c2, c3, c4, c5 = st.columns(5)
    else:
        c1, c2, c3, c4 = st.columns(4)

    c1.metric("Avancement",  f"{progress_percent} %")
    c2.metric("Traités",     f"{processed} / {total}", delta=speed_delta, delta_color="off")
    c3.metric("Succès",      success,          delta=pct_success,  delta_color="off")
    c4.metric("Échecs",      failed,           delta=pct_failed,   delta_color="inverse")
    if candidates_found > 0:
        c5.metric("Candidats", candidates_found, delta=avg_cands, delta_color="off")


def render_sirene_data_panel(status: DataFreshnessStatus) -> bool:
    """Render the SIRENE data freshness card. Return True when the update button is clicked."""
    with st.container(border=True):
        header_col, date_col = st.columns([3, 2], vertical_alignment="center")
        header_col.markdown("**Données SIRENE**")

        if not status.check_ok:
            date_col.markdown(":gray[vérification impossible]")
            st.caption(
                f"{status.error} Les fichiers déjà présents restent utilisables : "
                "leur fraîcheur n'a simplement pas pu être contrôlée."
            )
            return False

        date_col.markdown(
            f":gray[Publication data.gouv.fr : {format_publication_date(status.latest_publication)}]"
        )

        for item in status.categories:
            icon, color = _DATA_STATUS_BADGES.get(item.status, ("•", "gray"))
            icon_col, name_col, size_col, status_col = st.columns(
                [0.4, 4, 1.4, 3], vertical_alignment="center"
            )
            icon_col.markdown(icon)
            name_col.markdown(item.label)
            size_col.markdown(f":gray[{format_size_mo(item.remote_size_mo)}]")
            status_col.markdown(f":{color}[{item.status}]")

        if status.up_to_date:
            st.caption("Tous les fichiers correspondent à la dernière publication.")
            return False

        st.caption(
            f"{len(status.stale)} fichier(s) à récupérer, "
            f"{format_size_mo(status.total_download_mo)} au total. "
            "Le téléchargement peut durer plusieurs minutes ; les fichiers déjà à jour "
            "sont ignorés."
        )
        return st.button(
            f"Mettre à jour les données SIRENE ({format_size_mo(status.total_download_mo)})",
            type="primary",
            width="stretch",
        )


def render_download_metrics(
    *,
    progress_percent: int,
    downloaded_mo: float,
    total_mo: float | None,
    file_index: int,
    file_count: int,
    elapsed_seconds: float | None = None,
) -> None:
    """Render download progress metrics under progress bar."""
    speed_delta: str | None = None
    if elapsed_seconds and elapsed_seconds > 0 and downloaded_mo > 0:
        speed_delta = f"{downloaded_mo / elapsed_seconds:.1f} Mo/s"

    volume = f"{downloaded_mo:,.0f} / {total_mo:,.0f} Mo" if total_mo else f"{downloaded_mo:,.0f} Mo"

    c1, c2, c3 = st.columns(3)
    c1.metric("Avancement", f"{progress_percent} %")
    c2.metric("Volume", volume, delta=speed_delta, delta_color="off")
    c3.metric("Fichier", f"{file_index} / {file_count}")
