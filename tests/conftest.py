"""Configuração de testes.

Os testes precisam ser independentes do `.env` de desenvolvimento. Sem isso, ao
apontar a aplicação para o PostgreSQL real, os testes que criam um banco SQLite
em memória quebrariam por causa do schema `genomai_app`.

As variáveis abaixo são definidas antes de qualquer import de `app`, e têm
precedência sobre o `.env` no pydantic-settings.
"""

import os

os.environ["APP_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_DB_SCHEMA"] = "genomai_app"
os.environ["APP_DB_AUTO_CREATE"] = "true"
os.environ["APP_STORE_REQUIRE_REMOTE"] = "false"
