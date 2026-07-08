"""Streamlit entrypoint for Annuaire_SIRENE."""

from __future__ import annotations

import hashlib
import re
from time import monotonic
import unicodedata

import streamlit as st

from src.config import (
    APP_DESCRIPTION,
    APP_TITLE,
    DEFAULT_HISTORIQUE_PATH,
    DEFAULT_STOCKETABLISSEMENT_PATH,
    DEFAULT_STOCKUNITELEGALE_PATH,
    DEFAULT_SUCCESSION_PATH,
    build_default_output_path,
)
from src.export_utils import build_export_sheets, save_excel_file, to_excel_bytes
from src.io_utils import (
    get_input_file_extension,
    list_excel_sheets,
    read_user_input_file,
    resolve_output_excel_path,
    resolve_parquet_source,
)
from src.pipeline import ProcessResult, run_siret_control_pipeline
from src.sirene_queries import SireneSources
from src.siret_utils import build_siret_validation_frame, normalize_digits
from src.ui_helpers import (
    browse_save_excel_path,
    default_output_filename,
    render_progress_metrics,
    show_dataframe_preview,
    show_metrics,
    show_warnings,
    step_header,
)

def _normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _is_france_country(value: object) -> bool:
    normalized = _normalize_text(value)
    return normalized in {"fr", "fra", "france"}


def _schema_signature(columns: list[str]) -> str:
    payload = "\x1f".join(columns)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _column_tokens(name: object) -> set[str]:
    normalized = _normalize_text(name)
    return {token for token in re.split(r"[^a-z0-9]+", normalized) if token}


def _identifier_column_score(name: object) -> int:
    normalized = _normalize_text(name)
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    tokens = _column_tokens(name)
    score = 0

    if normalized == "siret":
        score += 1000
    if "siret" in tokens:
        score += 900
    elif "siret" in compact:
        score += 700

    if normalized == "siren":
        score += 850
    if "siren" in tokens:
        score += 700
    elif "siren" in compact:
        score += 500

    if {"id", "identifiant", "identifier"} & tokens:
        score += 60
    if {"societe", "entreprise", "company"} & tokens:
        score += 30
    return score


def _country_column_score(name: object) -> int:
    normalized = _normalize_text(name)
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    tokens = _column_tokens(name)
    score = 0

    if normalized in {"pays", "country"}:
        score += 1000
    if {"pays", "country"} & tokens:
        score += 850
    elif "country" in compact or "pays" in compact:
        score += 700

    if {"code", "iso", "nation", "nationalite"} & tokens:
        score += 50

    # Avoid common false positives such as postal code fields.
    if {"postal", "zipcode", "zip", "city", "ville", "commune"} & tokens:
        score -= 600
    return score


def _best_column_candidate(
    columns: list[str],
    score_fn,
    *,
    min_score: int = 1,
) -> str | None:
    best_col: str | None = None
    best_score = min_score - 1
    for col in columns:
        score = int(score_fn(col))
        if score > best_score:
            best_score = score
            best_col = col
    return best_col if best_score >= min_score else None


def _render_input_export_columns_selector(columns: list[str]) -> list[str]:
    """Render a compact selector for input columns exported in final report."""
    state_key = "input_export_columns_state"
    signature_key = "input_export_columns_signature"
    filter_key = "input_export_columns_filter"
    signature = _schema_signature(columns)

    if st.session_state.get(signature_key) != signature:
        st.session_state[signature_key] = signature
        st.session_state[state_key] = {col: True for col in columns}
        st.session_state[filter_key] = ""

    selection_map = st.session_state.get(state_key, {})
    selection_map = {col: bool(selection_map.get(col, True)) for col in columns}
    st.session_state[state_key] = selection_map

    selected: list[str] = [col for col in columns if selection_map.get(col, False)]
    with st.expander("Colonnes d'entree a exporter", expanded=False):
        st.caption("Cochez les colonnes d'entree a inclure dans le report final.")
        filter_text = st.text_input(
            "Recherche colonne",
            key=filter_key,
            placeholder="Filtrer par nom de colonne...",
        )

        action_cols = st.columns([1, 1, 6])
        if action_cols[0].button("Tout cocher", key=f"input_cols_select_all_{signature}"):
            for col in columns:
                selection_map[col] = True
            st.session_state[state_key] = selection_map
            st.rerun()
        if action_cols[1].button("Tout decocher", key=f"input_cols_clear_all_{signature}"):
            for col in columns:
                selection_map[col] = False
            st.session_state[state_key] = selection_map
            st.rerun()

        filtered_columns = [
            col for col in columns if not filter_text or filter_text.lower() in str(col).lower()
        ]
        if not filtered_columns:
            st.info("Aucune colonne ne correspond au filtre.")
        else:
            grid = st.columns(3)
            col_positions = {col_name: pos for pos, col_name in enumerate(columns)}
            for idx, col in enumerate(filtered_columns):
                widget_key = f"input_export_col_{signature}_{col_positions.get(col, idx)}"
                checked = grid[idx % 3].checkbox(
                    str(col),
                    value=selection_map.get(col, True),
                    key=widget_key,
                )
                selection_map[col] = checked

        st.session_state[state_key] = selection_map
        selected = [col for col in columns if selection_map.get(col, False)]
        st.caption(f"{len(selected)} / {len(columns)} colonnes d'entree selectionnees.")
    return selected


def _on_output_path_change() -> None:
    """Lock and persist output path once user edits the field."""
    output_text = str(st.session_state.get("output_path_widget", "") or "").strip()
    if not output_text:
        input_file_name = st.session_state.get("uploaded_input_filename")
        default_path = str(build_default_output_path(input_file_name))
        st.session_state["output_path_value"] = default_path
        st.session_state["output_path_widget_override"] = default_path
        st.session_state["output_path_locked"] = False
        return
    st.session_state["output_path_value"] = output_text
    st.session_state["output_path_locked"] = True


def _render_schema_report(result: ProcessResult) -> None:
    with st.expander("Diagnostic des schémas détectés", expanded=False):
        for table_name, details in result.schema_report.items():
            st.markdown(f"**{table_name}**")
            st.write(f"- Available columns count: {details.get('available_columns_count', 0)}")
            resolved = details.get("resolved_columns", {})
            if resolved:
                st.json(resolved)
            else:
                st.write("No resolved canonical columns.")


def _render_results(result: ProcessResult, excel_bytes: bytes) -> None:
    step_header(7, "Résultats")
    show_metrics(result.metrics)
    show_warnings(result.warnings)

    st.download_button(
        label="Télécharger le fichier Excel final",
        data=excel_bytes,
        file_name=str(st.session_state.get("latest_download_filename") or default_output_filename()),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    show_dataframe_preview(result.siret_overview, "Aperçu tableau unique siret_overview")

    _render_schema_report(result)


def main() -> None:
    st.set_page_config(page_title="Annuaire_SIRENE", layout="wide")
    st.title(APP_TITLE)
    st.caption(APP_DESCRIPTION)
    if "output_path_locked" not in st.session_state:
        st.session_state["output_path_locked"] = False
    default_output_path = str(build_default_output_path())
    if "output_path_initialized" not in st.session_state:
        st.session_state["output_path_value"] = default_output_path
        st.session_state["output_path_widget"] = default_output_path
        st.session_state["output_path_initialized"] = True
    elif not st.session_state.get("output_path_locked", False):
        st.session_state["output_path_value"] = default_output_path
        st.session_state["output_path_widget"] = default_output_path
    elif "output_path_value" not in st.session_state:
        st.session_state["output_path_value"] = default_output_path
    elif "output_path_widget" not in st.session_state:
        st.session_state["output_path_widget"] = st.session_state["output_path_value"]
    if "output_path_widget_override" in st.session_state:
        st.session_state["output_path_widget"] = st.session_state.pop("output_path_widget_override")

    step_header(1, "Charger le fichier utilisateur")
    uploaded_file = st.file_uploader(
        "Fichier contenant la liste d'identifiants SIRET/SIREN",
        type=["xlsx", "csv", "parquet"],
        accept_multiple_files=False,
    )
    st.session_state["uploaded_input_filename"] = (
        getattr(uploaded_file, "name", None) if uploaded_file is not None else None
    )
    if not st.session_state.get("output_path_locked", False):
        input_file_name = getattr(uploaded_file, "name", None) if uploaded_file is not None else None
        contextual_output_path = str(build_default_output_path(input_file_name))
        st.session_state["output_path_value"] = contextual_output_path
        st.session_state["output_path_widget"] = contextual_output_path

    input_df = None
    selected_sheet = None
    has_header = True
    if uploaded_file is not None:
        try:
            extension = get_input_file_extension(uploaded_file)
        except Exception as exc:
            st.error(f"Fichier non supporté: {exc}")
            return

        c_options_1, c_options_2 = st.columns(2)
        with c_options_1:
            has_header = st.checkbox(
                "Le fichier contient une ligne d'en-tête",
                value=True,
                help="Si décoché, les colonnes seront nommées column_1, column_2, etc.",
            )
        with c_options_2:
            st.checkbox(
                "Ignorer les lignes vides",
                value=True,
                disabled=True,
                help="Toujours activé: les lignes entièrement vides sont ignorées.",
            )

        if extension == ".xlsx":
            try:
                sheet_names = list_excel_sheets(uploaded_file)
            except Exception as exc:
                st.error(f"Impossible de lire les feuilles Excel: {exc}")
                return
            if not sheet_names:
                st.error("Le fichier Excel ne contient aucune feuille lisible.")
                return
            selected_sheet = st.selectbox(
                "Feuille à utiliser",
                options=sheet_names,
                index=0,
            )

        try:
            input_df = read_user_input_file(
                uploaded_file,
                sheet_name=selected_sheet,
                has_header=has_header,
                ignore_empty_rows=True,
            )
            show_dataframe_preview(input_df, "Aperçu fichier utilisateur")
        except Exception as exc:
            st.error(f"Impossible de lire le fichier utilisateur: {exc}")
            return

    if input_df is None:
        st.info("Chargez un fichier utilisateur pour continuer.")
        return

    step_header(2, "Colonnes d'entrée à exporter")
    selected_input_export_columns = _render_input_export_columns_selector(list(input_df.columns))

    step_header(3, "Sélection des colonnes de contrôle")
    available_columns = list(input_df.columns)
    default_siret_col = _best_column_candidate(available_columns, _identifier_column_score, min_score=500)
    default_country_col = _best_column_candidate(available_columns, _country_column_score, min_score=700)
    selector_col_1, selector_col_2 = st.columns(2)
    with selector_col_1:
        siret_column = st.selectbox(
            "Colonne contenant les identifiants (SIRET/SIREN)",
            options=available_columns,
            index=available_columns.index(default_siret_col) if default_siret_col in available_columns else None,
            placeholder="Sélectionner la colonne d'identifiants",
        )
    with selector_col_2:
        country_column_choice = st.selectbox(
            "Colonne Pays (optionnel - filtrer FR/FRA/France)",
            options=available_columns,
            index=available_columns.index(default_country_col) if default_country_col in available_columns else None,
            placeholder="Aucune colonne pays",
        )
    country_column = country_column_choice
    include_non_france_valid_siret = False
    if country_column is not None:
        include_non_france_valid_siret = st.checkbox(
            "Inclure aussi les hors France avec identifiant valide (SIRET/SIREN)",
            value=True,
        )

    step_header(4, "Renseigner les fichiers SIRENE Parquet")
    c1, c2 = st.columns(2)
    with c1:
        etab_path_text = st.text_input(
            "Chemin stocketablissement (obligatoire)",
            value=DEFAULT_STOCKETABLISSEMENT_PATH,
            placeholder=r"C:\path\to\StockEtablissement.parquet",
        )
        succession_path_text = st.text_input(
            "Chemin stocketablissementlienssuccession (optionnel)",
            value=DEFAULT_SUCCESSION_PATH,
            placeholder=r"C:\path\to\StockEtablissementLiensSuccession.parquet",
        )
    with c2:
        ul_path_text = st.text_input(
            "Chemin stockunitelegale (obligatoire)",
            value=DEFAULT_STOCKUNITELEGALE_PATH,
            placeholder=r"C:\path\to\StockUniteLegale.parquet",
        )
        historique_path_text = st.text_input(
            "Chemin stocketablissementhistorique (optionnel)",
            value=DEFAULT_HISTORIQUE_PATH,
            placeholder=r"C:\path\to\StockEtablissementHistorique.parquet",
        )

    step_header(5, "Sortie Excel")
    output_cols = st.columns([8, 2])
    with output_cols[0]:
        output_path_text = st.text_input(
            "Chemin fichier de sortie local",
            key="output_path_widget",
            on_change=_on_output_path_change,
            help="Le chemin est éditable. Vous pouvez aussi utiliser le bouton Browse.",
        )
        if str(output_path_text or "").strip():
            st.session_state["output_path_value"] = output_path_text
        else:
            fallback_path = str(
                build_default_output_path(st.session_state.get("uploaded_input_filename"))
            )
            st.session_state["output_path_value"] = fallback_path
            st.session_state["output_path_widget_override"] = fallback_path
            st.session_state["output_path_locked"] = False
    with output_cols[1]:
        st.markdown("<div style='height: 1.9rem;'></div>", unsafe_allow_html=True)
        if st.button("Browse...", width="stretch"):
            picked = browse_save_excel_path(st.session_state.get("output_path_value", ""))
            if picked:
                st.session_state["output_path_value"] = picked
                st.session_state["output_path_locked"] = True
                st.session_state["output_path_widget_override"] = picked
                st.rerun()
            st.info("Boîte de dialogue fermée sans sélection.")

    step_header(6, "Lancer le traitement")
    run_button = st.button("Exécuter le contrôle SIRET/SIREN", type="primary", width="stretch")

    if run_button:
        if not siret_column:
            st.error(
                "Sélectionnez la colonne d'identifiants (préselection auto par meilleur candidat SIRET/SIREN)."
            )
            return

        total_input_rows = int(len(input_df))
        france_input_count = total_input_rows
        non_france_input_count = 0
        unknown_country_input_count = 0
        non_france_valid_siret_included_count = 0
        country_filter_applied = country_column is not None
        base_df = input_df.copy()

        if country_filter_applied:
            country_values = base_df[country_column].fillna("").astype(str)
            country_values_normalized = country_values.map(_normalize_text)
            france_mask = country_values.map(_is_france_country)
            empty_country_mask = country_values_normalized.eq("") | country_values_normalized.str.fullmatch(
                r"0+"
            ).fillna(False)
            non_france_mask = ~(france_mask | empty_country_mask)
            france_input_count = int(france_mask.sum())
            unknown_country_input_count = int(empty_country_mask.sum())
            non_france_input_count = int(non_france_mask.sum())

            include_mask = france_mask & False
            if include_non_france_valid_siret and non_france_input_count > 0:
                non_france_validation = build_siret_validation_frame(
                    base_df.loc[non_france_mask, siret_column]
                )
                non_france_valid_mask = non_france_validation["siret_format_ok"].fillna(False).astype(bool)
                include_mask = non_france_mask.copy()
                include_mask.loc[non_france_mask] = non_france_valid_mask.values
                non_france_valid_siret_included_count = int(include_mask.sum())

            ignored_non_france_count = non_france_input_count - non_france_valid_siret_included_count
            if non_france_valid_siret_included_count > 0:
                st.info(
                    f"{non_france_valid_siret_included_count:,} ligne(s) hors France incluse(s) "
                    "car identifiant valide (SIRET/SIREN)."
                )
            if ignored_non_france_count > 0:
                st.info(
                    f"{ignored_non_france_count:,} ligne(s) hors France ignoree(s) "
                    f"(colonne pays: {country_column})."
                )
            if unknown_country_input_count > 0:
                st.info(
                    f"{unknown_country_input_count:,} ligne(s) conservee(s) "
                    "avec pays non precise."
                )

            base_df = base_df.loc[france_mask | empty_country_mask | include_mask].reset_index(
                drop=True
            )
            if base_df.empty:
                st.error("Aucune ligne France (FR/FRA/France) ou pays non precise a traiter.")
                return

        # Treat empty/zero-only identifier values as missing input rows.
        processing_df = base_df.copy()
        siret_values = processing_df[siret_column].fillna("").astype(str).str.strip()
        normalized_digits = siret_values.map(normalize_digits)
        zero_like_mask = normalized_digits.ne("") & normalized_digits.map(
            lambda value: set(value) == {"0"}
        )
        empty_like_mask = normalized_digits.eq("") | zero_like_mask
        ignored_empty_siret_rows = int(empty_like_mask.sum())
        missing_input_rows_df = processing_df.loc[empty_like_mask].copy().reset_index(drop=True)
        missing_export_columns = [
            col for col in selected_input_export_columns if col in missing_input_rows_df.columns
        ]
        if missing_export_columns:
            missing_input_rows_df = missing_input_rows_df[missing_export_columns].copy()
        else:
            missing_input_rows_df = missing_input_rows_df.iloc[:, 0:0].copy()
        if not missing_input_rows_df.empty:
            missing_input_rows_df.insert(0, "motif_exclusion_siret", "Identifiant vide ou egal a 0")
        processing_df = processing_df.loc[~empty_like_mask].reset_index(drop=True)

        if ignored_empty_siret_rows > 0:
            st.info(
                f"{ignored_empty_siret_rows:,} ligne(s) ignorée(s) car identifiant vide ou égal à 0."
            )
        if processing_df.empty:
            st.error("Aucune ligne exploitable après exclusion des identifiants vides/égaux à 0.")
            return

        progress_bar = st.progress(0, text="Initialisation...")
        progress_metrics_placeholder = st.empty()
        total_rows = len(processing_df)
        callback_state = {
            "last_emit": 0.0,
            "percent": 0,
            "processed": 0,
            "success": 0,
            "failed": 0,
        }

        def update_progress(
            percent: int,
            text: str,
            processed: int,
            success: int,
            failed: int,
            *,
            force: bool = False,
        ) -> None:
            now = monotonic()
            percent = max(percent, callback_state["percent"])
            processed = max(processed, callback_state["processed"])
            success = max(success, callback_state["success"])
            success = min(success, processed)
            # Keep displayed counters mathematically consistent at all times.
            # During intermediate stages, success can increase later for already
            # processed rows, so failures must be allowed to decrease accordingly.
            failed = max(0, processed - success)

            should_emit = force or (percent >= callback_state["percent"] + 1) or (
                now - callback_state["last_emit"]
            ) >= 2.0
            if not should_emit:
                return

            callback_state["last_emit"] = now
            callback_state["percent"] = percent
            callback_state["processed"] = processed
            callback_state["success"] = success
            callback_state["failed"] = failed
            progress_bar.progress(percent, text=text)
            with progress_metrics_placeholder.container():
                render_progress_metrics(
                    progress_percent=percent,
                    processed=processed,
                    total=total_rows,
                    success=success,
                    failed=failed,
                )

        try:
            update_progress(0, "Validation des chemins Parquet...", 0, 0, 0, force=True)
            sources = SireneSources(
                stocketablissement=resolve_parquet_source(
                    etab_path_text,
                    label="stocketablissement",
                    required=True,
                ),
                stockunitelegale=resolve_parquet_source(
                    ul_path_text,
                    label="stockunitelegale",
                    required=True,
                ),
                stocketablissementlienssuccession=resolve_parquet_source(
                    succession_path_text,
                    label="stocketablissementlienssuccession",
                    required=False,
                ),
                stocketablissementhistorique=resolve_parquet_source(
                    historique_path_text,
                    label="stocketablissementhistorique",
                    required=False,
                ),
            )
        except Exception as exc:
            update_progress(100, "Échec de validation des chemins.", 0, 0, total_rows, force=True)
            st.error(f"Erreur de paramétrage des chemins Parquet: {exc}")
            return

        try:
            output_path = resolve_output_excel_path(st.session_state.get("output_path_value", ""))
            if output_path is None:
                output_path = build_default_output_path(
                    st.session_state.get("uploaded_input_filename")
                )
                st.session_state["output_path_value"] = str(output_path)
                st.session_state["output_path_widget_override"] = str(output_path)
                st.session_state["output_path_locked"] = False

            update_progress(1, "Traitement des identifiants en cours...", 0, 0, 0, force=True)
            with st.spinner("Traitement en cours (DuckDB + enrichissement SIRENE)..."):
                result = run_siret_control_pipeline(
                    input_df=processing_df,
                    siret_column=siret_column,
                    sources=sources,
                    output_input_columns=selected_input_export_columns,
                    progress_callback=update_progress,
                )
                processed = int(result.metrics.get("total_input_siret", 0))
                success = int(result.metrics.get("found_in_sirene", 0))
                failed = int(result.metrics.get("invalid_format", 0)) + int(
                    result.metrics.get("not_found", 0)
                )
                update_progress(85, "Préparation du fichier Excel...", processed, success, failed, force=True)
                sheets = build_export_sheets(
                    siret_overview=result.siret_overview,
                    input_export_columns=selected_input_export_columns,
                    missing_input_siret_count=ignored_empty_siret_rows,
                    missing_input_rows=missing_input_rows_df,
                    country_filter_applied=country_filter_applied,
                    france_input_count=france_input_count,
                    non_france_input_count=non_france_input_count,
                    unknown_country_input_count=unknown_country_input_count,
                    non_france_valid_siret_included_count=non_france_valid_siret_included_count,
                    include_non_france_valid_siret_enabled=include_non_france_valid_siret,
                    total_input_rows=total_input_rows,
                )
                excel_bytes = to_excel_bytes(
                    sheets,
                    progress_callback=lambda p, t: update_progress(
                        p,
                        t,
                        processed,
                        success,
                        failed,
                    ),
                )
                update_progress(99, "Écriture du fichier sur disque...", processed, success, failed, force=True)

                saved_path = save_excel_file(sheets, output_path, payload=excel_bytes)
                st.session_state["latest_download_filename"] = (
                    saved_path.name if saved_path is not None else output_path.name
                )
                update_progress(100, "Terminé.", processed, success, failed, force=True)

            st.session_state["latest_result"] = result
            st.session_state["latest_excel_bytes"] = excel_bytes
            st.success("Traitement terminé.")
            if saved_path is not None:
                st.info(f"Fichier enregistré localement: {saved_path}")
        except Exception as exc:
            st.exception(exc)
            return

    latest_result = st.session_state.get("latest_result")
    latest_excel_bytes = st.session_state.get("latest_excel_bytes")
    if latest_result is not None and latest_excel_bytes is not None:
        _render_results(latest_result, latest_excel_bytes)


if __name__ == "__main__":
    main()


