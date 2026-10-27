-- GenomAI: usuário PostgreSQL estritamente de leitura para o schema public.
-- Execute no SQL Editor do Supabase como administrador.
-- ANTES DE EXECUTAR: substitua CHANGE_ME por uma senha forte e exclusiva.
-- Não versione nem compartilhe a versão preenchida com a senha.
--
-- Este script não altera permissões de outros usuários nem desabilita RLS.
-- Se a aplicação precisar analisar outro schema, replique os GRANTs para ele.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'genomai_readonly') THEN
        CREATE ROLE genomai_readonly;
    END IF;
END
$$;

ALTER ROLE genomai_readonly
    WITH LOGIN
    PASSWORD 'CHANGE_ME_USE_A_LONG_RANDOM_PASSWORD'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;

-- Remova permissões explícitas anteriores desse usuário e conceda apenas leitura.
REVOKE ALL PRIVILEGES ON SCHEMA public FROM genomai_readonly;
GRANT USAGE ON SCHEMA public TO genomai_readonly;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM genomai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO genomai_readonly;

REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM genomai_readonly;

-- Novas tabelas criadas pelo papel postgres também serão legíveis.
-- Se migrations/tabelas forem criadas por outro papel, repita este comando
-- para cada papel criador, substituindo postgres pelo nome desse papel.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT ON TABLES TO genomai_readonly;

-- Verificação das permissões no schema e nas tabelas existentes.
-- Todas as colunas *_any_write devem ser false.
SELECT
    has_schema_privilege('genomai_readonly', 'public', 'USAGE') AS can_use_schema,
    has_schema_privilege('genomai_readonly', 'public', 'CREATE') AS can_create_in_schema,
    COALESCE(bool_or(has_table_privilege('genomai_readonly', format('%I.%I', schemaname, tablename), 'SELECT')), false) AS can_select_any_table,
    COALESCE(bool_or(has_table_privilege('genomai_readonly', format('%I.%I', schemaname, tablename), 'INSERT')), false) AS can_insert_any_table,
    COALESCE(bool_or(has_table_privilege('genomai_readonly', format('%I.%I', schemaname, tablename), 'UPDATE')), false) AS can_update_any_table,
    COALESCE(bool_or(has_table_privilege('genomai_readonly', format('%I.%I', schemaname, tablename), 'DELETE')), false) AS can_delete_any_table
FROM pg_tables
WHERE schemaname = 'public';
