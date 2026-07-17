from __future__ import annotations

from src.core.exceptions import DataProviderError


def format_validation_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if isinstance(exc, DataProviderError):
        if "no ohlcv" in lowered or "no bars in range" in lowered:
            return (
                "No market data for the selected date range. "
                "Try a different start/end date or switch to Sample CSV."
            )
        if "unsupported exchange" in lowered or "does not have market symbol" in lowered:
            return f"Symbol or exchange not supported: {message}"
        if "failed to download" in lowered or "failed to fetch" in lowered:
            if "read-only file system" in lowered or "errno 30" in lowered:
                return (
                    "Could not save downloaded data to the server cache. "
                    "If using Docker, ensure ./data is mounted read-write."
                )
            return (
                "Could not download historical data from the exchange. "
                "Check your internet connection and try again."
            )
        return message
    if isinstance(exc, FileNotFoundError):
        return "Sample CSV fixture not found on the server."
    if isinstance(exc, ValueError) and "no bars in range" in lowered:
        return (
            "No bars in the selected date range. "
            "Adjust start/end dates or use Sample CSV for the bundled fixture."
        )
    return message
