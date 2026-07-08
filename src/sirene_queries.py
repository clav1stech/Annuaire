"""DuckDB queries for SIRENE parquet files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import duckdb
import pandas as pd

# Regex used to strip legal-form abbreviations before fuzzy name comparison.
_LEGAL_FORM_RE = r"\b(SAS|SARL|SA|SNC|EURL|SASU|SCI|GIE|EI)\b"

from .sirene_schema import (
    ETABLISSEMENT_COLUMN_ALIASES,
    HISTORIQUE_COLUMN_ALIASES,
    SUCCESSION_COLUMN_ALIASES,
    UNITE_LEGALE_COLUMN_ALIASES,
    build_select_expressions,
    resolve_column_map,
    sql_identifier,
)


@dataclass
class SireneSources:
    """Container for parquet sources."""

    stocketablissement: str
    stockunitelegale: str
    stocketablissementlienssuccession: str | None = None
    stocketablissementhistorique: str | None = None


class SireneQueryService:
    """Execute SIRENE parquet queries through a local DuckDB connection."""

    def __init__(self, sources: SireneSources) -> None:
        self.sources = sources
        self.con = duckdb.connect(database=":memory:")
        self._schema_cache: dict[str, list[str]] = {}

    def close(self) -> None:
        """Close DuckDB connection."""
        self.con.close()

    def __enter__(self) -> "SireneQueryService":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore[override]
        self.close()

    def list_columns(self, source: str) -> list[str]:
        """List available parquet columns with DuckDB describe."""
        if source in self._schema_cache:
            return self._schema_cache[source]
        query = "DESCRIBE SELECT * FROM read_parquet(?)"
        try:
            schema_df = self.con.execute(query, [source]).df()
        except Exception as exc:
            raise ValueError(f"Failed to inspect parquet schema: {source}\n{exc}") from exc
        columns = schema_df["column_name"].astype(str).tolist()
        self._schema_cache[source] = columns
        return columns

    def _query_by_values(
        self,
        source: str,
        alias_map: dict[str, list[str]],
        values: Iterable[str],
        parquet_key: str,
        tmp_table_name: str,
        tmp_column_name: str,
    ) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
        values_list = [str(v) for v in values if str(v)]
        available_columns = self.list_columns(source)
        resolved_map = resolve_column_map(available_columns, alias_map)
        if parquet_key not in resolved_map:
            raise ValueError(
                f"Required column '{parquet_key}' was not found. "
                f"Available columns include: {', '.join(available_columns[:20])}"
            )
        if not values_list:
            return pd.DataFrame(columns=list(resolved_map.keys())), resolved_map, available_columns

        select_exprs = build_select_expressions(resolved_map, table_alias="p")
        select_clause = ", ".join(select_exprs) if select_exprs else "1"

        temp_df = pd.DataFrame({tmp_column_name: sorted(set(values_list))})
        self.con.register(tmp_table_name, temp_df)
        try:
            query = f"""
                SELECT {select_clause}
                FROM read_parquet(?) p
                INNER JOIN {tmp_table_name} t
                    ON CAST(p.{sql_identifier(resolved_map[parquet_key])} AS VARCHAR) = t.{sql_identifier(tmp_column_name)}
            """
            df = self.con.execute(query, [source]).df()
        finally:
            self.con.unregister(tmp_table_name)
        return df, resolved_map, available_columns

    def fetch_establishments_by_sirets(
        self,
        sirets: Iterable[str],
    ) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
        """Fetch matching establishments from stocketablissement."""
        return self._query_by_values(
            source=self.sources.stocketablissement,
            alias_map=ETABLISSEMENT_COLUMN_ALIASES,
            values=sirets,
            parquet_key="siret",
            tmp_table_name="tmp_sirets",
            tmp_column_name="siret_key",
        )

    def fetch_all_establishments_by_sirens(
        self,
        sirens: Iterable[str],
    ) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
        """Fetch all establishments linked to sirens."""
        return self._query_by_values(
            source=self.sources.stocketablissement,
            alias_map=ETABLISSEMENT_COLUMN_ALIASES,
            values=sirens,
            parquet_key="siren",
            tmp_table_name="tmp_sirens_for_etab",
            tmp_column_name="siren_key",
        )

    def fetch_unites_legales_by_sirens(
        self,
        sirens: Iterable[str],
    ) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
        """Fetch legal units from stockunitelegale."""
        return self._query_by_values(
            source=self.sources.stockunitelegale,
            alias_map=UNITE_LEGALE_COLUMN_ALIASES,
            values=sirens,
            parquet_key="siren",
            tmp_table_name="tmp_sirens_for_ul",
            tmp_column_name="siren_key",
        )

    def fetch_succession_links(
        self,
        input_sirets: Iterable[str],
    ) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
        """Fetch succession links when optional parquet is provided."""
        if not self.sources.stocketablissementlienssuccession:
            return pd.DataFrame(), {}, []

        source = self.sources.stocketablissementlienssuccession
        input_sirets_list = sorted({str(s) for s in input_sirets if str(s)})
        available_columns = self.list_columns(source)
        resolved_map = resolve_column_map(available_columns, SUCCESSION_COLUMN_ALIASES)
        predecessor_col = resolved_map.get("siretEtablissementPredecesseur")
        successor_col = resolved_map.get("siretEtablissementSuccesseur")
        if not predecessor_col and not successor_col:
            return pd.DataFrame(), resolved_map, available_columns
        if not input_sirets_list:
            return pd.DataFrame(columns=list(resolved_map.keys())), resolved_map, available_columns

        select_exprs = build_select_expressions(resolved_map, table_alias="p")
        if predecessor_col:
            select_exprs.append(
                f"CAST(p.{sql_identifier(predecessor_col)} AS VARCHAR) AS {sql_identifier('siret_predecessor')}"
            )
        if successor_col:
            select_exprs.append(
                f"CAST(p.{sql_identifier(successor_col)} AS VARCHAR) AS {sql_identifier('siret_successor')}"
            )
        select_clause = ", ".join(select_exprs) if select_exprs else "1"

        self.con.register("tmp_input_sirets", pd.DataFrame({"siret_key": input_sirets_list}))
        try:
            if predecessor_col and successor_col:
                query = f"""
                    SELECT
                        {select_clause},
                        CASE
                            WHEN i_pred.siret_key IS NOT NULL AND i_succ.siret_key IS NOT NULL THEN 'INPUT_IS_PREDECESSOR_AND_SUCCESSOR'
                            WHEN i_pred.siret_key IS NOT NULL THEN 'INPUT_IS_PREDECESSOR'
                            WHEN i_succ.siret_key IS NOT NULL THEN 'INPUT_IS_SUCCESSOR'
                            ELSE 'NO_MATCH'
                        END AS input_match_type
                    FROM read_parquet(?) p
                    LEFT JOIN tmp_input_sirets i_pred
                        ON CAST(p.{sql_identifier(predecessor_col)} AS VARCHAR) = i_pred.siret_key
                    LEFT JOIN tmp_input_sirets i_succ
                        ON CAST(p.{sql_identifier(successor_col)} AS VARCHAR) = i_succ.siret_key
                    WHERE i_pred.siret_key IS NOT NULL OR i_succ.siret_key IS NOT NULL
                """
            elif predecessor_col:
                query = f"""
                    SELECT
                        {select_clause},
                        'INPUT_IS_PREDECESSOR' AS input_match_type
                    FROM read_parquet(?) p
                    INNER JOIN tmp_input_sirets i_pred
                        ON CAST(p.{sql_identifier(predecessor_col)} AS VARCHAR) = i_pred.siret_key
                """
            else:
                query = f"""
                    SELECT
                        {select_clause},
                        'INPUT_IS_SUCCESSOR' AS input_match_type
                    FROM read_parquet(?) p
                    INNER JOIN tmp_input_sirets i_succ
                        ON CAST(p.{sql_identifier(successor_col)} AS VARCHAR) = i_succ.siret_key
                """
            df = self.con.execute(query, [source]).df()
        finally:
            self.con.unregister("tmp_input_sirets")
        return df, resolved_map, available_columns

    def fetch_historique(
        self,
        sirets: Iterable[str],
        sirens: Iterable[str],
    ) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
        """Fetch historical records when optional parquet is provided."""
        if not self.sources.stocketablissementhistorique:
            return pd.DataFrame(), {}, []

        source = self.sources.stocketablissementhistorique
        input_sirets = sorted({str(s) for s in sirets if str(s)})
        input_sirens = sorted({str(s) for s in sirens if str(s)})
        available_columns = self.list_columns(source)
        resolved_map = resolve_column_map(available_columns, HISTORIQUE_COLUMN_ALIASES)
        siret_col = resolved_map.get("siret")
        siren_col = resolved_map.get("siren")

        if not siret_col and not siren_col:
            return pd.DataFrame(), resolved_map, available_columns
        if not input_sirets and not input_sirens:
            return pd.DataFrame(columns=list(resolved_map.keys())), resolved_map, available_columns

        select_exprs = build_select_expressions(resolved_map, table_alias="p")
        select_clause = ", ".join(select_exprs) if select_exprs else "1"

        if siret_col and input_sirets:
            self.con.register("tmp_hist_sirets", pd.DataFrame({"siret_key": input_sirets}))
            try:
                query = f"""
                    SELECT {select_clause}
                    FROM read_parquet(?) p
                    INNER JOIN tmp_hist_sirets t
                        ON CAST(p.{sql_identifier(siret_col)} AS VARCHAR) = t.siret_key
                """
                df = self.con.execute(query, [source]).df()
            finally:
                self.con.unregister("tmp_hist_sirets")
            return df, resolved_map, available_columns

        self.con.register("tmp_hist_sirens", pd.DataFrame({"siren_key": input_sirens}))
        try:
            query = f"""
                SELECT {select_clause}
                FROM read_parquet(?) p
                INNER JOIN tmp_hist_sirens t
                    ON CAST(p.{sql_identifier(siren_col)} AS VARCHAR) = t.siren_key
            """
            df = self.con.execute(query, [source]).df()
        finally:
            self.con.unregister("tmp_hist_sirens")
        return df, resolved_map, available_columns

    def search_candidates_by_text(
        self,
        name_token: str,
        zip_code: str | None = None,
        limit: int = 3,
    ) -> pd.DataFrame:
        """Return top-N establishments ranked by fuzzy name similarity.

        Scans both active ('A') and closed ('F') establishments so that a
        zip-code bonus still rewards old addresses present in the input file.
        One result per SIREN is kept (highest score wins) via QUALIFY
        ROW_NUMBER().  Resolving a potential move is left to the caller
        (e.g. app.py enrichment pipeline).
        """
        etab_source = self.sources.stocketablissement
        ul_source = self.sources.stockunitelegale

        etab_cols = self.list_columns(etab_source)
        ul_cols = self.list_columns(ul_source)
        etab_map = resolve_column_map(etab_cols, ETABLISSEMENT_COLUMN_ALIASES)
        ul_map = resolve_column_map(ul_cols, UNITE_LEGALE_COLUMN_ALIASES)

        clean_token = re.sub(_LEGAL_FORM_RE, "", name_token.upper()).strip()
        if len(clean_token) < 3:
            return pd.DataFrame(columns=["siret", "denomination", "adresse", "score_similarite"])

        for key, mapping, label in [
            ("siret", etab_map, "stocketablissement"),
            ("siren", etab_map, "stocketablissement"),
            ("siren", ul_map, "stockunitelegale"),
        ]:
            if key not in mapping:
                raise ValueError(
                    f"Required column '{key}' not found in {label}. "
                    f"Available columns: {', '.join(etab_cols[:20] if label == 'stocketablissement' else ul_cols[:20])}"
                )

        build_select_expressions(etab_map, table_alias="e")
        build_select_expressions(ul_map, table_alias="u")

        # --- Denomination COALESCE ------------------------------------------
        denom_candidates = [
            ("u", "denominationUniteLegale", ul_map),
            ("u", "denominationUsuelle1UniteLegale", ul_map),
            ("e", "denominationUsuelleEtablissement", etab_map),
            ("e", "enseigne1Etablissement", etab_map),
            ("u", "nomUniteLegale", ul_map),
        ]
        coalesce_terms = [
            f"NULLIF(CAST({alias}.{sql_identifier(m[canon])} AS VARCHAR), '')"
            for alias, canon, m in denom_candidates
            if canon in m
        ]
        if not coalesce_terms:
            raise ValueError(
                "No denomination column could be resolved from either parquet source."
            )
        denom_coalesce = f"COALESCE({', '.join(coalesce_terms)})"

        # --- Address CONCAT -------------------------------------------------
        addr_terms = [
            f"NULLIF(CAST(e.{sql_identifier(etab_map[canon])} AS VARCHAR), '')"
            for canon in (
                "numeroVoieEtablissement",
                "typeVoieEtablissement",
                "libelleVoieEtablissement",
                "codePostalEtablissement",
                "libelleCommuneEtablissement",
            )
            if canon in etab_map
        ]
        addr_expr = f"TRIM(CONCAT_WS(' ', {', '.join(addr_terms)}))" if addr_terms else "''"

        # --- Similarity expression with optional zip bonus ------------------
        siren_etab = sql_identifier(etab_map["siren"])
        siren_ul = sql_identifier(ul_map["siren"])
        siret_expr = (
            f"CAST(e.{sql_identifier(etab_map['siret'])} AS VARCHAR)"
            f" AS {sql_identifier('siret')}"
        )

        stripped_col = f"TRIM(regexp_replace(UPPER({denom_coalesce}), ?, '', 'g'))"
        base_similarity = f"jaro_winkler_similarity(?, {stripped_col})"
        zip_bonus_available = bool(zip_code and "codePostalEtablissement" in etab_map)
        if zip_bonus_available:
            cp_col = sql_identifier(etab_map["codePostalEtablissement"])
            score_expr = (
                f"LEAST(1.0, {base_similarity} + "
                f"CASE WHEN CAST(e.{cp_col} AS VARCHAR) = ? THEN 0.05 ELSE 0.0 END)"
            )
        else:
            score_expr = base_similarity

        # --- Query: two CTEs, one scan each ---------------------------------
        # fuzzy_matches : score every establishment (A and F)
        # best_sirens   : keep the highest-scoring establishment per SIREN
        query = f"""
        WITH fuzzy_matches AS (
            SELECT
                {siret_expr},
                CAST(e.{siren_etab} AS VARCHAR) AS "siren_key",
                {denom_coalesce} AS "denomination",
                {addr_expr}      AS "adresse",
                {score_expr}     AS "score_similarite"
            FROM read_parquet(?) e
            INNER JOIN read_parquet(?) u
                ON CAST(e.{siren_etab} AS VARCHAR) = CAST(u.{siren_ul} AS VARCHAR)
        ),
        best_sirens AS (
            SELECT *
            FROM fuzzy_matches
            QUALIFY ROW_NUMBER() OVER(
                PARTITION BY "siren_key" ORDER BY "score_similarite" DESC
            ) = 1
        )
        SELECT "siret", "denomination", "adresse", "score_similarite"
        FROM best_sirens
        ORDER BY "score_similarite" DESC
        LIMIT {limit}
        """

        # Parameter order (left-to-right '?' in the query):
        # 1. regexp_replace pattern  → _LEGAL_FORM_RE
        # 2. jaro_winkler first arg  → clean_token
        # 3. zip bonus (optional)    → zip_code
        # 4. read_parquet(?) e       → etab_source
        # 5. read_parquet(?) u       → ul_source
        params: list[object] = [_LEGAL_FORM_RE, clean_token]
        if zip_bonus_available:
            params.append(zip_code)
        params.extend([etab_source, ul_source])

        return self.con.execute(query, params).df()

