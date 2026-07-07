from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.governance import ConfigRevision
from src.core.settings import resolve_config_dir
from src.db.models import ConfigRevisionRow
from src.execution.config import load_default_fill_model
from src.providers.registry import discover_provider_configs


def _file_hash(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _providers_hash(config_dir: Path) -> str:
    parts: list[str] = []
    for cfg in sorted(discover_provider_configs(config_dir), key=lambda c: c.provider_id):
        path = config_dir / "providers" / f"{cfg.provider_id}.yaml"
        parts.append(f"{cfg.provider_id}:{_file_hash(path)}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def compute_config_revision(
    config_dir: Path | None = None,
    *,
    label: str = "auto",
    parent_revision_id: str | None = None,
) -> ConfigRevision:
    base = config_dir or resolve_config_dir()
    engine_raw = _load_yaml(base / "engine.yaml")
    features_raw = _load_yaml(base / "features.yaml")
    engine_hash = _file_hash(base / "engine.yaml")
    features_hash = _file_hash(base / "features.yaml")
    providers_hash = _providers_hash(base)
    risk_section = engine_raw.get("engine", {}).get("risk", engine_raw.get("risk", {}))
    risk_hash = hashlib.sha256(yaml.safe_dump(risk_section).encode()).hexdigest()
    fill_model = load_default_fill_model(base)
    combined = f"{engine_hash}:{features_hash}:{providers_hash}:{risk_hash}:{fill_model.model_id}"
    revision_id = f"rev_{hashlib.sha256(combined.encode()).hexdigest()[:16]}"
    provider_bundle = {
        cfg.provider_id: _load_yaml(base / "providers" / f"{cfg.provider_id}.yaml")
        for cfg in discover_provider_configs(base)
    }
    return ConfigRevision(
        revision_id=revision_id,
        created_at=datetime.now(UTC),
        engine_config_hash=engine_hash,
        features_config_hash=features_hash,
        providers_config_hash=providers_hash,
        fill_model_id=fill_model.model_id,
        risk_limits_hash=risk_hash,
        label=label,
        parent_revision_id=parent_revision_id,
        config_bundle={
            "engine": engine_raw,
            "features": features_raw,
            "providers": provider_bundle,
        },
    )


def _row_to_revision(row: ConfigRevisionRow) -> ConfigRevision:
    return ConfigRevision(
        revision_id=row.revision_id,
        created_at=row.created_at,
        engine_config_hash=row.engine_config_hash,
        features_config_hash=row.features_config_hash,
        providers_config_hash=row.providers_config_hash,
        fill_model_id=row.fill_model_id,
        risk_limits_hash=row.risk_limits_hash,
        label=row.label,
        parent_revision_id=row.parent_revision_id,
        config_bundle=row.config_bundle,
    )


async def save_revision(session: AsyncSession, revision: ConfigRevision) -> ConfigRevision:
    existing = await session.get(ConfigRevisionRow, revision.revision_id)
    if existing is not None:
        return _row_to_revision(existing)
    row = ConfigRevisionRow(
        revision_id=revision.revision_id,
        created_at=revision.created_at,
        engine_config_hash=revision.engine_config_hash,
        features_config_hash=revision.features_config_hash,
        providers_config_hash=revision.providers_config_hash,
        fill_model_id=revision.fill_model_id,
        risk_limits_hash=revision.risk_limits_hash,
        label=revision.label,
        parent_revision_id=revision.parent_revision_id,
        config_bundle=revision.config_bundle,
    )
    session.add(row)
    await session.flush()
    return revision


async def get_revision(session: AsyncSession, revision_id: str) -> ConfigRevision | None:
    row = await session.get(ConfigRevisionRow, revision_id)
    if row is None:
        return None
    return _row_to_revision(row)


async def list_revisions(session: AsyncSession, *, limit: int = 50) -> list[ConfigRevision]:
    stmt = select(ConfigRevisionRow).order_by(ConfigRevisionRow.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_revision(row) for row in rows]


async def ensure_current_revision(
    session: AsyncSession,
    *,
    label: str = "auto",
) -> ConfigRevision:
    revision = compute_config_revision(label=label)
    return await save_revision(session, revision)
