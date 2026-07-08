"""Streamlit app — fuzzy name search on SIRENE parquet files.

Reads an anomalies sheet produced by the main app, lets the user map
the company-name and postal-code columns, then calls
SireneQueryService.search_candidates_by_text for every row and exports
the enriched result as an Excel file.
"""

from __future__ import annotations

from pathlib import Path
from time import monotonic

import pandas as pd
import streamlit as st

from src.config import (
    DEFAULT_STOCKETABLISSEMENT_PATH,
    DEFAULT_STOCKUNITELEGALE_PATH,
    DEFAULT_SUCCESSION_PATH,
)
from src.export_utils import ColSpec, save_excel_file, to_name_search_excel_bytes
from src.ui_helpers import render_progress_metrics
from src.io_utils import (
    get_input_file_extension,
    list_excel_sheets,
    read_user_input_file,
    resolve_parquet_source,
)
from src.sirene_queries import SireneQueryService, SireneSources

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_APP_TITLE = "Recherche de candidats SIRENE par nom"
_DEFAULT_CANDIDATES = 3

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title=_APP_TITLE, layout="wide")
st.title(_APP_TITLE)
st.caption(
    "Importe la feuille *anomalies* générée par l'app principale, "
    "mappe les colonnes nom/code postal, et obtiens les meilleurs candidats SIRENE."
)

# ===========================================================================
# Step 1 — Parquet sources
# ===========================================================================
st.subheader("1. Sources parquet SIRENE")

col_etab, col_ul = st.columns(2)
with col_etab:
    etab_path_text = st.text_input(
        "Chemin StockEtablissement (.parquet ou dossier)",
        value=DEFAULT_STOCKETABLISSEMENT_PATH,
    )
with col_ul:
    ul_path_text = st.text_input(
        "Chemin StockUniteLegale (.parquet ou dossier)",
        value=DEFAULT_STOCKUNITELEGALE_PATH,
    )

succession_path_text = st.text_input(
    "Chemin StockEtablissementLiensSuccession (.parquet ou dossier) — optionnel",
    value=DEFAULT_SUCCESSION_PATH,
    help="Si renseigné, permet de résoudre les déménagements en remontant le successeur direct d'un établissement fermé.",
)

# ===========================================================================
# Step 2 — Upload anomalies file
# ===========================================================================
st.subheader("2. Fichier anomalies")

uploaded_file = st.file_uploader(
    "Importer la feuille anomalies (Excel, CSV ou Parquet)",
    type=["xlsx", "csv", "parquet"],
    accept_multiple_files=False,
)

if uploaded_file is None:
    st.info("Importe un fichier pour continuer.")
    st.stop()

# Sheet selector (Excel only)
selected_sheet: str | None = None
extension = get_input_file_extension(uploaded_file)
if extension == ".xlsx":
    sheet_names = list_excel_sheets(uploaded_file)
    # Pre-select the "anomalies" sheet if present
    default_sheet_idx = next(
        (i for i, s in enumerate(sheet_names) if s.lower() == "anomalies"),
        0,
    )
    selected_sheet = st.selectbox(
        "Feuille à utiliser",
        options=sheet_names,
        index=default_sheet_idx,
    )

try:
    input_df = read_user_input_file(
        uploaded_file,
        sheet_name=selected_sheet,
        has_header=True,
        ignore_empty_rows=True,
    )
except ValueError as exc:
    st.error(f"Impossible de lire le fichier : {exc}")
    st.stop()

st.caption(f"{len(input_df):,} lignes · {len(input_df.columns)} colonnes")

# ===========================================================================
# Step 3 — Column mapping
# ===========================================================================
st.subheader("3. Mapping des colonnes")

available_columns = list(input_df.columns)

# Heuristic: pick the column whose name contains "nom" or "entreprise"
def _score_name_col(col: str) -> int:
    lower = col.lower()
    score = 0
    if "nom" in lower:
        score += 500
    if "entreprise" in lower or "societe" in lower or "raison" in lower:
        score += 400
    if "denomination" in lower:
        score += 300
    return score

def _score_zip_col(col: str) -> int:
    lower = col.lower()
    score = 0
    if "postal" in lower or "cp" == lower or "zip" in lower:
        score += 600
    if "code" in lower:
        score += 200
    return score

def _score_pays_col(col: str) -> int:
    lower = col.lower()
    if "pays" in lower or "country" in lower:
        return 500
    return 0

def _score_ville_col(col: str) -> int:
    lower = col.lower()
    if "ville" in lower or "city" in lower or "commune" in lower:
        return 500
    if "libelle" in lower:
        return 200
    return 0

def _score_adr_col(col: str) -> int:
    lower = col.lower()
    if "adresse" in lower or "address" in lower or lower == "adr":
        return 500
    if "voie" in lower or "rue" in lower:
        return 300
    return 0

def _best_candidate(columns: list[str], score_fn) -> str | None:
    scored = [(score_fn(c), c) for c in columns]
    best_score, best_col = max(scored, key=lambda x: x[0])
    return best_col if best_score > 0 else None

default_name_col = _best_candidate(available_columns, _score_name_col)
default_zip_col = _best_candidate(available_columns, _score_zip_col)

map_col1, map_col2 = st.columns(2)
with map_col1:
    name_column = st.selectbox(
        "Colonne Nom entreprise",
        options=available_columns,
        index=available_columns.index(default_name_col)
        if default_name_col in available_columns
        else 0,
    )
with map_col2:
    zip_options = ["(aucune)"] + available_columns
    zip_default_idx = (
        zip_options.index(default_zip_col)
        if default_zip_col in zip_options
        else 0
    )
    zip_column_choice = st.selectbox(
        "Colonne Code Postal (optionnel)",
        options=zip_options,
        index=zip_default_idx,
    )
    zip_column: str | None = zip_column_choice if zip_column_choice != "(aucune)" else None

default_pays_col = _best_candidate(available_columns, _score_pays_col)
default_ville_col = _best_candidate(available_columns, _score_ville_col)
default_adr_col = _best_candidate(available_columns, _score_adr_col)

map_col3, map_col4, map_col5 = st.columns(3)
with map_col3:
    pays_options = ["(aucune)"] + available_columns
    pays_default_idx = (
        pays_options.index(default_pays_col)
        if default_pays_col in pays_options
        else 0
    )
    pays_column_choice = st.selectbox(
        "Colonne Pays (optionnel)",
        options=pays_options,
        index=pays_default_idx,
    )
    pays_column: str | None = pays_column_choice if pays_column_choice != "(aucune)" else None
with map_col4:
    ville_options = ["(aucune)"] + available_columns
    ville_default_idx = (
        ville_options.index(default_ville_col)
        if default_ville_col in ville_options
        else 0
    )
    ville_column_choice = st.selectbox(
        "Colonne Ville (optionnel)",
        options=ville_options,
        index=ville_default_idx,
    )
    ville_column: str | None = ville_column_choice if ville_column_choice != "(aucune)" else None
with map_col5:
    adr_options = ["(aucune)"] + available_columns
    adr_default_idx = (
        adr_options.index(default_adr_col)
        if default_adr_col in adr_options
        else 0
    )
    adr_column_choice = st.selectbox(
        "Colonne Adresse (optionnel)",
        options=adr_options,
        index=adr_default_idx,
    )
    adr_column: str | None = adr_column_choice if adr_column_choice != "(aucune)" else None

# ===========================================================================
# Step 4 — Search options
# ===========================================================================
st.subheader("4. Options de recherche")

limit = st.number_input(
    "Nombre de candidats par ligne",
    min_value=1,
    max_value=10,
    value=_DEFAULT_CANDIDATES,
    step=1,
)

# ===========================================================================
# Step 5 — Output path
# ===========================================================================
st.subheader("5. Fichier de sortie")

output_path_text = st.text_input(
    "Chemin du fichier Excel de sortie (.xlsx)",
    value="resultats_recherche_noms.xlsx",
)

# ===========================================================================
# Step 6 — Run
# ===========================================================================
st.subheader("6. Lancement")

if st.button("Lancer la recherche", type="primary"):
    # Clear any previous results so a new run always starts fresh.
    st.session_state.pop("search_results", None)

    # --- Validate sources ---------------------------------------------------
    try:
        sources = SireneSources(
            stocketablissement=resolve_parquet_source(
                etab_path_text, label="stocketablissement", required=True
            ),
            stockunitelegale=resolve_parquet_source(
                ul_path_text, label="stockunitelegale", required=True
            ),
            stocketablissementlienssuccession=resolve_parquet_source(
                succession_path_text, label="stocketablissementlienssuccession", required=False
            ),
        )
    except ValueError as exc:
        st.error(f"Erreur de chemin parquet : {exc}")
        st.stop()

    # --- Validate output path -----------------------------------------------
    output_path_raw = output_path_text.strip()
    if not output_path_raw:
        st.error("Veuillez renseigner un chemin de sortie.")
        st.stop()
    output_path = Path(output_path_raw)
    if output_path.suffix.lower() != ".xlsx":
        output_path = output_path.with_suffix(".xlsx")

    # --- Progress UI --------------------------------------------------------
    total_rows = len(input_df)
    progress_bar = st.progress(0, text="Initialisation...")
    progress_placeholder = st.empty()

    callback_state: dict[str, object] = {
        "last_emit": 0.0,
        "percent": 0,
        "start_time": monotonic(),
    }

    def _update_progress(
        percent: int,
        processed: int,
        *,
        force: bool = False,
        success: int = 0,
        failed: int = 0,
        candidates: int = 0,
    ) -> None:
        now = monotonic()
        should_emit = (
            force
            or percent >= (callback_state["percent"] or 0) + 1  # type: ignore[operator]
            or (now - callback_state["last_emit"]) >= 2.0  # type: ignore[operator]
        )
        if not should_emit:
            return
        callback_state["last_emit"] = now
        callback_state["percent"] = percent

        elapsed = now - callback_state["start_time"]  # type: ignore[operator]
        eta_str = ""
        if processed > 0 and processed < total_rows and elapsed > 1:
            rate = processed / elapsed
            remaining = int((total_rows - processed) / rate)
            if remaining < 60:
                eta_str = f" · ETA ~{remaining}s"
            else:
                eta_str = f" · ETA ~{remaining // 60}m{remaining % 60:02d}s"

        progress_bar.progress(
            min(percent, 100),
            text=f"Traitement {processed}/{total_rows}{eta_str}…",
        )
        with progress_placeholder.container():
            render_progress_metrics(
                progress_percent=percent,
                processed=processed,
                total=total_rows,
                success=success,
                failed=failed,
                candidates_found=candidates,
                elapsed_seconds=float(elapsed),
            )

    # --- Column specs for structured Excel output ---------------------------
    mapped_cols: set[str] = {
        c for c in [name_column, pays_column, zip_column, ville_column, adr_column] if c
    }
    passthrough_cols = [c for c in input_df.columns if c not in mapped_cols]

    col_specs: list[ColSpec] = []
    for _col in passthrough_cols:
        col_specs.append(ColSpec(key=_col, header=_col, category="INPUT"))
    col_specs += [
        ColSpec(key="__nom__", header="NOM", category="INPUT"),
        ColSpec(key="__pappers_nom__", header="Pappers", category="INPUT", is_pappers=True),
    ]
    if pays_column:
        col_specs.append(ColSpec(key="__pays__", header="PAYS", category="INPUT"))
    if zip_column:
        col_specs.append(ColSpec(key="__zip__", header="ZIP", category="INPUT"))
    if ville_column:
        col_specs.append(ColSpec(key="__ville__", header="VILLE", category="INPUT"))
    if adr_column:
        col_specs.append(ColSpec(key="__adr__", header="ADR", category="INPUT"))
    col_specs.append(ColSpec(key="__priorite__", header="Priorité", category="INPUT"))
    for _alice_key, _alice_hdr in [
        ("__alice_choix__", "Choix"),
        ("__alice_pays__", "PAYS"),
        ("__alice_siret__", "SIRET"),
        ("__alice_type__", "Type"),
        ("__alice_commentaire__", "Commentaire"),
    ]:
        col_specs.append(ColSpec(key=_alice_key, header=_alice_hdr, category="ALICE"))
    for _rank in range(1, int(limit) + 1):
        _cat = f"Candidat {_rank}"
        col_specs += [
            ColSpec(key=f"__siret_{_rank}__", header=f"suggested_siret_{_rank}", category=_cat),
            ColSpec(key=f"__pappers_{_rank}__", header="Pappers", category=_cat, is_pappers=True),
            ColSpec(key=f"__denomination_{_rank}__", header=f"suggested_denomination_{_rank}", category=_cat),
            ColSpec(key=f"__adresse_{_rank}__", header=f"suggested_adresse_{_rank}", category=_cat),
            ColSpec(key=f"__score_{_rank}__", header=f"score_{_rank}", category=_cat),
        ]

    # --- Search loop --------------------------------------------------------
    result_rows: list[dict] = []
    structured_rows: list[dict] = []
    n_success = 0
    n_failed = 0
    n_candidates = 0

    try:
        with SireneQueryService(sources) as service:
            for idx, row in input_df.iterrows():
                name_token = str(row.get(name_column, "") or "").strip()
                zip_code: str | None = None
                if zip_column:
                    raw_zip = str(row.get(zip_column, "") or "").strip()
                    zip_code = raw_zip if raw_zip else None

                candidates: pd.DataFrame = pd.DataFrame()
                if len(name_token) >= 3:
                    try:
                        candidates = service.search_candidates_by_text(
                            name_token=name_token,
                            zip_code=zip_code,
                            limit=int(limit),
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.warning(f"Ligne {idx} — erreur recherche : {exc}")

                n_found = len(candidates)
                if n_found > 0:
                    n_success += 1
                else:
                    n_failed += 1
                n_candidates += n_found

                # Display row (legacy format for st.dataframe preview)
                display_out: dict = row.to_dict()
                for rank in range(1, int(limit) + 1):
                    if not candidates.empty and rank <= len(candidates):
                        cand = candidates.iloc[rank - 1]
                        display_out[f"suggested_siret_{rank}"] = cand.get("siret", "")
                        display_out[f"suggested_denomination_{rank}"] = cand.get("denomination", "")
                        display_out[f"suggested_adresse_{rank}"] = cand.get("adresse", "")
                        display_out[f"score_{rank}"] = round(float(cand.get("score_similarite", 0)), 4)
                    else:
                        display_out[f"suggested_siret_{rank}"] = ""
                        display_out[f"suggested_denomination_{rank}"] = ""
                        display_out[f"suggested_adresse_{rank}"] = ""
                        display_out[f"score_{rank}"] = ""
                result_rows.append(display_out)

                # Structured row for formatted Excel
                nom_val = str(row.get(name_column, "") or "").strip()
                pays_val = str(row.get(pays_column, "") or "").strip() if pays_column else ""
                zip_val = str(row.get(zip_column, "") or "").strip() if zip_column else ""
                ville_val = str(row.get(ville_column, "") or "").strip() if ville_column else ""
                adr_val = str(row.get(adr_column, "") or "").strip() if adr_column else ""

                struct: dict = {}
                for _col in passthrough_cols:
                    struct[_col] = str(row.get(_col, "") or "")
                struct.update({
                    "__nom__": nom_val,
                    "__pappers_nom__": nom_val,
                    "__pays__": pays_val,
                    "__zip__": zip_val,
                    "__ville__": ville_val,
                    "__adr__": adr_val,
                    "__alice_choix__": "",
                    "__alice_pays__": "",
                    "__alice_siret__": "",
                    "__alice_type__": "",
                    "__alice_commentaire__": "",
                })

                siret1 = ""
                for rank in range(1, int(limit) + 1):
                    if not candidates.empty and rank <= len(candidates):
                        cand = candidates.iloc[rank - 1]
                        siret_v = str(cand.get("siret", "") or "")
                        denom_v = str(cand.get("denomination", "") or "")
                        adresse_v = str(cand.get("adresse", "") or "")
                        score_v: object = round(float(cand.get("score_similarite", 0)), 4)
                    else:
                        siret_v = denom_v = adresse_v = ""
                        score_v = ""
                    struct[f"__siret_{rank}__"] = siret_v
                    struct[f"__pappers_{rank}__"] = siret_v
                    struct[f"__denomination_{rank}__"] = denom_v
                    struct[f"__adresse_{rank}__"] = adresse_v
                    struct[f"__score_{rank}__"] = score_v
                    if rank == 1:
                        siret1 = siret_v

                pays_upper = pays_val.upper()
                if pays_upper in ("FRA", "FR", "FRANCE") and siret1:
                    struct["__priorite__"] = 1
                elif pays_upper in ("FRA", "FR", "FRANCE"):
                    struct["__priorite__"] = 2
                else:
                    struct["__priorite__"] = 3
                structured_rows.append(struct)

                percent = round(len(result_rows) / total_rows * 95)
                _update_progress(
                    percent, len(result_rows),
                    success=n_success, failed=n_failed, candidates=n_candidates,
                )

    except Exception as exc:
        st.error(f"Erreur lors de la recherche : {exc}")
        st.stop()

    _update_progress(
        95, total_rows, force=True,
        success=n_success, failed=n_failed, candidates=n_candidates,
    )

    # --- Serialize ----------------------------------------------------------
    result_df = pd.DataFrame(result_rows).astype(str).replace("nan", "")
    progress_bar.progress(96, text="Sérialisation Excel…")
    excel_bytes = to_name_search_excel_bytes(structured_rows, col_specs)

    # --- Save to disk -------------------------------------------------------
    progress_bar.progress(99, text="Écriture sur disque…")
    saved_path: Path | None = None
    try:
        saved_path = save_excel_file({}, output_path, payload=excel_bytes)
    except Exception as exc:
        st.error(f"Impossible d'écrire le fichier : {exc}")

    progress_bar.progress(100, text="Terminé.")
    progress_placeholder.empty()

    # --- Persist results in session state so reruns don't lose them ---------
    st.session_state["search_results"] = {
        "result_df": result_df,
        "excel_bytes": excel_bytes,
        "saved_path": saved_path,
        "output_filename": output_path.name,
        "n_success": n_success,
        "n_failed": n_failed,
        "n_candidates": n_candidates,
    }

# ===========================================================================
# Step 7 — Results (rendered from session state — survives download reruns)
# ===========================================================================
if "search_results" in st.session_state:
    r = st.session_state["search_results"]
    result_df: pd.DataFrame = r["result_df"]
    excel_bytes: bytes = r["excel_bytes"]
    saved_path: Path | None = r["saved_path"]
    output_filename: str = r["output_filename"]

    st.subheader("7. Résultats")

    _s = r.get("n_success", 0)
    _f = r.get("n_failed", 0)
    _c = r.get("n_candidates", 0)
    _total = len(result_df)
    _mc1, _mc2, _mc3, _mc4 = st.columns(4)
    _mc1.metric("Lignes traitées", f"{_total:,}")
    _mc2.metric("Avec candidats", _s, delta=f"{_s/_total*100:.0f} %" if _total else None, delta_color="off")
    _mc3.metric("Sans résultat",  _f, delta=f"{_f/_total*100:.0f} %" if _total else None, delta_color="inverse")
    _mc4.metric("Candidats trouvés", _c, delta=f"moy. {_c/_s:.1f}" if _s else None, delta_color="off")

    st.download_button(
        label="Télécharger le fichier Excel",
        data=excel_bytes,
        file_name=output_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    if saved_path:
        st.success(f"Fichier sauvegardé : {saved_path}")

    st.dataframe(result_df.head(20), use_container_width=True)
