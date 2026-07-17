from __future__ import annotations

# Register route modules for side-effect decorators.
from src.api.v1.validation_routes import history as _history  # noqa: F401
from src.api.v1.validation_routes import jobs as _jobs  # noqa: F401
from src.api.v1.validation_routes.router import router

__all__ = ["router"]
