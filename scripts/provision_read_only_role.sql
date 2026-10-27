-- Provisiona a role de runtime genomia_reader com acesso de leitura.
-- Execute conectado ao banco alvo, como owner/admin. Nunca armazene senha aqui.
-- psql solicitará a senha com entrada oculta.
\set ON_ERROR_STOP on
\set target_schema public
SELECT current_database() AS target_database \gset

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'genomia_reader') THEN
        CREATE ROLE genomia_reader LOGIN;
    END IF;
END
$$;

ALTER ROLE genomia_reader
    LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;

\password genomia_reader

-- Para outro schema, altere target_schema acima e use o mesmo valor em DB_SCHEMA.
GRANT CONNECT ON DATABASE :"target_database" TO genomia_reader;
GRANT USAGE ON SCHEMA :"target_schema" TO genomia_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA :"target_schema" TO genomia_reader;

-- Execute como cada role que cria tabelas no schema para conceder SELECT
-- também sobre tabelas futuras.
ALTER DEFAULT PRIVILEGES IN SCHEMA :"target_schema"
    GRANT SELECT ON TABLES TO genomia_reader;

-- Remove privilégios diretos de escrita na role de runtime.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA :"target_schema" FROM genomia_reader;
REVOKE CREATE ON SCHEMA :"target_schema" FROM genomia_reader;

-- information_schema é fornecido pelo PostgreSQL; não altere suas permissões.
-- Sua visibilidade de metadados segue os objetos que a role pode acessar.
-- Confirme que a role não tem memberships adicionais:
-- SELECT pg_get_userbyid(roleid) AS granted_role
-- FROM pg_auth_members WHERE member = 'genomia_reader'::regrole;
