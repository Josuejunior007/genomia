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

-- Verificação rápida: estas consultas devem retornar false para as permissões
-- de escrita e true para SELECT em tabelas às quais o usuário tem acesso.
SELECT
    has_schema_privilege('genomai_readonly', 'public', 'USAGE') AS can_use_schema,
    has_schema_privilege('genomai_readonly', 'public', 'CREATE') AS can_create_in_schema,
    has_table_privilege('genomai_readonly', 'public.alguma_tabela', 'SELECT') AS can_select_example,
    has_table_privilege('genomai_readonly', 'public.alguma_tabela', 'INSERT') AS can_insert_example,
    has_table_privilege('genomai_readonly', 'public.alguma_tabela', 'UPDATE') AS can_update_example,
    has_table_privilege('genomai_readonly', 'public.alguma_tabela', 'DELETE') AS can_delete_example;
-- Troque public.alguma_tabela por uma tabela real antes de executar a verificação.
