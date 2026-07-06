from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CatalogModel:
    id: str
    label: str
    family: str
    quantization: str
    file_path: str
    runtime: str
    recommended_endpoint: str
    notes: str
    temperature: float | None = None
    top_k: int | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    timeout_seconds: int | None = None
    system_prompt_override: str | None = None


@dataclass(slots=True)
class ModelCatalog:
    role: str
    models: list[CatalogModel]


def load_catalog(path: Path) -> ModelCatalog:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ModelCatalog(
        role=payload["role"],
        models=[CatalogModel(**item) for item in payload["models"]],
    )


def format_catalog(catalog: ModelCatalog) -> str:
    lines = [f"Role: {catalog.role}", ""]
    for model in catalog.models:
        lines.extend(
            [
                f"- ID: {model.id}",
                f"  Label: {model.label}",
                f"  Family: {model.family}",
                f"  Quantization: {model.quantization}",
                f"  File: {model.file_path}",
                f"  Runtime: {model.runtime}",
                f"  Endpoint: {model.recommended_endpoint}",
                f"  Notes: {model.notes}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
