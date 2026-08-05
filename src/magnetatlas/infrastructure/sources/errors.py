"""User-facing transport errors shared by external source adapters."""

from __future__ import annotations

import requests


def transport_error_message(source: str, error: Exception) -> str:
    """Translate network failures into concise Swedish messages."""
    if isinstance(error, requests.Timeout):
        return f"{source} svarade inte inom tidsgränsen. Försök igen senare."
    if isinstance(error, requests.ConnectionError):
        return (
            f"{source} kunde inte nås. Kontrollera internetanslutningen och "
            "försök igen."
        )
    return f"{source} kunde inte nås. Försök igen senare."
