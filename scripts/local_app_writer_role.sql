-- Role de escrita do armazenamento interno para o docker-compose local.
-- NUNCA use estas senhas em produção; troque-as e use secret manager.
\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'genomia_app_writer') THEN
        CREATE ROLE genomia_app_writer LOGIN PASSWORD 'change_me_writer';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE ai_manager TO genomia_app_writer;
GRANT USAGE ON SCHEMA genomai_app TO genomia_app_writer;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA genomai_app TO genomia_app_writer;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA genomai_app TO genomia_app_writer;

ALTER DEFAULT PRIVILEGES IN SCHEMA genomai_app
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO genomia_app_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA genomai_app
    GRANT USAGE, SELECT ON SEQUENCES TO genomia_app_writer;

-- A role interna não deve enxergar o schema analisado.
REVOKE ALL ON SCHEMA public FROM genomia_app_writer;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM genomia_app_writer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM genomia_app_writer;
