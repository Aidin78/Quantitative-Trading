"""Compatibility shim — prefer ``src.validation.job_runner`` / ``src.validation.errors``."""

from __future__ import annotations

from src.validation.errors import format_validation_error
from src.validation.job_runner import new_validation_job_id, run_validation_job

__all__ = [
    "format_validation_error",
    "new_validation_job_id",
    "run_validation_job",
]
