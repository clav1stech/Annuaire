"""Utilities for SIRET/SIREN normalization and validation."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .config import (
    SIRET_STATUS_ACTIVE,
    SIRET_STATUS_CLOSED,
    SIRET_STATUS_FOUND_UNKNOWN,
)


def normalize_digits(value: Any) -> str:
    """Keep only digits from any input value."""
    if value is None:
        return ""
    return re.sub(r"\D+", "", str(value))


def normalize_identifier_for_lookup(value: Any, *, max_digits: int = 14) -> str:
    """Normalize an input identifier to the lookup key used by the pipeline."""
    digits = normalize_digits(value)
    if not digits:
        return ""
    if len(digits) > max_digits:
        return digits[:max_digits]
    return digits


def _resolve_lookup_identifier(digits: str) -> tuple[str, str, str, bool, bool]:
    """
    Resolve the identifier used for lookup and its validation route.

    Rules:
    1) Try SIRET on 14-digit key (left truncation if input longer than 14).
    2) If SIRET check fails, try SIREN on first 9 digits.
    """
    if not digits:
        return "", "", "INVALID", False, False

    siret_candidate = digits[:14]
    siret_ok = len(siret_candidate) == 14 and is_luhn_valid(siret_candidate)
    if siret_ok:
        return siret_candidate, "SIRET", "SIRET_OK", True, True

    siren_candidate = digits[:9]
    siren_ok = len(siren_candidate) == 9 and is_luhn_valid(siren_candidate)
    if siren_ok:
        route = "SIREN_DIRECT" if len(digits) == 9 else "SIREN_FALLBACK_FROM_SIRET"
        return siren_candidate, "SIREN", route, True, True

    return normalize_identifier_for_lookup(digits), "", "INVALID", False, False


def is_luhn_valid(number: str) -> bool:
    """Validate a numeric string with the Luhn algorithm."""
    if not number.isdigit():
        return False
    # Reject obvious placeholder identifiers (all zeros).
    if set(number) == {"0"}:
        return False
    checksum = 0
    reverse_digits = number[::-1]
    for idx, char in enumerate(reverse_digits):
        digit = int(char)
        if idx % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def build_siret_validation_frame(siret_series: pd.Series) -> pd.DataFrame:
    """Create validation columns for SIRET/SIREN controls."""
    siret_input = siret_series.fillna("").astype(str)
    raw_digits = siret_input.map(normalize_digits)
    normalized_input = raw_digits.map(normalize_identifier_for_lookup)
    resolved = raw_digits.map(_resolve_lookup_identifier)
    resolved_df = pd.DataFrame(
        resolved.tolist(),
        index=siret_input.index,
        columns=[
            "siret_lookup_key",
            "siret_input_type",
            "siret_validation_route",
            "siret_len_ok",
            "siret_luhn_ok",
        ],
    )
    format_ok = resolved_df["siret_input_type"].ne("")
    return pd.DataFrame(
        {
            "siret_input": siret_input,
            "siret_normalized": normalized_input,
            "siret_lookup_key": resolved_df["siret_lookup_key"],
            "siret_input_type": resolved_df["siret_input_type"],
            "siret_validation_route": resolved_df["siret_validation_route"],
            "siret_len_ok": resolved_df["siret_len_ok"],
            "siret_luhn_ok": resolved_df["siret_luhn_ok"],
            "siret_format_ok": format_ok,
        }
    )


def classify_etablissement_status(etat_admin: Any) -> str:
    """Map etatAdministratifEtablissement to a business status."""
    value = str(etat_admin or "").strip().upper()
    if value == "A":
        return SIRET_STATUS_ACTIVE
    if value == "F":
        return SIRET_STATUS_CLOSED
    return SIRET_STATUS_FOUND_UNKNOWN


def first_non_empty(values: list[Any]) -> str:
    """Return the first meaningful value in a list."""
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def build_address(row: pd.Series, fields: list[str]) -> str:
    """Build a one-line address from available components."""
    tokens: list[str] = []
    for field in fields:
        if field not in row:
            continue
        value = str(row.get(field, "") or "").strip()
        if value and value.lower() != "nan":
            tokens.append(value)
    return " ".join(tokens)
