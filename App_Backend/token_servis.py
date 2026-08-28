"""KVKK helpers for the local patient-summary workflow."""

from __future__ import annotations

import hashlib
import secrets


def anonim_token_uret() -> str:
    """Return a short, random queue token for kiosk receipts."""
    return secrets.token_hex(4)


def tc_maskele_ve_hashle(tc_kimlik: str) -> str:
    """Return a one-way SHA-256 digest for local diagnostics only."""
    return hashlib.sha256(str(tc_kimlik).strip().encode("utf-8")).hexdigest()


def klinik_rapor_maskele(ad: str, soyad: str) -> str:
    """Return a KVKK-safe display name, such as A**** K*****."""
    first_name = str(ad).strip()
    last_name = str(soyad).strip()
    masked_first = first_name[:1] + "*" * max(4, len(first_name) - 1) if first_name else ""
    masked_last = last_name[:1] + "*" * max(4, len(last_name) - 1) if last_name else ""
    return f"{masked_first} {masked_last}".strip()
