"""Exporta o contrato OpenAPI para ``docs/openapi.json``.

Uso::

    python -m scripts.export_openapi

O arquivo é consumido por ferramentas e agentes de IA. Não contém credenciais.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> int:
    """Gera o JSON formatado e imprime o caminho."""
    destination = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"OpenAPI exportado para {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
