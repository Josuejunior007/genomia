# Decisões de arquitetura (ADRs)

## ADR-001 — Separar o armazenamento interno do banco analisado

**Contexto:** as sugestões começaram em SQLite; em algum momento a tabela
`public.suggestions` existiu no schema analisado e a IA gerou sugestões sobre
ela. Isso caracteriza mistura entre "onde salvar" e "o que analisar".

**Decisão:**

- `APP_DATABASE_URL` é uma conexão separada.
- Em PostgreSQL, as tabelas internas ficam no schema `genomai_app`.
- `ANALYSIS_EXCLUDED_TABLES` remove as tabelas internas de qualquer snapshot.
- O startup falha se o schema interno for igual ao analisado ou se a role for a
  mesma.

**Consequências:** mais configuração no deploy; em troca, isolamento verificável
e ausência de contaminação da análise.

## ADR-002 — Allowlist de metadados para IA

**Contexto:** prompts com "não envie dados pessoais" não são garantia técnica.

**Decisão:** `app/privacy/metadata.py` constrói um payload com allowlist,
sanitiza identificadores, marca colunas sensíveis e valida o resultado com
`assert_safe_payload` antes da chamada de rede.

**Consequências:** novos campos de metadados exigem atualização explícita da
allowlist; nenhum campo "extra" vaza por padrão.

## ADR-003 — Auditoria por hash, não por conteúdo

**Contexto:** armazenar o payload para auditar criaria uma segunda cópia de
metadados (e possíveis dados sensíveis).

**Decisão:** guardar SHA-256, contagens, modelo, persona e status. O payload pode
ser regenerado por `/privacy/ai-payload`.

**Consequências:** auditoria suficiente para provar o que foi enviado sem reter o
conteúdo; se for necessário reproduzir exatamente, versionar o schema.

## ADR-004 — Persona por cabeçalho no MVP

**Contexto:** o projeto não tinha autenticação, mas a mentora pediu respeito a
personas.

**Decisão:** `X-GenomAI-Persona` + matriz de capacidades no backend. O frontend
envia a persona selecionada e esconde ações, mas o backend sempre valida.

**Consequências:** demonstração clara e testável; **não** é autenticação forte.
Em produção, substituir por OIDC/JWT mantendo `require_capability`.

## ADR-005 — Aplicar apenas SQL gerado pelo servidor

**Contexto:** o SQL candidato da IA é texto não confiável e pode conter
instruções perigosas ou nomes inválidos.

**Decisão:** `ChangeApplyService` valida tabela/coluna no snapshot e gera
`CREATE INDEX`/`COMMENT ON` por conta própria. O SQL da IA fica apenas como
informação na sugestão.

**Consequências:** menos flexibilidade imediata, muito menos risco. Novos tipos
de mudança exigem implementação explícita e testes.

## ADR-006 — Edição sempre reabre a sugestão

**Contexto:** a mentora pediu edição para casos de aprovação parcial.

**Decisão:** `PATCH` cria uma revisão imutável, incrementa a versão e volta o
status para `pending` (configurável por `reopen`). O status anterior é
preservado em `previous_status`.

**Consequências:** nenhuma edição "passa por cima" de uma aprovação; toda mudança
de conteúdo exige nova decisão humana.

## ADR-007 — Migração leve de SQLite, DDL explícito em PostgreSQL

**Contexto:** o banco de desenvolvimento SQLite já existia e não pode ser perdido
ao adicionar colunas; em produção, DDL deve ser controlado.

**Decisão:** `_SQLITE_COLUMN_MIGRATIONS` adiciona colunas ausentes de forma
idempotente. PostgreSQL usa `scripts/app_store_postgres.sql`; o startup não faz
ALTER TABLE.

**Consequências:** dev funciona sem apagar dados; produção exige migração
versionada.
