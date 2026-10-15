-- =====================================================================
-- SCHEMA RELACIONAL - Sistemas de Atendimento (App Atendimento,
-- Atendimentos Unificados e Bora Conversar)
-- Gerado a partir dos arquivos anonimizados enviados.
-- =====================================================================

-- ---------------------------------------------------------------------
-- DOMINIO 1: APP ATENDIMENTO (sistema de tickets/atendimento interno)
-- ---------------------------------------------------------------------

CREATE TABLE app_atendimento_status (
    cd_status     INTEGER PRIMARY KEY,
    nm_status     VARCHAR(50) NOT NULL,
    ativo         SMALLINT NOT NULL DEFAULT 1
);

CREATE TABLE app_atendimento_canal (
    cd_tip_origem INTEGER PRIMARY KEY,
    nm_tip_origem VARCHAR(100) NOT NULL,
    canal         VARCHAR(100) NOT NULL,
    ativo         SMALLINT NOT NULL DEFAULT 1
);

CREATE TABLE app_atendimento_registro (
    protocolo                     INTEGER PRIMARY KEY,
    dt_abertura                   TIMESTAMP NOT NULL,
    cd_status                     INTEGER NOT NULL,
    mtc_responsavel               VARCHAR(20),   -- matricula do funcionario responsavel
    mtc_atendida                  VARCHAR(20),   -- matricula do funcionario atendido
    restrito                      SMALLINT,
    ind_ts                        SMALLINT,
    cd_assunto_ts                 INTEGER,
    cd_canal                      INTEGER,
    dt_atualizacao                TIMESTAMP,
    cd_atividade                  INTEGER,
    cd_detalhe                    INTEGER,
    gsv_protocolo                 BIGINT,        -- protocolo de sistema externo (GSV)
    telefone                      VARCHAR(20),
    resumo_gsv                    TEXT,
    resumo_app                    TEXT,
    canal_selecionado             VARCHAR(100),
    atividade_detalhe_selecionado VARCHAR(200),
    CONSTRAINT fk_registro_status FOREIGN KEY (cd_status)
        REFERENCES app_atendimento_status (cd_status),
    CONSTRAINT fk_registro_canal FOREIGN KEY (cd_canal)
        REFERENCES app_atendimento_canal (cd_tip_origem)
);

CREATE TABLE app_atendimento_historico (
    id_descricao     INTEGER PRIMARY KEY,
    protocolo        INTEGER NOT NULL,
    dt_registro      TIMESTAMP NOT NULL,
    mtc_responsavel  VARCHAR(20),
    descricao        TEXT,
    confirmacao      VARCHAR(20),
    dt_atualizacao   TIMESTAMP,
    ord_descricao     INTEGER,
    excluido         SMALLINT DEFAULT 0,
    CONSTRAINT fk_historico_registro FOREIGN KEY (protocolo)
        REFERENCES app_atendimento_registro (protocolo)
);

-- ---------------------------------------------------------------------
-- DOMINIO 2: ATENDIMENTOS UNIFICADOS (amostra consolidada / relatorio)
-- Sem FK formal para o Dominio 1: o vinculo possivel e por MATRICULA
-- (funcionario), nao por protocolo (numeracoes distintas).
-- ---------------------------------------------------------------------

CREATE TABLE atendimentos_unificados (
    id             INTEGER PRIMARY KEY,
    protocolo      BIGINT,
    data_hora      TIMESTAMP NOT NULL,
    duracao_seg    INTEGER,
    responsavel    VARCHAR(20),   -- codigo funcional (ex: F1363203)
    canal          VARCHAR(50),
    matricula      VARCHAR(20),   -- matricula do funcionario atendido
    matricula_norm VARCHAR(20),   -- matricula normalizada
    status         VARCHAR(30),
    link           VARCHAR(300)
);

-- ---------------------------------------------------------------------
-- DOMINIO 3: BORA CONVERSAR (canal de apoio: saude mental, assedio etc.)
-- Sistema proprio, com sua propria base de usuarios (login/admin).
-- IMPORTANTE: responsavel_matricula e criado_por_matricula sao
-- MATRICULAS de funcionario, e NAO fazem referencia a
-- bora_conversar_usuarios.id (validado nos dados: nenhum valor bate).
-- ---------------------------------------------------------------------

CREATE TABLE bora_conversar_usuarios (
    id           INTEGER PRIMARY KEY,
    nome         VARCHAR(100) NOT NULL,
    email        VARCHAR(150) NOT NULL,
    senha_hash   VARCHAR(255) NOT NULL,
    perfil       VARCHAR(30) NOT NULL,
    ativo        SMALLINT NOT NULL DEFAULT 1,
    data_criacao TIMESTAMP NOT NULL
);

CREATE TABLE bora_conversar_atendimentos (
    id                     INTEGER PRIMARY KEY,
    numero_atendimento     VARCHAR(20) NOT NULL,
    cliente_nome           VARCHAR(100),
    cliente_matricula      VARCHAR(20),
    responsavel_matricula  VARCHAR(20),   -- matricula (nao referencia usuarios.id)
    assunto                VARCHAR(100),
    status                 VARCHAR(30),
    data_atendimento       DATE,
    data_retorno           DATE,
    protocolo_gsv          BIGINT,        -- protocolo de sistema externo (GSV)
    canal_atendimento      VARCHAR(30),
    observacoes_iniciais   TEXT,
    data_criacao           TIMESTAMP,
    criado_por_matricula   VARCHAR(20)    -- matricula (nao referencia usuarios.id)
);

-- =====================================================================
-- Observacoes:
-- 1) Nao ha FK entre os 3 dominios porque cada um e um sistema/base
--    diferente. A "chave de negocio" comum entre eles e a MATRICULA
--    do funcionario (funciona como uma dimensao compartilhada, nao
--    como chave estrangeira formal).
-- 2) gsv_protocolo (dominio 1) e protocolo_gsv (dominio 3) apontam
--    para um sistema externo chamado GSV, mas as faixas numericas
--    nao coincidem nos dados de amostra (periodos diferentes),
--    portanto nao devem ser declaradas como FK entre si.
-- =====================================================================
