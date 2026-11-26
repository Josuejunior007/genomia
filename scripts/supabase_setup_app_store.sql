-- =====================================================================
-- GenomAI — configuração do armazenamento interno no Supabase
--
-- COMO USAR
-- 1. Abra o SQL Editor do Supabase como owner/admin.
-- 2. Troque TODAS as ocorrências de TROQUE_POR_UMA_SENHA_FORTE por uma
--    senha forte (letras, números e _; evite @ : / ? # para não precisar
--    codificar na URL).
-- 3. Cole o script inteiro e clique em Run.
-- 4. Guarde a senha no gerenciador de segredos / .env local.
--
-- O que este script faz:
--   - cria o schema genomai_app (separado do schema analisado public);
--   - cria as tabelas de sugestões, revisões, aplicação e auditoria de IA;
--   - cria a role genomia_app_writer, que só pode ler/escrever em genomai_app;
--   - NÃO altera nenhuma tabela do schema public.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Schema interno
-- ---------------------------------------------------------------------
create schema if not exists genomai_app;

comment on schema genomai_app is
    'Armazenamento interno do GenomAI: sugestões, revisões e auditoria. Nunca é analisado pela IA.';

-- ---------------------------------------------------------------------
-- 2) Tabelas
-- ---------------------------------------------------------------------
create table if not exists genomai_app.suggestions (
    id              serial primary key,
    table_name      varchar(255) not null,
    kind            varchar(40)  not null,
    column_name     varchar(255),
    description     text         not null,
    confidence      double precision not null,
    status          varchar(20)  not null default 'pending',
    rationale       text         not null,
    suggested_sql   text,
    version         integer      not null default 1,
    previous_status varchar(20),
    review_comment  varchar(1000) not null default '',
    reviewed_by     varchar(80),
    edited_by       varchar(80),
    created_at      timestamptz  not null default now(),
    updated_at      timestamptz,
    reviewed_at     timestamptz,
    applied_at      timestamptz,
    applied_by      varchar(80),
    apply_error     text
);

create index if not exists ix_suggestions_table_name on genomai_app.suggestions (table_name);
create index if not exists ix_suggestions_kind       on genomai_app.suggestions (kind);
create index if not exists ix_suggestions_status     on genomai_app.suggestions (status);

comment on table genomai_app.suggestions is
    'Propostas de melhoria. Somente leitura pela IA; decisão e aplicação são humanas.';

create table if not exists genomai_app.suggestion_revisions (
    id            serial primary key,
    suggestion_id integer      not null,
    version       integer      not null,
    table_name    varchar(255) not null,
    kind          varchar(40)  not null,
    column_name   varchar(255),
    description   text         not null,
    confidence    double precision not null,
    status        varchar(20)  not null,
    rationale     text         not null,
    suggested_sql text,
    edited_by     varchar(80)  not null,
    comment       varchar(1000) not null default '',
    created_at    timestamptz  not null default now()
);

create index if not exists ix_suggestion_revisions_suggestion_id
    on genomai_app.suggestion_revisions (suggestion_id);

create table if not exists genomai_app.apply_logs (
    id            serial primary key,
    suggestion_id integer,
    persona       varchar(40) not null,
    action        varchar(40) not null,
    sql_text      text        not null,
    success       boolean     not null default false,
    error         text,
    duration_ms   integer,
    created_at    timestamptz not null default now()
);

create index if not exists ix_apply_logs_suggestion_id
    on genomai_app.apply_logs (suggestion_id);

create table if not exists genomai_app.ai_metadata_audits (
    id                         serial primary key,
    provider                   varchar(40)  not null default 'groq',
    model                      varchar(120) not null,
    payload_sha256             varchar(64)  not null,
    tables_count               integer      not null default 0,
    columns_count              integer      not null default 0,
    sensitive_columns_count    integer      not null default 0,
    redacted_identifiers_count integer      not null default 0,
    removed_fields_count       integer      not null default 0,
    excluded_tables            text         not null default '[]',
    triggered_by               varchar(80)  not null default 'sistema',
    status                     varchar(20)  not null default 'success',
    created_at                 timestamptz  not null default now()
);

comment on table genomai_app.ai_metadata_audits is
    'Hash e contagens do payload enviado à IA. O conteúdo do payload não é armazenado.';

-- ---------------------------------------------------------------------
-- 3) Role de escrita do GenomAI
--    A senha abaixo é um placeholder: troque antes de executar.
--    Se a role já existir, o bloco não a recria; o ALTER ROLE abaixo
--    atualiza a senha para a que você escolher.
-- ---------------------------------------------------------------------
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'genomia_app_writer') then
        create role genomia_app_writer login;
    end if;
end
$$;

-- A role é criada com os defaults seguros do PostgreSQL (NOSUPERUSER,
-- NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS). NÃO tente alterar
-- esses atributos aqui: no SQL Editor do Supabase a role atual pode não ser
-- SUPERUSER, e só um superuser pode mudar o atributo SUPERUSER.
alter role genomia_app_writer
    login
    password 'TROQUE_POR_UMA_SENHA_FORTE';

-- Permite conectar ao banco atual (postgres no Supabase).
do $$
begin
    execute format(
        'grant connect on database %I to genomia_app_writer',
        current_database()
    );
end
$$;

grant usage on schema genomai_app to genomia_app_writer;
grant select, insert, update, delete on all tables in schema genomai_app to genomia_app_writer;
grant usage, select on all sequences in schema genomai_app to genomia_app_writer;

-- Objetos futuros criados pelo owner atual (postgres) também são liberados.
alter default privileges in schema genomai_app
    grant select, insert, update, delete on tables to genomia_app_writer;
alter default privileges in schema genomai_app
    grant usage, select on sequences to genomia_app_writer;

-- A role interna não deve enxergar/alterar o schema analisado.
revoke all on schema public from genomia_app_writer;
revoke all on all tables in schema public from genomia_app_writer;
revoke all on all sequences in schema public from genomia_app_writer;

-- ---------------------------------------------------------------------
-- 4) Conferência rápida (deve retornar 4 tabelas e a role)
-- ---------------------------------------------------------------------
select table_schema, table_name
from information_schema.tables
where table_schema = 'genomai_app'
order by table_name;

select rolname, rolcanlogin, rolsuper
from pg_roles
where rolname = 'genomia_app_writer';
