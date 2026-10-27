-- Provisiona a role de runtime genomia_reader com acesso de leitura.
-- Execute conectado ao banco alvo, como owner/admin. Não coloque senha neste arquivo.
-- Após criar a role, psql pedirá a senha com entrada oculta (password).
\set ON_ERROR_STOP on

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

-- Ajuste public para o schema realmente lido pelo backend antes de executar.
GRANT CONNECT ON DATABASE postgres TO genomia_reader;
GRANT USAGE ON SCHEMA public TO genomia_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO genomia_reader;

-- information_schema é fornecido pelo PostgreSQL; a introspeção revela apenas
-- objetos que a role já pode acessar. Conceder USAGE/SELECT permite consultar
-- os metadados expostos pelo servidor sem habilitar escrita.
GRANT USAGE ON SCHEMA information_schema TO genomia_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA information_schema TO genomia_reader;

-- Execute este comando como CADA role que cria tabelas no schema alvo,
-- para que tabelas futuras também recebam SELECT.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO genomia_reader;

-- Remove privilégios de escrita diretos em objetos existentes no schema alvo.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public FROM genomia_reader;
REVOKE CREATE ON SCHEMA public FROM genomia_reader;

-- A role de runtime não deve pertencer a roles adicionais. Confira e remova
-- qualquer membership preexistente antes de usar:
-- SELECT pg_get_userbyid(roleid) AS granted_role
-- FROM pg_auth_members WHERE member = 'genomia_reader'::regrole;
