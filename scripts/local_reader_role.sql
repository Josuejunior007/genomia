-- Role de leitura para o ambiente local do docker-compose.
-- NUNCA use estas senhas em produção; troque-as e use secret manager.
\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'genomia_reader') THEN
        CREATE ROLE genomia_reader LOGIN PASSWORD 'change_me_reader';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE ai_manager TO genomia_reader;
GRANT USAGE ON SCHEMA public TO genomia_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO genomia_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO genomia_reader;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public FROM genomia_reader;
REVOKE CREATE ON SCHEMA public FROM genomia_reader;
