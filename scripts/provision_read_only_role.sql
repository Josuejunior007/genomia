-- Provisiona a role de runtime para leitura. Este arquivo é SQL padrão,
-- compatível com o SQL Editor do Supabase, DataGrip e outros clientes gráficos.
-- Não coloque senha neste arquivo. Crie/defina a senha pelo painel Supabase
-- Database > Roles antes de configurar DATABASE_URL.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'genomia_reader_app') THEN
        CREATE ROLE genomia_reader_app LOGIN NOINHERIT;
    END IF;
END
$$;

-- Supabase normalmente conecta ao banco "postgres". Se o banco alvo tiver outro
-- nome, substitua postgres pelo nome literal antes de executar.
GRANT CONNECT ON DATABASE postgres TO genomia_reader_app;

-- Mantenha este schema igual a DB_SCHEMA no .env.
GRANT USAGE ON SCHEMA public TO genomia_reader_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO genomia_reader_app;

-- Execute também como CADA role que cria tabelas em public, para que novos
-- objetos recebam SELECT automaticamente (privilégios padrão são por owner).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO genomia_reader_app;

-- Remove privilégios diretos de escrita nessa role nas tabelas existentes.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public FROM genomia_reader_app;
REVOKE CREATE ON SCHEMA public FROM genomia_reader_app;

-- A role não pode ter memberships adicionais. Confira:
-- SELECT pg_get_userbyid(roleid) AS granted_role
-- FROM pg_auth_members
-- WHERE member = 'genomia_reader_app'::regrole;

-- Depois de aplicar, rode: python -m scripts.check_read_only
