-- =====================================================================
-- GenomAI — provisionamento da role de escrita do armazenamento interno
--
-- Execute como owner/admin, conectado ao banco do GenomAI. O script pede
-- a senha de forma oculta e não grava credenciais no repositório.
--
-- No SQL Editor web do Supabase, o meta-comando \password não é suportado.
-- Nesse caso, crie a role pelo painel Database > Roles (com senha) e execute
-- apenas os GRANT/ALTER abaixo. Nunca commite a senha.
--
-- IMPORTANTE: esta role NÃO deve ter acesso ao schema analisado. Ela serve
-- apenas para o schema genomai_app.
-- =====================================================================

\set ON_ERROR_STOP on
\set app_schema genomai_app
SELECT current_database() AS target_database \gset

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'genomia_app_writer') THEN
        CREATE ROLE genomia_app_writer LOGIN;
    END IF;
END
$$;

-- A role nasce com os defaults seguros (NOSUPERUSER, NOCREATEDB,
-- NOCREATEROLE, NOREPLICATION, NOBYPASSRLS). Não altere esses atributos:
-- o SQL Editor do Supabase pode não ser SUPERUSER, e apenas um superuser
-- pode mudar o atributo SUPERUSER.
ALTER ROLE genomia_app_writer
    LOGIN NOINHERIT;

\password genomia_app_writer

GRANT CONNECT ON DATABASE :"target_database" TO genomia_app_writer;
REVOKE CREATE ON DATABASE :"target_database" FROM genomia_app_writer;

GRANT USAGE ON SCHEMA :"app_schema" TO genomia_app_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA :"app_schema"
    TO genomia_app_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA :"app_schema"
    TO genomia_app_writer;

-- Tabelas futuras criadas pelo owner que executa este script.
ALTER DEFAULT PRIVILEGES IN SCHEMA :"app_schema"
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO genomia_app_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA :"app_schema"
    GRANT USAGE, SELECT ON SEQUENCES TO genomia_app_writer;

-- Garante que a role não consiga criar objetos no schema analisado.
REVOKE ALL ON SCHEMA public FROM genomia_app_writer;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM genomia_app_writer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM genomia_app_writer;

-- Confira memberships:
-- SELECT pg_get_userbyid(roleid) AS granted_role
-- FROM pg_auth_members WHERE member = 'genomia_app_writer'::regrole;
