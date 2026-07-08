"""Business pipeline for SIRET/SIREN controls and SIRENE enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from .config import (
    ADDRESS_COMPONENT_FIELDS,
    DENOMINATION_COALESCE_FIELDS,
    ETABLISSEMENT_CANONICAL_FIELDS,
    HISTORIQUE_PRIORITY_FIELDS,
    PERSON_NAME_FIELDS,
    SIRET_STATUS_ACTIVE,
    SIRET_STATUS_CLOSED,
    SIRET_STATUS_FOUND_UNKNOWN,
    SIRET_STATUS_INVALID,
    SIRET_STATUS_NOT_FOUND,
    SIRET_STATUS_RADIATED,
    UNITE_LEGALE_CANONICAL_FIELDS,
)
from .sirene_queries import SireneQueryService, SireneSources
from .siret_utils import (
    build_address,
    build_siret_validation_frame,
    classify_etablissement_status,
    first_non_empty,
    normalize_digits,
)


@dataclass
class ProcessResult:
    """Container for all pipeline outputs."""

    controle_siret: pd.DataFrame
    siret_overview: pd.DataFrame
    all_etablissements: pd.DataFrame
    move_candidates: pd.DataFrame
    succession_links: pd.DataFrame | None
    historique: pd.DataFrame | None
    params_logs: pd.DataFrame
    metrics: dict[str, int]
    warnings: list[str]
    schema_report: dict[str, dict[str, Any]]


ProgressCallback = Callable[[int, str, int, int, int], None]


def _normalize_identifier(value: Any, expected_len: int) -> str:
    digits = normalize_digits(value)
    if not digits:
        return ""
    if len(digits) < expected_len:
        return digits.zfill(expected_len)
    return digits


def _normalize_id_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "siret" in out.columns:
        out["siret"] = out["siret"].map(lambda x: _normalize_identifier(x, 14))
    if "siren" in out.columns:
        out["siren"] = out["siren"].map(lambda x: _normalize_identifier(x, 9))
    if "nic" in out.columns:
        out["nic"] = out["nic"].map(lambda x: _normalize_identifier(x, 5))
    return out


def _build_denomination_entreprise(row: pd.Series) -> str:
    primary = first_non_empty([row.get(col, "") for col in DENOMINATION_COALESCE_FIELDS])
    if primary:
        return primary
    person_name = first_non_empty(
        [
            " ".join(
                part
                for part in [
                    str(row.get("prenom1UniteLegale", "") or "").strip(),
                    str(row.get("prenom2UniteLegale", "") or "").strip(),
                    str(row.get("prenom3UniteLegale", "") or "").strip(),
                    str(row.get("nomUsageUniteLegale", "") or "").strip(),
                    str(row.get("nomUniteLegale", "") or "").strip(),
                ]
                if part and part.lower() != "nan"
            ),
            " ".join(
                str(row.get(field, "") or "").strip()
                for field in PERSON_NAME_FIELDS
                if str(row.get(field, "") or "").strip()
            ),
        ]
    )
    return person_name


def _compute_aggregates(all_etablissements: pd.DataFrame) -> pd.DataFrame:
    if all_etablissements.empty or "siren" not in all_etablissements.columns:
        return pd.DataFrame(
            columns=[
                "siren",
                "total_etablissements",
                "total_etablissements_actifs",
                "total_etablissements_fermes",
            ]
        )

    work = all_etablissements.copy()
    status = work.get("etatAdministratifEtablissement", "").fillna("").astype(str).str.upper()
    work["is_active"] = status.eq("A")
    work["is_closed"] = status.eq("F")
    grouped = (
        work.groupby("siren", dropna=False)
        .agg(
            total_etablissements=("siren", "size"),
            total_etablissements_actifs=("is_active", "sum"),
            total_etablissements_fermes=("is_closed", "sum"),
        )
        .reset_index()
    )
    return grouped


def _build_historique_summary(
    historique_df: pd.DataFrame,
) -> tuple[pd.DataFrame, str | None]:
    if historique_df.empty:
        return pd.DataFrame(), None

    if "siret" in historique_df.columns and historique_df["siret"].notna().any():
        key = "siret"
    elif "siren" in historique_df.columns and historique_df["siren"].notna().any():
        key = "siren"
    else:
        return pd.DataFrame(), None

    work = historique_df.copy()
    for date_col in ["dateDebut", "dateFin"]:
        if date_col in work.columns:
            work[date_col] = work[date_col].astype(str)

    grouped = work.groupby(key, dropna=False).agg(
        historique_records_count=(key, "size"),
        historique_latest_dateDebut=("dateDebut", "max") if "dateDebut" in work.columns else (key, "size"),
        historique_latest_dateFin=("dateFin", "max") if "dateFin" in work.columns else (key, "size"),
    )
    grouped = grouped.reset_index()
    if "historique_latest_dateDebut" in grouped.columns:
        grouped["historique_latest_dateDebut"] = grouped["historique_latest_dateDebut"].replace(
            {"nan": ""}
        )
    if "historique_latest_dateFin" in grouped.columns:
        grouped["historique_latest_dateFin"] = grouped["historique_latest_dateFin"].replace(
            {"nan": ""}
        )
    return grouped, key


def _ensure_int_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype("int64")
    return out


def _is_truthy_flag(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "t", "yes", "y", "oui", "o"}


def _select_establishments_for_siren_inputs(
    establishments: pd.DataFrame,
) -> pd.DataFrame:
    """
    Select one establishment per SIREN input using deterministic ranking.

    Ranking:
    1) siège if available
    2) otherwise active establishment
    3) tie-break by dateDebut desc, dateCreationEtablissement desc, siret asc
    """
    if establishments.empty or "siren" not in establishments.columns or "siret" not in establishments.columns:
        return pd.DataFrame()

    work = establishments.copy()
    work["siren"] = work["siren"].fillna("").astype(str).str.strip()
    work["siret"] = work["siret"].fillna("").astype(str).str.strip()
    work = work[work["siren"].ne("") & work["siret"].ne("")]
    if work.empty:
        return pd.DataFrame()

    siege_series = (
        work["etablissementSiege"]
        if "etablissementSiege" in work.columns
        else pd.Series("", index=work.index)
    )
    etat_series = (
        work["etatAdministratifEtablissement"]
        if "etatAdministratifEtablissement" in work.columns
        else pd.Series("", index=work.index)
    )
    date_debut_series = (
        work["dateDebut"] if "dateDebut" in work.columns else pd.Series("", index=work.index)
    )
    date_creation_series = (
        work["dateCreationEtablissement"]
        if "dateCreationEtablissement" in work.columns
        else pd.Series("", index=work.index)
    )
    work["_is_siege"] = siege_series.map(_is_truthy_flag)
    work["_is_active"] = etat_series.fillna("").astype(str).str.upper().eq("A")
    work["_date_debut_dt"] = pd.to_datetime(date_debut_series, errors="coerce")
    work["_date_creation_dt"] = pd.to_datetime(date_creation_series, errors="coerce")

    selected_rows: list[pd.Series] = []
    for _, group in work.groupby("siren", dropna=False):
        candidates = group[group["_is_siege"]]
        lookup_mode = "SIREN_SIEGE"
        if candidates.empty:
            candidates = group[group["_is_active"]]
            lookup_mode = "SIREN_ACTIVE_FALLBACK"
        if candidates.empty:
            continue
        ranked = candidates.sort_values(
            by=["_date_debut_dt", "_date_creation_dt", "siret"],
            ascending=[False, False, True],
            kind="mergesort",
        )
        selected = ranked.iloc[0].copy()
        selected["_tmp_siren_lookup_mode"] = lookup_mode
        selected_rows.append(selected)

    if not selected_rows:
        return pd.DataFrame()

    selected_df = pd.DataFrame(selected_rows)
    return selected_df.drop(
        columns=["_is_siege", "_is_active", "_date_debut_dt", "_date_creation_dt"],
        errors="ignore",
    )


def _build_active_sibling_candidates_by_siren(
    all_etablissements: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    """Build active sibling candidates per SIREN with ranking metadata."""
    if all_etablissements.empty:
        return {}
    required_cols = {"siren", "siret", "etatAdministratifEtablissement"}
    if not required_cols.issubset(set(all_etablissements.columns)):
        return {}

    work = all_etablissements.copy()
    work = work[work["etatAdministratifEtablissement"].fillna("").astype(str).str.upper().eq("A")]
    work["siren"] = work.get("siren", "").fillna("").astype(str).str.strip()
    work["siret"] = work.get("siret", "").fillna("").astype(str).str.strip()
    work = work[work["siren"].ne("") & work["siret"].ne("")]
    if work.empty:
        return {}

    siege_series = (
        work["etablissementSiege"]
        if "etablissementSiege" in work.columns
        else pd.Series("", index=work.index)
    )
    date_debut_series = (
        work["dateDebut"] if "dateDebut" in work.columns else pd.Series("", index=work.index)
    )
    date_creation_series = (
        work["dateCreationEtablissement"]
        if "dateCreationEtablissement" in work.columns
        else pd.Series("", index=work.index)
    )
    work["_is_siege"] = siege_series.map(_is_truthy_flag)
    work["_date_debut_dt"] = pd.to_datetime(date_debut_series, errors="coerce")
    work["_date_creation_dt"] = pd.to_datetime(date_creation_series, errors="coerce")
    work = work.sort_values(
        by=["siren", "_is_siege", "_date_debut_dt", "_date_creation_dt", "siret"],
        ascending=[True, False, False, False, True],
        kind="mergesort",
    )
    work = work.drop_duplicates(subset=["siren", "siret"], keep="first")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for siren, group in work.groupby("siren", dropna=False):
        grouped[str(siren)] = [
            {
                "siret": str(row.get("siret", "") or "").strip(),
                "is_siege": bool(row.get("_is_siege", False)),
                "date_debut": str(row.get("dateDebut", "") or "").strip(),
                "date_creation": str(row.get("dateCreationEtablissement", "") or "").strip(),
            }
            for _, row in group.iterrows()
        ]
    return grouped


def _choose_active_sibling_candidate(
    *,
    siren: str,
    current_siret: str,
    candidates_by_siren: dict[str, list[dict[str, Any]]],
) -> tuple[str, int, str]:
    """Choose a sibling candidate and explain the choice."""
    candidates = candidates_by_siren.get(siren, [])
    if not candidates:
        return "", 0, ""

    filtered = [candidate for candidate in candidates if candidate.get("siret") != current_siret]
    if not filtered:
        filtered = candidates
    if not filtered:
        return "", 0, ""

    chosen = filtered[0]
    count = len(filtered)
    if count == 1:
        reason = "Candidat unique actif sur le meme SIREN."
    elif bool(chosen.get("is_siege")):
        reason = "Choisi car il s'agit du siege parmi plusieurs etablissements actifs."
    elif str(chosen.get("date_debut", "")).strip():
        reason = "Choisi pour sa dateDebut la plus recente parmi plusieurs candidats actifs."
    elif str(chosen.get("date_creation", "")).strip():
        reason = (
            "Choisi pour sa dateCreationEtablissement la plus recente parmi plusieurs candidats actifs."
        )
    else:
        reason = "Choisi par tri deterministe du SIRET parmi plusieurs candidats actifs."
    return str(chosen.get("siret", "") or "").strip(), count, reason


def _classify_cleaning_action(row: pd.Series) -> str:
    """Return a single business action label for third-party cleanup."""
    status = str(row.get("siret_status", "") or "")
    replacement = str(row.get("siret_remplacement_recommande", "") or "").strip()
    if status == SIRET_STATUS_INVALID:
        return "Invalide"
    if status == SIRET_STATUS_NOT_FOUND:
        return "Non trouvé"
    if status == SIRET_STATUS_ACTIVE:
        return "Conserver"
    if status == SIRET_STATUS_CLOSED:
        if replacement:
            return "Remplacer"
        return "A clôturer"
    if status == SIRET_STATUS_RADIATED:
        return "Radiée"
    return "A analyser"


def _to_yes_no(flag: Any) -> str:
    """Convert boolean-like value to Oui/Non."""
    return "Oui" if bool(flag) else "Non"


def _build_nd_detection_mask(overview: pd.DataFrame) -> pd.Series:
    """
    Detect [ND] marker (including spaced variants like [ ND ]) in key business fields.

    This marker is commonly used when data is intentionally hidden.
    """
    if overview.empty:
        return pd.Series(dtype=bool, index=overview.index)

    candidate_columns = list(
        dict.fromkeys(
            [
                "denomination_entreprise",
                "adresse_reconstituee",
                "enseigne1Etablissement",
                "denominationUsuelleEtablissement",
                "denominationUniteLegale",
                "denominationUsuelle1UniteLegale",
                "denominationUsuelle2UniteLegale",
                "denominationUsuelle3UniteLegale",
                "sigleUniteLegale",
                "nomUniteLegale",
                "nomUsageUniteLegale",
                "prenom1UniteLegale",
                "prenom2UniteLegale",
                "prenom3UniteLegale",
                "complementAdresseEtablissement",
                "numeroVoieEtablissement",
                "indiceRepetitionEtablissement",
                "typeVoieEtablissement",
                "libelleVoieEtablissement",
                "codePostalEtablissement",
                "libelleCommuneEtablissement",
                "libelleCommuneEtrangerEtablissement",
                "distributionSpecialeEtablissement",
                "libelleCedexEtablissement",
            ]
            + ETABLISSEMENT_CANONICAL_FIELDS
            + UNITE_LEGALE_CANONICAL_FIELDS
        )
    )
    available = [col for col in candidate_columns if col in overview.columns]
    if not available:
        return pd.Series(False, index=overview.index, dtype=bool)

    nd_mask = pd.Series(False, index=overview.index, dtype=bool)
    pattern = r"\[\s*ND\s*\]"
    for col in available:
        col_mask = overview[col].fillna("").astype(str).str.contains(pattern, case=False, regex=True)
        nd_mask = nd_mask | col_mask
    return nd_mask


def _status_label_fr(status_internal: str) -> str:
    """Map internal status to French display label."""
    mapping = {
        SIRET_STATUS_ACTIVE: "Actif",
        SIRET_STATUS_CLOSED: "Fermé",
        SIRET_STATUS_RADIATED: "Radiée",
        SIRET_STATUS_FOUND_UNKNOWN: "Radiée",
        SIRET_STATUS_INVALID: "Invalide",
        SIRET_STATUS_NOT_FOUND: "Non trouvé",
    }
    return mapping.get(status_internal, "Radiée")


def _priority_label_fr(priority_internal: str) -> str:
    """Map internal analysis priority to French label."""
    return {"HIGH": "Haute", "MEDIUM": "Moyenne", "LOW": "Basse"}.get(
        str(priority_internal or "").upper(),
        "Basse",
    )


def _build_siret_overview(
    controle_siret: pd.DataFrame,
    input_columns: list[str],
    siret_source_column: str,
    all_etablissements: pd.DataFrame,
    succession_links: pd.DataFrame | None,
) -> pd.DataFrame:
    """Build a single output table optimized for third-party data cleanup."""
    overview = controle_siret.copy()
    overview = overview.rename(
        columns={
            "siret_input": "siret_entree",
            "siret_normalized": "siret_normalise",
        }
    )
    overview["identifiant_recherche"] = (
        overview.get("siret_lookup_key", pd.Series("", index=overview.index, dtype=str))
        .fillna("")
        .astype(str)
        .str.strip()
    )
    format_series = overview.get("siret_format_ok", False)
    if isinstance(format_series, pd.Series):
        overview["siret_format_valide"] = format_series.fillna(False).astype(bool)
    else:
        overview["siret_format_valide"] = pd.Series(
            bool(format_series),
            index=overview.index,
            dtype=bool,
        )
    if "siret_doublon_entree" not in overview.columns:
        overview["siret_doublon_entree"] = False
    if "siren_doublon_entree" not in overview.columns:
        overview["siren_doublon_entree"] = False
    overview = overview.drop(
        columns=[siret_source_column, "siret_len_ok", "siret_luhn_ok", "siret_format_ok"],
        errors="ignore",
    )

    active_sibling_candidates = _build_active_sibling_candidates_by_siren(all_etablissements)
    succession_map: dict[str, str] = {}
    if succession_links is not None and not succession_links.empty:
        required_cols = {"siret_predecessor", "siret_successor"}
        if required_cols.issubset(set(succession_links.columns)):
            succession_rows = succession_links.dropna(subset=["siret_predecessor", "siret_successor"])
            succession_rows = succession_rows.drop_duplicates(subset=["siret_predecessor"], keep="first")
            succession_map = dict(
                zip(
                    succession_rows["siret_predecessor"].astype(str),
                    succession_rows["siret_successor"].astype(str),
                )
            )

    def suggest_active_sibling(row: pd.Series) -> tuple[str, int, str]:
        siren = str(row.get("siren", "") or "").strip()
        current_siret = str(row.get("siret_normalise", "") or "").strip()
        return _choose_active_sibling_candidate(
            siren=siren,
            current_siret=current_siret,
            candidates_by_siren=active_sibling_candidates,
        )

    overview["_tmp_replacement_from_succession"] = overview["siret_normalise"].map(
        lambda s: succession_map.get(str(s), "")
    )
    active_sibling_details = overview.apply(suggest_active_sibling, axis=1, result_type="expand")
    active_sibling_details.columns = [
        "_tmp_replacement_from_active_same_siren",
        "_tmp_active_same_siren_candidate_count",
        "_tmp_active_same_siren_choice_reason",
    ]
    overview = pd.concat([overview, active_sibling_details], axis=1)

    overview["siret_remplacement_recommande"] = overview["_tmp_replacement_from_succession"]
    empty_replacement = overview["siret_remplacement_recommande"].fillna("").astype(str).eq("")
    overview.loc[empty_replacement, "siret_remplacement_recommande"] = overview.loc[
        empty_replacement,
        "_tmp_replacement_from_active_same_siren",
    ]

    closed_mask = overview["siret_status"].eq(SIRET_STATUS_CLOSED)
    non_closed_mask = ~closed_mask
    overview.loc[non_closed_mask, "siret_remplacement_recommande"] = ""
    overview["cleaning_action"] = overview.apply(_classify_cleaning_action, axis=1)

    succession_replacement_mask = (
        closed_mask & overview["_tmp_replacement_from_succession"].fillna("").astype(str).ne("")
    )
    active_same_siren_replacement_mask = (
        closed_mask
        & overview["_tmp_replacement_from_succession"].fillna("").astype(str).eq("")
        & overview["_tmp_replacement_from_active_same_siren"].fillna("").astype(str).ne("")
    )
    no_replacement_available_mask = (
        closed_mask
        & overview["_tmp_replacement_from_succession"].fillna("").astype(str).eq("")
        & overview["_tmp_replacement_from_active_same_siren"].fillna("").astype(str).eq("")
    )

    overview["analysis_succession_disponible"] = ""
    overview.loc[succession_replacement_mask, "analysis_succession_disponible"] = "Oui"
    overview.loc[closed_mask & ~succession_replacement_mask, "analysis_succession_disponible"] = "Non"

    candidate_count_series = (
        pd.to_numeric(
            overview.get(
                "_tmp_active_same_siren_candidate_count",
                pd.Series(0, index=overview.index),
            ),
            errors="coerce",
        )
        .fillna(0)
        .astype("int64")
    )

    overview["analysis_nb_candidats_remplacement"] = ""
    overview.loc[active_same_siren_replacement_mask, "analysis_nb_candidats_remplacement"] = (
        candidate_count_series.loc[active_same_siren_replacement_mask]
    )
    overview.loc[no_replacement_available_mask, "analysis_nb_candidats_remplacement"] = 0

    overview["analysis_raison_choix_remplacement"] = ""
    multi_candidate_mask = active_same_siren_replacement_mask & candidate_count_series.gt(1)
    overview.loc[multi_candidate_mask, "analysis_raison_choix_remplacement"] = overview.loc[
        multi_candidate_mask,
        "_tmp_active_same_siren_choice_reason",
    ].fillna("").astype(str)

    overview["analysis_synthese_remplacement"] = ""
    overview.loc[succession_replacement_mask, "analysis_synthese_remplacement"] = "Succession"
    overview.loc[
        active_same_siren_replacement_mask,
        "analysis_synthese_remplacement",
    ] = "Autre SIRET même SIREN"
    overview.loc[no_replacement_available_mask, "analysis_synthese_remplacement"] = "Aucun"

    historique_count_series = (
        overview["historique_records_count"]
        if "historique_records_count" in overview.columns
        else pd.Series([0] * len(overview), index=overview.index)
    )
    overview["analysis_historique_disponible"] = (
        pd.to_numeric(historique_count_series, errors="coerce").fillna(0).gt(0)
    )
    closed_with_replacement_mask = (
        overview["siret_status"].eq(SIRET_STATUS_CLOSED)
        & overview["siret_remplacement_recommande"].fillna("").astype(str).ne("")
    )
    overview["analysis_priority"] = "LOW"
    overview.loc[overview["siret_status"].eq(SIRET_STATUS_INVALID), "analysis_priority"] = "HIGH"
    overview.loc[overview["siret_status"].eq(SIRET_STATUS_NOT_FOUND), "analysis_priority"] = "HIGH"
    overview.loc[
        overview["siret_status"].eq(SIRET_STATUS_CLOSED) & ~closed_with_replacement_mask,
        "analysis_priority",
    ] = "MEDIUM"
    overview.loc[closed_with_replacement_mask, "analysis_priority"] = "HIGH"

    def build_status_note(row: pd.Series) -> str:
        status = str(row.get("siret_status", "") or "")
        input_type = str(row.get("siret_input_type", "") or "").strip().upper()
        validation_route = str(row.get("siret_validation_route", "") or "").strip().upper()
        lookup_mode = str(row.get("analysis_lookup_mode", "") or "").strip().upper()
        resolved_siret = str(row.get("siret", "") or "").strip()
        replacement = str(row.get("siret_remplacement_recommande", "") or "").strip()
        synthese = str(row.get("analysis_synthese_remplacement", "") or "").strip()
        candidate_count_raw = pd.to_numeric(
            row.get("analysis_nb_candidats_remplacement", 0),
            errors="coerce",
        )
        candidate_count = int(candidate_count_raw) if pd.notna(candidate_count_raw) else 0
        choice_reason = str(row.get("analysis_raison_choix_remplacement", "") or "").strip()

        fallback_prefix = ""
        if validation_route == "SIREN_FALLBACK_FROM_SIRET":
            fallback_prefix = "SIRET invalide en 14, recherche effectuee en SIREN (9 premiers chiffres). "

        siren_prefix = ""
        if input_type == "SIREN":
            if lookup_mode == "SIREN_SIEGE" and resolved_siret:
                siren_prefix = f"Entree SIREN, siege retourne: {resolved_siret}. "
            elif lookup_mode == "SIREN_ACTIVE_FALLBACK" and resolved_siret:
                siren_prefix = (
                    f"Entree SIREN, siege absent, etablissement actif retenu: {resolved_siret}. "
                )
            elif status == SIRET_STATUS_NOT_FOUND:
                return f"{fallback_prefix}SIREN valide mais aucun etablissement trouve.".strip()

        if status == SIRET_STATUS_INVALID:
            return "Identifiant invalide (format SIRET/SIREN)."
        if status == SIRET_STATUS_NOT_FOUND:
            return f"{fallback_prefix}{siren_prefix}Identifiant valide mais non trouve dans SIRENE.".strip()
        if status == SIRET_STATUS_ACTIVE:
            return f"{fallback_prefix}{siren_prefix}SIRET actif.".strip()
        if status == SIRET_STATUS_CLOSED and synthese == "Succession" and replacement:
            return (
                f"{fallback_prefix}{siren_prefix}SIRET ferme, remplacement recommande: {replacement} (Succession)."
            ).strip()
        if status == SIRET_STATUS_CLOSED and synthese == "Autre SIRET même SIREN" and replacement:
            if candidate_count > 0:
                if choice_reason:
                    return (
                        f"{fallback_prefix}{siren_prefix}SIRET ferme, remplacement recommande: {replacement} "
                        f"(Autre SIRET même SIREN, {candidate_count} candidat(s)). {choice_reason}"
                    ).strip()
                return (
                    f"{fallback_prefix}{siren_prefix}SIRET ferme, remplacement recommande: {replacement} "
                    f"(Autre SIRET même SIREN, {candidate_count} candidat(s))."
                ).strip()
            return f"{fallback_prefix}{siren_prefix}SIRET ferme, remplacement recommande: {replacement}.".strip()
        if status == SIRET_STATUS_CLOSED and synthese == "Aucun":
            return f"{fallback_prefix}{siren_prefix}SIRET ferme sans remplacant disponible.".strip()
        if status == SIRET_STATUS_CLOSED:
            return f"{fallback_prefix}{siren_prefix}SIRET ferme.".strip()
        return f"{fallback_prefix}{siren_prefix}SIRET radie ou statut administratif atypique.".strip()

    overview["analysis_status_note"] = overview.apply(build_status_note, axis=1)
    overview = _apply_closed_row_data_policy(overview, all_etablissements=all_etablissements)
    _active_mask = overview["siret_status"].eq(SIRET_STATUS_ACTIVE)
    _replacement_mask = (
        overview["siret_status"].eq(SIRET_STATUS_CLOSED)
        & overview["siret_remplacement_recommande"].fillna("").astype(str).ne("")
    )
    overview["siret_retenu"] = ""
    overview.loc[_active_mask, "siret_retenu"] = (
        overview.loc[_active_mask, "siret"].fillna("").astype(str)
    )
    overview.loc[_replacement_mask, "siret_retenu"] = (
        overview.loc[_replacement_mask, "siret_remplacement_recommande"].fillna("").astype(str)
    )
    overview["analysis_nd_detecte"] = _build_nd_detection_mask(overview)
    overview["analysis_historique_disponible"] = overview["analysis_historique_disponible"].map(_to_yes_no)
    overview["analysis_nd_detecte"] = overview["analysis_nd_detecte"].map(_to_yes_no)
    overview["siret_doublon_entree"] = overview["siret_doublon_entree"].map(_to_yes_no)
    overview["siren_doublon_entree"] = overview["siren_doublon_entree"].map(_to_yes_no)
    overview["analysis_priority"] = overview["analysis_priority"].map(_priority_label_fr)
    overview["siret_status"] = overview["siret_status"].map(_status_label_fr)
    overview = overview.drop(
        columns=[
            "_tmp_replacement_from_succession",
            "_tmp_replacement_from_active_same_siren",
            "_tmp_active_same_siren_candidate_count",
            "_tmp_active_same_siren_choice_reason",
            "siret_remplacement_succession",
            "siret_remplacement_actif_meme_siren",
            "analysis_source_remplacement",
            "analysis_remplacement_identifie",
            "analysis_ferme_avec_remplacement",
            "analysis_lookup_mode",
            "siret_input_type",
            "siret_validation_route",
            "siret_lookup_key",
            "siret",
            "siret_hist",
        ],
        errors="ignore",
    )

    input_columns_filtered = [col for col in input_columns if col != siret_source_column]
    preferred_columns = (
        input_columns_filtered
        + [
            "siret_entree",
            "siret_normalise",
            "identifiant_recherche",
            "siret_format_valide",
            "siret_doublon_entree",
            "siren_doublon_entree",
            "siret_status",
            "cleaning_action",
            "siret_remplacement_recommande",
            "analysis_succession_disponible",
            "analysis_nb_candidats_remplacement",
            "analysis_raison_choix_remplacement",
            "analysis_synthese_remplacement",
            "analysis_historique_disponible",
            "analysis_nd_detecte",
            "analysis_priority",
            "analysis_status_note",
            "analysis_data_applied",
            "siret_retenu",
            "siren",
            "nic",
            "denomination_entreprise",
            "etatAdministratifEtablissement",
            "etatAdministratifUniteLegale",
            "adresse_reconstituee",
            "codePostalEtablissement",
            "libelleCommuneEtablissement",
            "dateDebut",
            "dateFin",
            "total_etablissements",
            "total_etablissements_actifs",
            "total_etablissements_fermes",
            "historique_records_count",
            "historique_latest_dateDebut",
            "historique_latest_dateFin",
        ]
    )
    existing = []
    seen = set()
    for col in preferred_columns + [c for c in overview.columns if c not in preferred_columns]:
        if col in overview.columns and col not in seen:
            existing.append(col)
            seen.add(col)
    return overview[existing].copy()


def _clamp_percent(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _chunked_values(values: list[str], chunk_size: int) -> list[list[str]]:
    return [values[idx : idx + chunk_size] for idx in range(0, len(values), chunk_size)]


def _choose_chunk_size(values_count: int, *, target_updates: int = 80) -> int:
    """Choose a chunk size that gives smoother progress without exploding query count."""
    if values_count <= 0:
        return 2000
    approx = int(values_count / max(1, target_updates))
    return min(5000, max(1200, approx))


def _business_data_columns_to_clear() -> set[str]:
    """Return business data columns that should be blanked when closed without replacement."""
    columns_to_clear = set(ETABLISSEMENT_CANONICAL_FIELDS + UNITE_LEGALE_CANONICAL_FIELDS)
    columns_to_clear.update(
        {
            "siret",
            "siren",
            "nic",
            "adresse_reconstituee",
            "denomination_entreprise",
            "total_etablissements",
            "total_etablissements_actifs",
            "total_etablissements_fermes",
            "historique_records_count",
            "historique_latest_dateDebut",
            "historique_latest_dateFin",
        }
    )
    return columns_to_clear


def _build_replacement_etablissement_lookup(
    all_etablissements: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    """Build a lookup map by replacement SIRET."""
    if all_etablissements.empty or "siret" not in all_etablissements.columns:
        return {}
    work = all_etablissements.copy()
    work["siret"] = work["siret"].fillna("").astype(str)
    work = work[work["siret"].ne("")]
    if work.empty:
        return {}
    work = work.drop_duplicates(subset=["siret"], keep="first")
    return work.set_index("siret").to_dict(orient="index")


def _apply_closed_row_data_policy(
    overview: pd.DataFrame,
    all_etablissements: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply business rule:
    - CLOSED + replacement found: apply replacement establishment data.
    - CLOSED + no replacement: clear business data columns.
    """
    if overview.empty:
        return overview

    result = overview.copy()
    replacement_lookup = _build_replacement_etablissement_lookup(all_etablissements)
    columns_to_clear = _business_data_columns_to_clear()
    if "analysis_data_applied" not in result.columns:
        result["analysis_data_applied"] = "INPUT_SIRET_DATA"

    # Cast numeric columns to object so empty-string assignment doesn't raise a FutureWarning
    _agg_cols = {
        "total_etablissements",
        "total_etablissements_actifs",
        "total_etablissements_fermes",
        "historique_records_count",
        "historique_latest_dateDebut",
        "historique_latest_dateFin",
    }
    for _col in columns_to_clear | _agg_cols:
        if _col in result.columns and result[_col].dtype != object:
            result[_col] = result[_col].astype(object)

    closed_mask = result["siret_status"].eq(SIRET_STATUS_CLOSED)
    for row_idx in result.index[closed_mask]:
        replacement_siret = str(result.at[row_idx, "siret_remplacement_recommande"] or "").strip()
        if replacement_siret:
            replacement_data = replacement_lookup.get(replacement_siret)
            if replacement_data:
                original_siren = str(result.at[row_idx, "siren"] or "")
                replacement_siren = str(replacement_data.get("siren", "") or "")
                for col in ETABLISSEMENT_CANONICAL_FIELDS + ["siret", "siren", "nic"]:
                    if col in result.columns:
                        result.at[row_idx, col] = replacement_data.get(col, "")
                result.at[row_idx, "adresse_reconstituee"] = build_address(
                    result.loc[row_idx], ADDRESS_COMPONENT_FIELDS
                )
                if original_siren != replacement_siren:
                    for ul_col in UNITE_LEGALE_CANONICAL_FIELDS:
                        if ul_col in result.columns:
                            result.at[row_idx, ul_col] = ""
                    if "denomination_entreprise" in result.columns:
                        result.at[row_idx, "denomination_entreprise"] = ""
                    for agg_col in [
                        "total_etablissements",
                        "total_etablissements_actifs",
                        "total_etablissements_fermes",
                        "historique_records_count",
                        "historique_latest_dateDebut",
                        "historique_latest_dateFin",
                    ]:
                        if agg_col in result.columns:
                            result.at[row_idx, agg_col] = ""
                result.at[row_idx, "analysis_data_applied"] = "REPLACEMENT_SIRET_DATA"
            else:
                for col in columns_to_clear:
                    if col in result.columns:
                        result.at[row_idx, col] = ""
                result.at[row_idx, "analysis_data_applied"] = "NO_DATA_REPLACEMENT_NOT_LOADED"
        else:
            for col in columns_to_clear:
                if col in result.columns:
                    result.at[row_idx, col] = ""
            result.at[row_idx, "analysis_data_applied"] = "NO_DATA_CLOSED_NO_REPLACEMENT"
    return result


def _fetch_in_chunks(
    *,
    values: list[str],
    fetch_fn: Callable[[list[str]], tuple[pd.DataFrame, dict[str, str], list[str]]],
    chunk_size: int,
    stage_start: int,
    stage_end: int,
    message: str,
    progress_callback: ProgressCallback | None,
    processed_rows_for_values: Callable[[set[str]], int],
    success_rows_for_found: Callable[[set[str]], int],
    base_failed_rows: int,
) -> tuple[pd.DataFrame, dict[str, str], list[str], set[str], set[str]]:
    """
    Fetch values in chunks and emit incremental progress.

    Returns:
    - concatenated dataframe
    - resolved column map
    - available columns
    - processed value set
    - found key set (siret/siren depending on fetch)
    """
    if not values:
        empty_df, col_map, available = fetch_fn([])
        return empty_df, col_map, available, set(), set()

    chunks = _chunked_values(values, chunk_size=chunk_size)
    processed_values: set[str] = set()
    found_keys: set[str] = set()
    all_parts: list[pd.DataFrame] = []
    resolved_map: dict[str, str] = {}
    available_columns: list[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        part_df, part_map, part_columns = fetch_fn(chunk)
        if idx == 1:
            resolved_map = part_map
            available_columns = part_columns
        if not part_df.empty:
            all_parts.append(part_df)
            if "siret" in part_df.columns:
                found_keys.update(part_df["siret"].dropna().astype(str).tolist())
            elif "siren" in part_df.columns:
                found_keys.update(part_df["siren"].dropna().astype(str).tolist())

        processed_values.update(chunk)
        if progress_callback:
            ratio = idx / len(chunks)
            percent = _clamp_percent(stage_start + (stage_end - stage_start) * ratio)
            processed_rows = processed_rows_for_values(processed_values)
            success_rows = success_rows_for_found(found_keys)
            failed_rows = max(base_failed_rows, processed_rows - success_rows)
            progress_callback(
                percent,
                f"{message} ({idx}/{len(chunks)})",
                processed_rows,
                success_rows,
                failed_rows,
            )

    if not all_parts:
        return pd.DataFrame(), resolved_map, available_columns, processed_values, found_keys
    return pd.concat(all_parts, ignore_index=True), resolved_map, available_columns, processed_values, found_keys


def _build_params_logs(sources: SireneSources, siret_column: str, total_rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"parameter": "execution_timestamp", "value": datetime.now().isoformat(timespec="seconds")},
            {"parameter": "input_siret_column", "value": siret_column},
            {"parameter": "input_row_count", "value": total_rows},
            {"parameter": "stocketablissement", "value": sources.stocketablissement},
            {"parameter": "stockunitelegale", "value": sources.stockunitelegale},
            {
                "parameter": "stocketablissementlienssuccession",
                "value": sources.stocketablissementlienssuccession or "",
            },
            {
                "parameter": "stocketablissementhistorique",
                "value": sources.stocketablissementhistorique or "",
            },
        ]
    )


def run_siret_control_pipeline(
    input_df: pd.DataFrame,
    siret_column: str,
    sources: SireneSources,
    output_input_columns: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ProcessResult:
    """Run the full control and enrichment pipeline."""
    if siret_column not in input_df.columns:
        raise ValueError(f"Selected SIRET column not found: {siret_column}")

    warnings: list[str] = []
    schema_report: dict[str, dict[str, Any]] = {}

    base_df = input_df.copy().reset_index(drop=True)
    input_columns = list(base_df.columns)
    output_input_columns_ordered = (
        [col for col in input_columns if col in set(output_input_columns)]
        if output_input_columns is not None
        else input_columns
    )
    validation_df = build_siret_validation_frame(base_df[siret_column])
    controle = pd.concat([base_df, validation_df], axis=1)
    lookup_keys = controle.get(
        "siret_lookup_key",
        pd.Series("", index=controle.index, dtype=str),
    ).fillna("").astype(str).str.strip()
    input_type_series = controle.get(
        "siret_input_type",
        pd.Series("", index=controle.index, dtype=str),
    ).fillna("").astype(str)
    valid_input_mask = controle["siret_format_ok"].astype(bool)
    siret_key_mask = valid_input_mask & input_type_series.eq("SIRET") & lookup_keys.ne("")
    siret_dup_counts = lookup_keys[siret_key_mask].value_counts()
    controle["siret_doublon_entree"] = (
        lookup_keys.map(siret_dup_counts).fillna(0).astype("int64").gt(1)
    )

    siren_keys_for_duplicates = pd.Series("", index=controle.index, dtype=str)
    siren_keys_for_duplicates.loc[siret_key_mask] = lookup_keys.loc[siret_key_mask].str[:9]
    siren_input_mask = valid_input_mask & input_type_series.eq("SIREN") & lookup_keys.ne("")
    siren_keys_for_duplicates.loc[siren_input_mask] = lookup_keys.loc[siren_input_mask]
    siren_dup_counts = siren_keys_for_duplicates[siren_keys_for_duplicates.ne("")].value_counts()
    controle["siren_doublon_entree"] = (
        siren_keys_for_duplicates.map(siren_dup_counts).fillna(0).astype("int64").gt(1)
    )
    if progress_callback:
        progress_callback(2, "Préparation et validation des identifiants SIRET/SIREN...", 0, 0, 0)

    invalid_rows = int((~controle["siret_format_ok"]).sum())

    valid_sirets = (
        controle.loc[controle["siret_format_ok"] & input_type_series.eq("SIRET"), "siret_lookup_key"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    valid_sirens_for_lookup = (
        controle.loc[controle["siret_format_ok"] & input_type_series.eq("SIREN"), "siret_lookup_key"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    input_siret_lookup_counts = (
        controle.loc[controle["siret_format_ok"] & input_type_series.eq("SIRET"), "siret_lookup_key"]
        .fillna("")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    input_siren_lookup_counts = (
        controle.loc[controle["siret_format_ok"] & input_type_series.eq("SIREN"), "siret_lookup_key"]
        .fillna("")
        .astype(str)
        .value_counts()
        .to_dict()
    )

    with SireneQueryService(sources) as service:
        etab_chunk_siret = _choose_chunk_size(len(valid_sirets), target_updates=10)
        stage_split = 32 if valid_sirens_for_lookup else 55
        etab_df, etab_map, etab_columns, processed_sirets, found_sirets = _fetch_in_chunks(
            values=valid_sirets,
            fetch_fn=service.fetch_establishments_by_sirets,
            chunk_size=etab_chunk_siret,
            stage_start=5,
            stage_end=stage_split,
            message="Lecture stocketablissement",
            progress_callback=progress_callback,
            processed_rows_for_values=lambda processed: invalid_rows
            + sum(input_siret_lookup_counts.get(value, 0) for value in processed),
            success_rows_for_found=lambda found: sum(
                input_siret_lookup_counts.get(value, 0) for value in found
            ),
            base_failed_rows=invalid_rows,
        )
        etab_chunk_siren = _choose_chunk_size(len(valid_sirens_for_lookup), target_updates=8)
        siren_lookup_df, siren_lookup_map, siren_lookup_columns, _, _ = _fetch_in_chunks(
            values=valid_sirens_for_lookup,
            fetch_fn=service.fetch_all_establishments_by_sirens,
            chunk_size=etab_chunk_siren,
            stage_start=stage_split,
            stage_end=55,
            message="Recherche etablissements pour entrees SIREN",
            progress_callback=progress_callback,
            processed_rows_for_values=lambda processed: invalid_rows
            + sum(input_siret_lookup_counts.get(value, 0) for value in processed_sirets)
            + sum(input_siren_lookup_counts.get(value, 0) for value in processed),
            success_rows_for_found=lambda found: sum(
                input_siret_lookup_counts.get(value, 0) for value in found_sirets
            )
            + sum(input_siren_lookup_counts.get(value, 0) for value in found),
            base_failed_rows=invalid_rows,
        )

        combined_etab_map = etab_map or siren_lookup_map
        combined_etab_columns = etab_columns or siren_lookup_columns
        schema_report["stocketablissement"] = {
            "available_columns_count": len(combined_etab_columns),
            "resolved_columns": combined_etab_map,
        }
        missing_etab = [c for c in ETABLISSEMENT_CANONICAL_FIELDS if c not in combined_etab_map]
        if missing_etab:
            warnings.append(
                "Missing establishment columns (handled defensively): " + ", ".join(missing_etab)
            )

        etab_df = _normalize_id_columns(etab_df)
        if "siret" in etab_df.columns:
            etab_df = etab_df.drop_duplicates(subset=["siret"], keep="first")
        siren_lookup_df = _normalize_id_columns(siren_lookup_df)
        selected_siren_df = _select_establishments_for_siren_inputs(siren_lookup_df)
        selected_sirens_lookup = (
            set(selected_siren_df["siren"].dropna().astype(str).tolist())
            if not selected_siren_df.empty and "siren" in selected_siren_df.columns
            else set()
        )

        establishment_matches: list[pd.DataFrame] = []
        if not etab_df.empty and "siret" in etab_df.columns:
            siret_matches = etab_df.copy()
            siret_matches["_tmp_lookup_key"] = siret_matches["siret"].fillna("").astype(str).str.strip()
            siret_matches["_tmp_siren_lookup_mode"] = ""
            establishment_matches.append(siret_matches)
        if not selected_siren_df.empty and "siren" in selected_siren_df.columns:
            siren_matches = selected_siren_df.copy()
            siren_matches["_tmp_lookup_key"] = siren_matches["siren"].fillna("").astype(str).str.strip()
            establishment_matches.append(siren_matches)

        if establishment_matches:
            matched_establishments = pd.concat(establishment_matches, ignore_index=True, sort=False)
            matched_establishments["_tmp_lookup_key"] = (
                matched_establishments["_tmp_lookup_key"].fillna("").astype(str).str.strip()
            )
            matched_establishments = matched_establishments[
                matched_establishments["_tmp_lookup_key"].ne("")
            ].drop_duplicates(subset=["_tmp_lookup_key"], keep="first")
            controle = controle.merge(
                matched_establishments,
                how="left",
                left_on="siret_lookup_key",
                right_on="_tmp_lookup_key",
                suffixes=("", "_etab"),
            )
        else:
            for field in ETABLISSEMENT_CANONICAL_FIELDS:
                if field not in controle.columns:
                    controle[field] = ""
            controle["_tmp_siren_lookup_mode"] = ""

        if "siren" not in controle.columns and "siren_etab" in controle.columns:
            controle["siren"] = controle["siren_etab"]
        if "nic" not in controle.columns and "nic_etab" in controle.columns:
            controle["nic"] = controle["nic_etab"]

        is_siren_input = controle["siret_format_ok"].astype(bool) & controle.get(
            "siret_input_type",
            pd.Series("", index=controle.index, dtype=str),
        ).fillna("").astype(str).eq("SIREN")
        siren_mode_series = controle.get(
            "_tmp_siren_lookup_mode",
            pd.Series("", index=controle.index, dtype=str),
        ).fillna("").astype(str)
        controle["analysis_lookup_mode"] = ""
        controle.loc[is_siren_input & siren_mode_series.eq("SIREN_SIEGE"), "analysis_lookup_mode"] = (
            "SIREN_SIEGE"
        )
        controle.loc[
            is_siren_input & siren_mode_series.eq("SIREN_ACTIVE_FALLBACK"),
            "analysis_lookup_mode",
        ] = "SIREN_ACTIVE_FALLBACK"
        controle.loc[is_siren_input & siren_mode_series.eq(""), "analysis_lookup_mode"] = (
            "SIREN_NOT_FOUND"
        )
        controle = controle.drop(columns=["_tmp_lookup_key", "_tmp_siren_lookup_mode"], errors="ignore")

        found_input_rows_count = (
            int(sum(input_siret_lookup_counts.get(value, 0) for value in found_sirets))
            + int(sum(input_siren_lookup_counts.get(value, 0) for value in selected_sirens_lookup))
        )

        found_sirens = (
            controle.get("siren", pd.Series(dtype=str))
            .fillna("")
            .astype(str)
            .map(lambda x: _normalize_identifier(x, 9))
        )
        found_sirens = sorted({s for s in found_sirens if s})
        input_siren_counts = controle["siren"].fillna("").astype(str).value_counts().to_dict()

        ul_chunk = _choose_chunk_size(len(found_sirens), target_updates=10)
        ul_df, ul_map, ul_columns, _, _ = _fetch_in_chunks(
            values=found_sirens,
            fetch_fn=service.fetch_unites_legales_by_sirens,
            chunk_size=ul_chunk,
            stage_start=55,
            stage_end=68,
            message="Lecture stockunitelegale",
            progress_callback=progress_callback,
            processed_rows_for_values=lambda processed: invalid_rows
            + sum(input_siren_counts.get(value, 0) for value in processed),
            success_rows_for_found=lambda _: found_input_rows_count,
            base_failed_rows=invalid_rows,
        )
        schema_report["stockunitelegale"] = {
            "available_columns_count": len(ul_columns),
            "resolved_columns": ul_map,
        }
        missing_ul = [c for c in UNITE_LEGALE_CANONICAL_FIELDS if c not in ul_map]
        if missing_ul:
            warnings.append("Missing legal unit columns (handled defensively): " + ", ".join(missing_ul))

        ul_df = _normalize_id_columns(ul_df)
        if not ul_df.empty and "siren" in ul_df.columns:
            ul_df = ul_df.drop_duplicates(subset=["siren"], keep="first")
            controle = controle.merge(ul_df, how="left", on="siren", suffixes=("", "_ul"))
        else:
            for field in UNITE_LEGALE_CANONICAL_FIELDS:
                if field not in controle.columns:
                    controle[field] = ""

        all_etab_chunk = _choose_chunk_size(len(found_sirens), target_updates=10)
        all_etab_df, all_map, all_columns, _, _ = _fetch_in_chunks(
            values=found_sirens,
            fetch_fn=service.fetch_all_establishments_by_sirens,
            chunk_size=all_etab_chunk,
            stage_start=68,
            stage_end=80,
            message="Récupération des établissements du même SIREN",
            progress_callback=progress_callback,
            processed_rows_for_values=lambda processed: invalid_rows
            + sum(input_siren_counts.get(value, 0) for value in processed),
            success_rows_for_found=lambda _: found_input_rows_count,
            base_failed_rows=invalid_rows,
        )
        schema_report["all_etablissements"] = {
            "available_columns_count": len(all_columns),
            "resolved_columns": all_map,
        }
        all_etab_df = _normalize_id_columns(all_etab_df)

        aggregates = _compute_aggregates(all_etab_df)
        controle = controle.merge(aggregates, how="left", on="siren")
        controle = _ensure_int_columns(
            controle,
            ["total_etablissements", "total_etablissements_actifs", "total_etablissements_fermes"],
        )

        succession_df: pd.DataFrame | None = None
        if sources.stocketablissementlienssuccession:
            if progress_callback:
                progress_callback(
                    83,
                    "Lecture des liens de succession...",
                    int(len(controle)),
                    found_input_rows_count,
                    invalid_rows,
                )
            succession_df, succession_map, succession_columns = service.fetch_succession_links(valid_sirets)
            schema_report["stocketablissementlienssuccession"] = {
                "available_columns_count": len(succession_columns),
                "resolved_columns": succession_map,
            }
            if succession_df is not None and not succession_df.empty:
                if "siret_predecessor" in succession_df.columns:
                    succession_df["siret_predecessor"] = succession_df["siret_predecessor"].map(
                        lambda x: _normalize_identifier(x, 14)
                    )
                if "siret_successor" in succession_df.columns:
                    succession_df["siret_successor"] = succession_df["siret_successor"].map(
                        lambda x: _normalize_identifier(x, 14)
                    )
            else:
                warnings.append(
                    "Succession file provided but no matching links were found for input SIRET values."
                )

        historique_df: pd.DataFrame | None = None
        if sources.stocketablissementhistorique:
            if progress_callback:
                progress_callback(
                    88,
                    "Lecture de l'historique...",
                    int(len(controle)),
                    found_input_rows_count,
                    invalid_rows,
                )
            historique_df, hist_map, hist_columns = service.fetch_historique(
                sirets=valid_sirets,
                sirens=found_sirens,
            )
            schema_report["stocketablissementhistorique"] = {
                "available_columns_count": len(hist_columns),
                "resolved_columns": hist_map,
            }
            if historique_df is not None and not historique_df.empty:
                historique_df = _normalize_id_columns(historique_df)
                selected_hist_cols = [
                    col for col in HISTORIQUE_PRIORITY_FIELDS if col in historique_df.columns
                ]
                historique_df = historique_df[selected_hist_cols].copy()
                historique_summary, hist_key = _build_historique_summary(historique_df)
                if not historique_summary.empty and hist_key:
                    if hist_key == "siret":
                        controle = controle.merge(
                            historique_summary,
                            how="left",
                            left_on="siret_lookup_key",
                            right_on="siret",
                            suffixes=("", "_hist"),
                        )
                    else:
                        controle = controle.merge(
                            historique_summary,
                            how="left",
                            on="siren",
                            suffixes=("", "_hist"),
                        )
            else:
                warnings.append(
                    "Historique file provided but no matching historical rows were found."
                )

    for col in ETABLISSEMENT_CANONICAL_FIELDS + UNITE_LEGALE_CANONICAL_FIELDS:
        if col not in controle.columns:
            controle[col] = ""

    if "etatAdministratifEtablissement" not in controle.columns:
        controle["etatAdministratifEtablissement"] = ""

    controle["adresse_reconstituee"] = controle.apply(
        lambda row: build_address(row, ADDRESS_COMPONENT_FIELDS),
        axis=1,
    )
    controle["denomination_entreprise"] = controle.apply(_build_denomination_entreprise, axis=1)

    controle["siret_status"] = SIRET_STATUS_INVALID
    valid_mask = controle["siret_format_ok"].astype(bool)
    found_mask = valid_mask & controle["siret"].fillna("").astype(str).ne("")
    controle.loc[valid_mask & ~found_mask, "siret_status"] = SIRET_STATUS_NOT_FOUND
    controle.loc[found_mask, "siret_status"] = controle.loc[
        found_mask, "etatAdministratifEtablissement"
    ].map(classify_etablissement_status)
    # Business rule:
    # - CLOSED: input establishment closed, but at least one sibling establishment is active.
    # - RADIATED: no active establishment remains for the SIREN.
    radiated_mask = (
        controle["siret_status"].eq(SIRET_STATUS_CLOSED)
        & controle["total_etablissements_actifs"].fillna(0).le(0)
    )
    controle.loc[radiated_mask, "siret_status"] = SIRET_STATUS_RADIATED

    move_mask = (
        controle["siret_status"].eq(SIRET_STATUS_CLOSED)
        & controle["total_etablissements_actifs"].gt(0)
    )
    move_candidates = controle.loc[move_mask].copy()
    move_candidates["move_candidate_reason"] = (
        "Input SIRET is closed and at least one sibling establishment is active."
    )

    if sources.stocketablissementlienssuccession and succession_df is not None and not succession_df.empty:
        if "siret_predecessor" in succession_df.columns and "siret_successor" in succession_df.columns:
            successor_by_predecessor = (
                succession_df.dropna(subset=["siret_predecessor", "siret_successor"])
                .drop_duplicates(subset=["siret_predecessor"], keep="first")
                .set_index("siret_predecessor")["siret_successor"]
            )
            move_candidates["successeur_potentiel"] = move_candidates["siret_lookup_key"].map(
                successor_by_predecessor
            )

    metrics = {
        "total_input_siret": int(len(controle)),
        "valid_siret_format": int(controle["siret_format_ok"].sum()),
        "found_in_sirene": int(found_mask.sum()),
        "active": int(controle["siret_status"].eq(SIRET_STATUS_ACTIVE).sum()),
        "closed": int(controle["siret_status"].eq(SIRET_STATUS_CLOSED).sum()),
        "radiated": int(controle["siret_status"].eq(SIRET_STATUS_RADIATED).sum()),
        "not_found": int(controle["siret_status"].eq(SIRET_STATUS_NOT_FOUND).sum()),
        "invalid_format": int(controle["siret_status"].eq(SIRET_STATUS_INVALID).sum()),
        "move_candidates": int(move_mask.sum()),
        "duplicate_siren": int(siren_dup_counts.gt(1).sum()),
    }

    if progress_callback:
        progress_callback(
            92,
            "Finalisation du tableau de sortie...",
            metrics["total_input_siret"],
            metrics["found_in_sirene"],
            metrics["invalid_format"] + metrics["not_found"],
        )

    params_logs = _build_params_logs(sources, siret_column=siret_column, total_rows=len(controle))

    sorted_columns = (
        list(input_df.columns)
        + [
            "siret_input",
            "siret_normalized",
            "siret_lookup_key",
            "siret_len_ok",
            "siret_luhn_ok",
            "siret_format_ok",
            "siret_doublon_entree",
            "siren_doublon_entree",
            "siret_status",
            "siren",
            "nic",
            "adresse_reconstituee",
            "denomination_entreprise",
            "total_etablissements",
            "total_etablissements_actifs",
            "total_etablissements_fermes",
            "historique_records_count",
            "historique_latest_dateDebut",
            "historique_latest_dateFin",
        ]
        + ETABLISSEMENT_CANONICAL_FIELDS
        + UNITE_LEGALE_CANONICAL_FIELDS
    )
    unique_sorted_columns = []
    seen = set()
    for col in sorted_columns + [c for c in controle.columns if c not in sorted_columns]:
        if col not in seen and col in controle.columns:
            unique_sorted_columns.append(col)
            seen.add(col)
    controle = controle[unique_sorted_columns].copy()
    siret_overview = _build_siret_overview(
        controle_siret=controle,
        input_columns=output_input_columns_ordered,
        siret_source_column=siret_column,
        all_etablissements=all_etab_df if not all_etab_df.empty else pd.DataFrame(),
        succession_links=succession_df if succession_df is not None and not succession_df.empty else None,
    )
    controle = controle.drop(
        columns=[
            "analysis_lookup_mode",
            "siret_input_type",
            "siret_validation_route",
            "siret_lookup_key",
        ],
        errors="ignore",
    )

    return ProcessResult(
        controle_siret=controle,
        siret_overview=siret_overview,
        all_etablissements=all_etab_df if not all_etab_df.empty else pd.DataFrame(),
        move_candidates=move_candidates,
        succession_links=succession_df if succession_df is not None and not succession_df.empty else None,
        historique=historique_df if historique_df is not None and not historique_df.empty else None,
        params_logs=params_logs,
        metrics=metrics,
        warnings=warnings,
        schema_report=schema_report,
    )
