-- =====================================================================
-- GenomAI — armazenamento interno em PostgreSQL
--
-- Execute este script com uma role administrativa no banco do GenomAI
-- (por exemplo, no SQL Editor do Supabase), ANTES de apontar
-- APP_DATABASE_URL para esse banco.
--
-- O schema "genomai_app" é deliberadamente separado do schema analisado
-- ("public"). A IA nunca lê estas tabelas.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS genomai_app;

COMMENT ON SCHEMA genomai_app IS
    'Armazenamento interno do GenomAI: sugestões, revisões e auditoria. Nunca é analisado pela IA.';

CREATE TABLE IF NOT EXISTS genomai_app.suggestions (
    id              SERIAL PRIMARY KEY,
    table_name      VARCHAR(255) NOT NULL,
    kind            VARCHAR(40)  NOT NULL,
    column_name     VARCHAR(255),
    description     TEXT         NOT NULL,
    confidence      DOUBLE PRECISION NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    rationale       TEXT         NOT NULL,
    suggested_sql   TEXT,
    version         INTEGER      NOT NULL DEFAULT 1,
    previous_status VARCHAR(20),
    review_comment  VARCHAR(1000) NOT NULL DEFAULT '',
    reviewed_by     VARCHAR(80),
    edited_by       VARCHAR(80),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ,
    reviewed_at     TIMESTAMPTZ,
    applied_at      TIMESTAMPTZ,
    applied_by      VARCHAR(80),
    apply_error     TEXT
);

CREATE INDEX IF NOT EXISTS ix_suggestions_table_name ON genomai_app.suggestions (table_name);
CREATE INDEX IF NOT EXISTS ix_suggestions_kind       ON genomai_app.suggestions (kind);
CREATE INDEX IF NOT EXISTS ix_suggestions_status     ON genomai_app.suggestions (status);

COMMENT ON TABLE genomai_app.suggestions IS
    'Propostas de melhoria. Somente leitura pela IA; decisão e aplicação são humanas.';

CREATE TABLE IF NOT EXISTS genomai_app.suggestion_revisions (
    id            SERIAL PRIMARY KEY,
    suggestion_id INTEGER      NOT NULL,
    version       INTEGER      NOT NULL,
    table_name    VARCHAR(255) NOT NULL,
    kind          VARCHAR(40)  NOT NULL,
    column_name   VARCHAR(255),
    description   TEXT         NOT NULL,
    confidence    DOUBLE PRECISION NOT NULL,
    status        VARCHAR(20)  NOT NULL,
    rationale     TEXT         NOT NULL,
    suggested_sql TEXT,
    edited_by     VARCHAR(80)  NOT NULL,
    comment       VARCHAR(1000) NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_suggestion_revisions_suggestion_id
    ON genomai_app.suggestion_revisions (suggestion_id);

CREATE TABLE IF NOT EXISTS genomai_app.apply_logs (
    id            SERIAL PRIMARY KEY,
    suggestion_id INTEGER,
    persona       VARCHAR(40) NOT NULL,
    action        VARCHAR(40) NOT NULL,
    sql_text      TEXT        NOT NULL,
    success       BOOLEAN     NOT NULL DEFAULT FALSE,
    error         TEXT,
    duration_ms   INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_apply_logs_suggestion_id
    ON genomai_app.apply_logs (suggestion_id);

CREATE TABLE IF NOT EXISTS genomai_app.ai_metadata_audits (
    id                         SERIAL PRIMARY KEY,
    provider                   VARCHAR(40)  NOT NULL DEFAULT 'groq',
    model                      VARCHAR(120) NOT NULL,
    payload_sha256             VARCHAR(64)  NOT NULL,
    tables_count               INTEGER      NOT NULL DEFAULT 0,
    columns_count              INTEGER      NOT NULL DEFAULT 0,
    sensitive_columns_count    INTEGER      NOT NULL DEFAULT 0,
    redacted_identifiers_count INTEGER      NOT NULL DEFAULT 0,
    removed_fields_count       INTEGER      NOT NULL DEFAULT 0,
    excluded_tables            TEXT         NOT NULL DEFAULT '[]',
    triggered_by               VARCHAR(80)  NOT NULL DEFAULT 'sistema',
    status                     VARCHAR(20)  NOT NULL DEFAULT 'success',
    created_at                 TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE genomai_app.ai_metadata_audits IS
    'Hash e contagens do payload enviado à IA. O conteúdo do payload não é armazenado.';

-- A role de runtime (criada por provision_app_store_role.sql) precisa destes
-- privilégios. Repita os GRANTs se criar novas tabelas no futuro.
-- GRANT USAGE ON SCHEMA genomai_app TO genomia_app_writer;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA genomai_app TO genomia_app_writer;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA genomai_app TO genomia_app_writer;
