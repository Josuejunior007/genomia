"""Configuração central da aplicação.

O GenomAI usa **três conexões conceitualmente separadas**:

``DATABASE_URL``
    Banco analisado (PostgreSQL/Supabase). Deve usar uma role *somente leitura*.
``APP_DATABASE_URL``
    Banco interno do GenomAI, onde ficam sugestões, revisões e auditorias.
    É isolado do banco analisado e nunca é enviado à IA.
``WRITE_DATABASE_URL``
    Conexão opcional, com role de escrita, usada **somente** para aplicar uma
    mudança já aprovada por uma persona autorizada. Fica desativada por padrão.

Todos os nomes de variáveis podem ser definidos no ``.env`` ou no secret
manager do deploy. Nenhuma credencial deve ser versionada.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações tipadas, carregadas de variáveis de ambiente e do ``.env``."""

    app_name: str = "GenomAI API"
    app_env: str = "development"

    # --- Banco analisado (read-only) -------------------------------------
    database_url: str
    db_schema: str = "public"
    db_read_only: bool = True

    # --- Armazenamento interno do GenomAI (sugestões/auditoria) ----------
    # Em produção use um PostgreSQL dedicado. O schema abaixo isola as tabelas
    # internas do schema analisado. Em SQLite o schema é ignorado.
    app_database_url: str = "sqlite:///./genomai_app.db"
    app_db_schema: str = "genomai_app"
    # Cria schema/tabelas automaticamente no startup (bom para dev).
    app_db_auto_create: bool = True
    # Em produção, defina true para recusar SQLite (armazenamento local).
    app_store_require_remote: bool = False

    # Tabelas que nunca devem ser analisadas nem enviadas à IA. Isso protege
    # contra o cenário em que o banco de armazenamento do app está no mesmo
    # schema do banco analisado (foi exatamente o que aconteceu com a tabela
    # legada "suggestions" no Supabase).
    analysis_excluded_tables: list[str] = [
        "suggestions",
        "suggestion_revisions",
        "apply_logs",
        "ai_metadata_audits",
    ]

    # --- Aplicação controlada de mudanças no banco analisado -------------
    write_database_url: str | None = None
    db_write_enabled: bool = False
    # Persona usada quando o cabeçalho X-GenomAI-Persona não é enviado.
    # "leitor" é o padrão seguro; o frontend escolhe explicitamente uma persona.
    default_persona: str = "leitor"

    # --- IA / privacidade ------------------------------------------------
    ai_enabled: bool = False
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    # Se true, nomes de colunas sensíveis são pseudonimizados antes do envio.
    privacy_mask_sensitive_identifiers: bool = False
    # Se true, sequências de 6+ dígitos em identificadores são redigidas.
    privacy_redact_digit_runs: bool = True

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def app_store_is_sqlite(self) -> bool:
        """Indica se o armazenamento interno é um arquivo SQLite local."""
        return self.app_database_url.lower().startswith("sqlite")

    @property
    def app_store_schema(self) -> str | None:
        """Schema usado pelas tabelas internas (``None`` para SQLite)."""
        return None if self.app_store_is_sqlite else self.app_db_schema

    @property
    def analysis_exclusion_set(self) -> set[str]:
        """Nomes de tabela normalizados que nunca entram na análise."""
        return {name.strip().casefold() for name in self.analysis_excluded_tables if name.strip()}


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única de configuração (cacheada)."""
    return Settings()


settings = get_settings()
