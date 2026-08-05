"""Tests de la chaîne de succession SIRET (remplacement recommandé).

Un successeur SIRENE peut lui-même être fermé : ces tests figent le parcours de la
chaîne jusqu'à un successeur exploitable, ses garde-fous (cycle, profondeur) et le
repli sur un établissement actif du même SIREN.
"""

from __future__ import annotations

import pandas as pd

from src.config import SIRET_STATUS_ACTIVE, SIRET_STATUS_CLOSED
from src.pipeline import (
    _build_siret_overview,
    _expand_succession_chain,
    _resolve_active_successor,
    _status_by_siret,
    _succession_map_from_links,
)

SIRET_A = "11111111100011"
SIRET_B = "22222222200022"
SIRET_C = "33333333300033"
SIRET_D = "44444444400044"


def _links(pairs: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(pairs, columns=["siret_predecessor", "siret_successor"])


def _dated_links(rows: list[tuple[str, str, str, object]]) -> pd.DataFrame:
    """Liens de succession complets (date + continuité économique), comme SIRENE les livre."""
    return pd.DataFrame(
        rows,
        columns=[
            "siret_predecessor",
            "siret_successor",
            "dateLienSuccession",
            "continuiteEconomique",
        ],
    )


class TestSuccessionMapFromLinks:
    def test_empty_or_missing_columns_yield_empty_map(self):
        assert _succession_map_from_links(None) == {}
        assert _succession_map_from_links(pd.DataFrame()) == {}
        assert _succession_map_from_links(pd.DataFrame({"autre": ["x"]})) == {}

    def test_lowest_successor_wins_without_date_column(self):
        # Sans date ni continuité, le tri sur le SIRET successeur garde un résultat
        # reproductible quel que soit l'ordre de lecture du Parquet.
        links = _links([(SIRET_A, SIRET_C), (SIRET_A, SIRET_B)])
        assert _succession_map_from_links(links) == {SIRET_A: SIRET_B}

    def test_most_recent_link_wins(self):
        # Cas réel : deux reprises anciennes par d'autres entreprises, puis un transfert
        # interne récent. C'est le mouvement le plus récent qui décrit la situation.
        links = _dated_links(
            [
                (SIRET_A, SIRET_C, "1997-08-01", True),
                (SIRET_A, SIRET_D, "2003-04-05", True),
                (SIRET_A, SIRET_B, "2011-07-25", False),
            ]
        )
        assert _succession_map_from_links(links) == {SIRET_A: SIRET_B}

    def test_economic_continuity_breaks_a_date_tie(self):
        links = _dated_links(
            [
                (SIRET_A, SIRET_B, "2011-07-25", False),
                (SIRET_A, SIRET_C, "2011-07-25", True),
            ]
        )
        assert _succession_map_from_links(links) == {SIRET_A: SIRET_C}

    def test_missing_date_never_outranks_a_dated_link(self):
        links = _dated_links(
            [
                (SIRET_A, SIRET_B, "", True),
                (SIRET_A, SIRET_C, "1997-08-01", False),
            ]
        )
        assert _succession_map_from_links(links) == {SIRET_A: SIRET_C}

    def test_order_of_rows_does_not_change_the_result(self):
        pairs = [
            (SIRET_A, SIRET_C, "1997-08-01", True),
            (SIRET_A, SIRET_B, "2011-07-25", False),
        ]
        assert _succession_map_from_links(_dated_links(pairs)) == _succession_map_from_links(
            _dated_links(list(reversed(pairs)))
        )

    def test_duckdb_string_booleans_are_understood(self):
        # DuckDB renvoie les colonnes SIRENE castées en VARCHAR : "true"/"false".
        links = _dated_links(
            [
                (SIRET_A, SIRET_B, "2011-07-25", "false"),
                (SIRET_A, SIRET_C, "2011-07-25", "true"),
            ]
        )
        assert _succession_map_from_links(links) == {SIRET_A: SIRET_C}


class TestStatusBySiret:
    def test_reads_administrative_state_and_ignores_blank_sirets(self):
        etablissements = pd.DataFrame(
            {
                "siret": [SIRET_A, "", SIRET_B],
                "etatAdministratifEtablissement": ["F", "A", "A"],
            }
        )
        assert _status_by_siret(etablissements) == {SIRET_A: "F", SIRET_B: "A"}

    def test_missing_columns_yield_empty_map(self):
        assert _status_by_siret(pd.DataFrame({"siret": [SIRET_A]})) == {}


class TestResolveActiveSuccessor:
    def test_single_level_active_successor(self):
        resolved = _resolve_active_successor(
            SIRET_A,
            succession_map={SIRET_A: SIRET_B},
            status_by_siret={SIRET_B: "A"},
        )
        assert resolved == SIRET_B

    def test_cascade_skips_closed_successors(self):
        resolved = _resolve_active_successor(
            SIRET_A,
            succession_map={SIRET_A: SIRET_B, SIRET_B: SIRET_C, SIRET_C: SIRET_D},
            status_by_siret={SIRET_B: "F", SIRET_C: "F", SIRET_D: "A"},
        )
        assert resolved == SIRET_D

    def test_unknown_status_is_accepted(self):
        # Statut absent du stock chargé : rien ne permet d'écarter ce successeur.
        resolved = _resolve_active_successor(
            SIRET_A,
            succession_map={SIRET_A: SIRET_B},
            status_by_siret={},
        )
        assert resolved == SIRET_B

    def test_cycle_returns_no_replacement(self):
        resolved = _resolve_active_successor(
            SIRET_A,
            succession_map={SIRET_A: SIRET_B, SIRET_B: SIRET_A},
            status_by_siret={SIRET_A: "F", SIRET_B: "F"},
        )
        assert resolved == ""

    def test_chain_of_closed_successors_without_end_returns_nothing(self):
        resolved = _resolve_active_successor(
            SIRET_A,
            succession_map={SIRET_A: SIRET_B, SIRET_B: SIRET_C},
            status_by_siret={SIRET_B: "F", SIRET_C: "F"},
        )
        assert resolved == ""

    def test_depth_limit_stops_the_walk(self):
        resolved = _resolve_active_successor(
            SIRET_A,
            succession_map={SIRET_A: SIRET_B, SIRET_B: SIRET_C, SIRET_C: SIRET_D},
            status_by_siret={SIRET_B: "F", SIRET_C: "F", SIRET_D: "A"},
            max_depth=2,
        )
        assert resolved == ""

    def test_no_link_or_empty_input(self):
        assert _resolve_active_successor("", succession_map={}, status_by_siret={}) == ""
        assert (
            _resolve_active_successor(SIRET_A, succession_map={}, status_by_siret={}) == ""
        )


class _FakeQueryService:
    """Service SIRENE minimal : renvoie des niveaux de chaîne prédéfinis."""

    def __init__(self, states: dict[str, str], links: dict[str, str]) -> None:
        self._states = states
        self._links = links
        self.etablissement_calls: list[list[str]] = []
        self.succession_calls: list[list[str]] = []

    def fetch_establishments_by_sirets(self, sirets):
        requested = sorted(str(s) for s in sirets)
        self.etablissement_calls.append(requested)
        rows = [
            {"siret": siret, "etatAdministratifEtablissement": self._states[siret]}
            for siret in requested
            if siret in self._states
        ]
        columns = ["siret", "etatAdministratifEtablissement"]
        return pd.DataFrame(rows, columns=columns), {}, columns

    def fetch_succession_links(self, sirets):
        requested = sorted(str(s) for s in sirets)
        self.succession_calls.append(requested)
        rows = [
            (siret, self._links[siret]) for siret in requested if siret in self._links
        ]
        return _links(rows), {}, ["siret_predecessor", "siret_successor"]


class TestExpandSuccessionChain:
    def test_loads_deeper_levels_for_closed_successors(self):
        service = _FakeQueryService(
            states={SIRET_A: "F", SIRET_B: "F", SIRET_C: "A"},
            links={SIRET_B: SIRET_C},
        )
        chain_map, statuses = _expand_succession_chain(
            service=service,
            succession_links=_links([(SIRET_A, SIRET_B)]),
            status_by_siret={SIRET_A: "F"},
        )
        assert chain_map == {SIRET_A: SIRET_B, SIRET_B: SIRET_C}
        assert statuses[SIRET_B] == "F"
        assert statuses[SIRET_C] == "A"
        assert service.succession_calls == [[SIRET_B]]

    def test_active_successor_stops_the_expansion(self):
        service = _FakeQueryService(
            states={SIRET_B: "A"},
            links={SIRET_B: SIRET_C},
        )
        chain_map, statuses = _expand_succession_chain(
            service=service,
            succession_links=_links([(SIRET_A, SIRET_B)]),
            status_by_siret={},
        )
        assert chain_map == {SIRET_A: SIRET_B}
        assert statuses[SIRET_B] == "A"
        assert service.succession_calls == []

    def test_unknown_successor_is_recorded_to_bound_the_loop(self):
        service = _FakeQueryService(states={}, links={})
        chain_map, statuses = _expand_succession_chain(
            service=service,
            succession_links=_links([(SIRET_A, SIRET_B)]),
            status_by_siret={},
        )
        assert chain_map == {SIRET_A: SIRET_B}
        assert statuses[SIRET_B] == ""
        assert len(service.etablissement_calls) == 1

    def test_cycle_terminates(self):
        service = _FakeQueryService(
            states={SIRET_A: "F", SIRET_B: "F"},
            links={SIRET_A: SIRET_B, SIRET_B: SIRET_A},
        )
        chain_map, _ = _expand_succession_chain(
            service=service,
            succession_links=_links([(SIRET_A, SIRET_B)]),
            status_by_siret={SIRET_A: "F"},
        )
        assert chain_map == {SIRET_A: SIRET_B, SIRET_B: SIRET_A}

    def test_no_links_means_no_query(self):
        service = _FakeQueryService(states={}, links={})
        chain_map, statuses = _expand_succession_chain(
            service=service,
            succession_links=None,
            status_by_siret={SIRET_A: "F"},
        )
        assert chain_map == {}
        assert statuses == {SIRET_A: "F"}
        assert service.etablissement_calls == []


def _controle_frame(siret: str, siren: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "siret_input": siret,
                "siret_normalized": siret,
                "siret_lookup_key": siret,
                "siret_status": SIRET_STATUS_CLOSED,
                "siret_format_ok": True,
                "siret": siret,
                "siren": siren,
                "etatAdministratifEtablissement": "F",
            }
        ]
    )


class TestBuildSiretOverviewReplacement:
    def test_cascade_recommends_the_first_active_successor(self):
        overview = _build_siret_overview(
            controle_siret=_controle_frame(SIRET_A, SIRET_A[:9]),
            input_columns=[],
            siret_source_column="siret_input",
            all_etablissements=pd.DataFrame(),
            succession_map={SIRET_A: SIRET_B, SIRET_B: SIRET_C},
            succession_status_by_siret={SIRET_B: "F", SIRET_C: "A"},
        )
        row = overview.iloc[0]
        assert row["siret_remplacement_recommande"] == SIRET_C
        assert row["analysis_synthese_remplacement"] == "Succession"
        assert row["siret_retenu"] == SIRET_C

    def test_dead_end_chain_falls_back_to_active_sibling(self):
        siren = SIRET_A[:9]
        sibling = f"{siren}00099"
        all_etablissements = pd.DataFrame(
            [
                {
                    "siret": sibling,
                    "siren": siren,
                    "etatAdministratifEtablissement": "A",
                    "etablissementSiege": True,
                    "dateDebut": "2020-01-01",
                    "dateCreationEtablissement": "2019-01-01",
                }
            ]
        )
        overview = _build_siret_overview(
            controle_siret=_controle_frame(SIRET_A, siren),
            input_columns=[],
            siret_source_column="siret_input",
            all_etablissements=all_etablissements,
            succession_map={SIRET_A: SIRET_B},
            succession_status_by_siret={SIRET_B: "F"},
        )
        row = overview.iloc[0]
        assert row["siret_remplacement_recommande"] == sibling
        assert row["analysis_synthese_remplacement"] == "Autre SIRET même SIREN"
        assert row["analysis_succession_disponible"] == "Non"

    def test_replacement_on_another_siren_is_flagged(self):
        # SIRET_B releve d'un autre SIREN : lien legitime dans SIRENE (cession
        # d'etablissement) mais changement d'entite juridique, donc signale.
        overview = _build_siret_overview(
            controle_siret=_controle_frame(SIRET_A, SIRET_A[:9]),
            input_columns=[],
            siret_source_column="siret_input",
            all_etablissements=pd.DataFrame(),
            succession_map={SIRET_A: SIRET_B},
            succession_status_by_siret={SIRET_B: "A"},
        )
        row = overview.iloc[0]
        assert row["siret_remplacement_recommande"] == SIRET_B
        assert row["analysis_alerte_siren_different"] == "Oui"
        assert "autre SIREN" in row["analysis_status_note"]
        # Le remplacant reste recommande : l'alerte informe, elle n'ecarte pas le lien.
        assert row["siret_retenu"] == SIRET_B

    def test_replacement_on_same_siren_is_not_flagged(self):
        siren = SIRET_A[:9]
        successor = f"{siren}00099"
        overview = _build_siret_overview(
            controle_siret=_controle_frame(SIRET_A, siren),
            input_columns=[],
            siret_source_column="siret_input",
            all_etablissements=pd.DataFrame(),
            succession_map={SIRET_A: successor},
            succession_status_by_siret={successor: "A"},
        )
        row = overview.iloc[0]
        assert row["analysis_alerte_siren_different"] == "Non"
        assert "autre SIREN" not in row["analysis_status_note"]

    def test_alert_is_empty_without_replacement(self):
        overview = _build_siret_overview(
            controle_siret=_controle_frame(SIRET_A, SIRET_A[:9]),
            input_columns=[],
            siret_source_column="siret_input",
            all_etablissements=pd.DataFrame(),
            succession_map={},
            succession_status_by_siret={},
        )
        assert overview.iloc[0]["analysis_alerte_siren_different"] == ""

    def test_alert_holds_when_replacement_data_is_not_loaded(self):
        # NO_DATA_REPLACEMENT_NOT_LOADED : donnee du remplacant absente du lot charge.
        # L'alerte se calcule sur les 9 premiers chiffres, donc reste disponible.
        overview = _build_siret_overview(
            controle_siret=_controle_frame(SIRET_A, SIRET_A[:9]),
            input_columns=[],
            siret_source_column="siret_input",
            all_etablissements=pd.DataFrame(),
            succession_map={SIRET_A: SIRET_B},
            succession_status_by_siret={SIRET_B: "A"},
        )
        row = overview.iloc[0]
        assert row["analysis_data_applied"] == "NO_DATA_REPLACEMENT_NOT_LOADED"
        assert row["analysis_alerte_siren_different"] == "Oui"
        assert row["siret_remplacement_recommande"] == SIRET_B

    def test_active_siret_keeps_no_replacement(self):
        controle = _controle_frame(SIRET_A, SIRET_A[:9])
        controle["siret_status"] = SIRET_STATUS_ACTIVE
        controle["etatAdministratifEtablissement"] = "A"
        overview = _build_siret_overview(
            controle_siret=controle,
            input_columns=[],
            siret_source_column="siret_input",
            all_etablissements=pd.DataFrame(),
            succession_map={SIRET_A: SIRET_B},
            succession_status_by_siret={SIRET_B: "A"},
        )
        assert overview.iloc[0]["siret_remplacement_recommande"] == ""
