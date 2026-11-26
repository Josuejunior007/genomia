# Guia do desenvolvedor

## 1. Stack

- Python 3.11+ (o ambiente atual usa 3.14), FastAPI, SQLAlchemy 2.x, Pydantic 2.x,
  psycopg 3, OpenAI SDK apontando para a Groq.
- React 18 + TypeScript + Vite.
- PostgreSQL/Supabase como banco analisado; PostgreSQL (recomendado) ou SQLite
  como armazenamento interno.

## 2. Setup local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edite DATABASE_URL e APP_DATABASE_URL
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Testes:

```bash
python -m pytest -q
cd frontend && npm run build
```

## 3. Configuração

Leia `app/core/config.py`. As variáveis estão documentadas no
[README](../README.md#variáveis-de-ambiente) e no `.env.example`.

Pontos de atenção:

- `DATABASE_URL` deve usar uma role **somente leitura**. O startup executa
  `validate_read_only` e **não sobe** se a role puder escrever.
- `APP_DATABASE_URL` é o banco interno. Em PostgreSQL, as tabelas ficam em
  `APP_DB_SCHEMA` (`genomai_app` por padrão).
- `WRITE_DATABASE_URL` é opcional e só é usada pelo endpoint de aplicação.
- `DB_WRITE_ENABLED=false` por padrão. Mantenha assim até ter uma role de DDL
  dedicada e um processo de revisão.

## 4. Banco interno: criação e migração

### PostgreSQL (produção)

```bash
psql "$ADMIN_DATABASE_URL" -f scripts/app_store_postgres.sql
psql "$ADMIN_DATABASE_URL" -f scripts/provision_app_store_role.sql
```

Depois:

```dotenv
APP_DATABASE_URL=postgresql+psycopg://genomia_app_writer:<senha>@<host>:5432/<db>?sslmode=require
APP_DB_SCHEMA=genomai_app
APP_DB_AUTO_CREATE=false
APP_STORE_REQUIRE_REMOTE=true
```

O startup chama `ensure_app_store()`. Com `APP_DB_AUTO_CREATE=false`, ele não
tenta criar schema nem tabelas; apenas verifica se o provisionamento existe e
falha com instrução clara se faltar algo. Em SQLite, o `create_all` e a migração
leve continuam acontecendo.

### SQLite (desenvolvimento)

O padrão `sqlite:///./genomai_app.db` é resolvido para a raiz do projeto. O
arquivo antigo é migrado automaticamente: `column_name`, `suggested_sql`,
`version`, `previous_status`, `reviewed_by`, `edited_by`, `updated_at`,
`applied_at`, `applied_by`, `apply_error` são adicionados se faltarem. Cada
sugestão antiga sem histórico recebe uma revisão inicial (`migracao`) para o
modal de edição não começar vazio.

### Migrar sugestões legadas

```bash
# Prévia
python -m scripts.migrate_app_store --sqlite ./genomai_app.db --dry-run

# SQLite local -> PostgreSQL interno
python -m scripts.migrate_app_store --sqlite ./genomai_app.db

# public.suggestions do Supabase -> armazenamento interno
python -m scripts.migrate_app_store --postgres-url "$DATABASE_URL" --dry-run
```

O script é idempotente por `(tabela, tipo, descrição)`, não lê dados de
atendimentos e não altera o banco de origem.

## 5. Estrutura do código

```text
app/main.py                     criação da app, startup, health
app/core/config.py              Settings + propriedades de isolamento
app/core/personas.py            Persona, capacidades, dependencies
app/db/session.py               engine read-only
app/db/app_session.py           engine interno, ensure_app_store, migração SQLite
app/db/write_session.py         engine de escrita opcional
app/db/permissions.py           validação fail-closed da role
app/models/                     Suggestion, SuggestionRevision, ApplyLog, AiMetadataAudit
app/privacy/metadata.py         allowlist, redação, sensibilidade, hash, assert
app/schemas/schema.py           contratos Pydantic (OpenAPI)
app/services/schema_service.py  reflection + exclusão de tabelas internas
app/services/table_data_service.py  linhas/relacionamentos read-only
app/services/advisor_service.py regras determinísticas
app/services/groq_advisor_service.py cliente Groq (recebe só payload seguro)
app/services/change_apply_service.py preview/apply/auditoria
app/api/v1/endpoints/           rotas
```

### Como adicionar uma regra determinística

1. Edite `AdvisorService.analyze` em `app/services/advisor_service.py`.
2. Use apenas `SchemaSnapshot` (metadados).
3. Adicione um teste em `tests/test_advisor.py`.
4. Nunca execute SQL; no máximo devolva `suggested_sql` informativo.

### Como adicionar um provedor de IA

Implemente uma classe com o mesmo contrato de `GroqAdvisorService`:

```python
def analyze(
    self,
    safe_context: SafeSchemaContext | dict,
    deterministic: AnalysisReport | dict,
) -> GroqAnalysis:
    ...
```

Regras:

- chame `assert_safe_payload` antes de qualquer rede;
- use `build_safe_schema_context` na rota (não no cliente);
- devolva o mesmo JSON (`summary`, `suggestions[]`);
- registre um `AiMetadataAudit` com hash/contagens;
- nunca envie `SchemaSnapshot` cru.

### Como adicionar suporte a outro SGBD

Veja [Integração com outros bancos e IAs](integracao-outros-bancos-e-ias.md).
Resumo:

- `SchemaService` usa o inspector do SQLAlchemy; a maior parte é portável.
- `app/db/permissions.py` é específico de PostgreSQL e precisa de um validador
  por dialeto.
- `ChangeApplyService` tem DDL específico (`CREATE INDEX`, `COMMENT ON`).
- `TableDataService` já usa quoting do dialeto.

## 6. Testes

```bash
python -m pytest -q
python -m pytest tests/test_privacy_metadata.py -q
python -m pytest tests/test_apply_service.py -q
```

Cobertura relevante:

- `test_privacy_metadata.py` — allowlist, redação, sensibilidade, payload.
- `test_apply_service.py` — preview/apply/auditoria em SQLite, bloqueios.
- `test_suggestions_workflow.py` — criação, edição versionada, revisão parcial.
- `test_analysis_exclusions.py` — tabelas internas fora do catálogo/IA.
- `test_personas.py` — matriz de capacidades.
- `test_read_only_role.py` — validação da role.

O frontend precisa compilar:

```bash
cd frontend
npm run build
```

## 7. Exportar o OpenAPI

```bash
python -m scripts.export_openapi
```

Gera `docs/openapi.json` (contrato para integração e para agentes de IA).

## 8. Checklist de produção

- [ ] `DATABASE_URL` com role read-only validada (`python -m scripts.check_read_only`).
- [ ] `APP_DATABASE_URL` em PostgreSQL, schema `genomai_app`, role de escrita
      dedicada, `APP_STORE_REQUIRE_REMOTE=true`, `APP_DB_AUTO_CREATE=false`.
- [ ] `ANALYSIS_EXCLUDED_TABLES` revisado para o seu ambiente.
- [ ] `DB_WRITE_ENABLED=false` até existir processo de aprovação e role de DDL.
- [ ] `AI_ENABLED` e `GROQ_API_KEY` no secret manager (nunca no Git).
- [ ] `CORS_ORIGINS` com a origem real do frontend.
- [ ] Autenticação real substituindo `X-GenomAI-Persona`.
- [ ] Backup do banco interno e política de retenção de auditoria.
- [ ] HTTPS/TLS e rotação de credenciais.

## 9. Troubleshooting

| Sintoma | Causa provável | Solução |
|---|---|---|
| Startup falha com "Permissões do PostgreSQL não são somente leitura" | `DATABASE_URL` usa role admin ou com grants de escrita | Crie/use `genomia_reader` (`scripts/provision_read_only_role.sql`). |
| "schema interno ... não foi possível criar" | Role do app sem `CREATE SCHEMA` | Rode `scripts/app_store_postgres.sql` como admin e `APP_DB_AUTO_CREATE=false`. |
| "mesma role" no startup | `APP_DATABASE_URL` e `DATABASE_URL` usam a mesma role | Crie `genomia_app_writer`. |
| `Aplicar no BD` desabilitado | persona ou `DB_WRITE_ENABLED` | Use desenvolvedor/admin e configure `WRITE_DATABASE_URL`. |
| IA desativada | `AI_ENABLED=false`/sem chave | Configure no `.env`/secret manager. |
| Tabela interna aparecendo | `ANALYSIS_EXCLUDED_TABLES` incompleto | Inclua o nome e reinicie. |
| Frontend não conecta | `VITE_API_URL`/CORS | Ajuste `frontend/.env` e `CORS_ORIGINS`. |

## 10. Convenções

- Docstrings em português, com o "porquê" de segurança quando aplicável.
- Rotas finas; lógica em `services/`.
- Toda saída de IA é não confiável: valide tabela/coluna novamente.
- Nunca interpole texto de usuário/IA em SQL; use quoting/validação.
- Toda mudança de schema interno precisa de migração SQL + migração SQLite.
