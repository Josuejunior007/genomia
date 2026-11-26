# Mapa do código

Este mapa explica o papel de cada arquivo e onde procurar ao fazer uma mudança.

## Backend

| Arquivo | Responsabilidade | Pontos de entrada |
|---|---|---|
| `app/main.py` | Cria a FastAPI, CORS, startup, handlers, `/` e `/health`. | `startup_checks`, `health` |
| `app/core/config.py` | `Settings` tipado; três URLs, schema interno, exclusões, privacidade. | `Settings`, `settings` |
| `app/core/personas.py` | Enum `Persona`, capacidades e dependencies. | `get_persona`, `require_capability` |
| `app/db/session.py` | Engine do banco analisado (read-only). | `engine` |
| `app/db/app_session.py` | Engine interno, `ensure_app_store`, migração SQLite, isolamento. | `ensure_app_store`, `validate_store_isolation` |
| `app/db/write_session.py` | Engine opcional de escrita para aplicar mudanças. | `get_write_engine` |
| `app/db/permissions.py` | Validação fail-closed da role PostgreSQL. | `validate_read_only` |
| `app/db/base.py` | Base declarativa e `app_table_args` (schema interno). | `Base`, `app_table_args` |
| `app/models/suggestion.py` | Estado atual da sugestão. | `Suggestion` |
| `app/models/audit.py` | Revisões, aplicação e auditoria de IA. | `SuggestionRevision`, `ApplyLog`, `AiMetadataAudit` |
| `app/privacy/metadata.py` | Allowlist, classificação sensível, redação, hash, `assert_safe_payload`. | `build_safe_schema_context` |
| `app/schemas/schema.py` | Contratos Pydantic/OpenAPI. | todos os `*Info`, `ReviewItem` etc. |
| `app/services/schema_service.py` | Reflection + exclusão de tabelas internas. | `snapshot`, `table` |
| `app/services/table_data_service.py` | Linhas paginadas e relacionamentos (read-only). | `rows`, `relationships` |
| `app/services/advisor_service.py` | Regras determinísticas. | `AdvisorService.analyze` |
| `app/services/groq_advisor_service.py` | Cliente Groq; valida payload seguro. | `GroqAdvisorService.analyze` |
| `app/services/change_apply_service.py` | Preview/apply/auditoria de mudanças. | `ChangeApplyService` |
| `app/api/v1/router.py` | Agrega as rotas. | `api_router` |
| `app/api/v1/endpoints/schema.py` | `/schema`. | `get_schema` |
| `app/api/v1/endpoints/catalog.py` | Catálogo, linhas, relacionamentos. | `list_tables` etc. |
| `app/api/v1/endpoints/advisor.py` | Análise determinística e IA. | `analyze_schema`, `analyze_schema_with_ai` |
| `app/api/v1/endpoints/suggestions.py` | CRUD, edição versionada, revisão, aplicação. | rotas `/suggestions` |
| `app/api/v1/endpoints/dashboard.py` | Métricas. | `metrics` |
| `app/api/v1/endpoints/system.py` | Personas, storage, privacidade. | `storage_info`, `preview_ai_payload` |
| `app/api/v1/endpoints/demo.py` | Compatibilidade (re-exporta o router). | `router` |

## Scripts

| Arquivo | Uso |
|---|---|
| `scripts/init.sql` | Schema de exemplo do banco analisado. |
| `scripts/provision_read_only_role.sql` | Cria a role `genomia_reader` no PostgreSQL. |
| `scripts/check_read_only.py` | Valida a role configurada. |
| `scripts/app_store_postgres.sql` | Cria o schema/tabelas internas em PostgreSQL. |
| `scripts/provision_app_store_role.sql` | Cria a role `genomia_app_writer` em produção. |
| `scripts/local_reader_role.sql` | Role de leitura do docker-compose local. |
| `scripts/local_app_writer_role.sql` | Role de escrita do docker-compose local. |
| `scripts/migrate_app_store.py` | Migra SQLite/legado para o armazenamento interno. |
| `scripts/export_openapi.py` | Gera `docs/openapi.json`. |

## Frontend

| Arquivo | Responsabilidade |
|---|---|
| `frontend/src/App.tsx` | Shell, navegação, visão geral, catálogo, análise, revisão, modais (edição, aplicação, privacidade), persona. |
| `frontend/src/api.ts` | Cliente HTTP, tipos, cabeçalho de persona, tratamento de erros. |
| `frontend/src/TableDrawer.tsx` | Painel lateral: dados, colunas, relacionamentos, índices. |
| `frontend/src/styles.css` | Estilos (inclui componentes de modal/persona/privacidade). |
| `frontend/src/table-drawer.css` | Estilos do drawer. |
| `frontend/vite.config.ts` | Configuração do Vite. |

## Testes

| Arquivo | Foco |
|---|---|
| `tests/test_advisor.py` | regras determinísticas. |
| `tests/test_schema_service.py` | reflection. |
| `tests/test_table_data.py` | linhas/relacionamentos/serialização. |
| `tests/test_read_only_role.py` | permissões PostgreSQL. |
| `tests/test_database_errors.py` | 503 padronizado. |
| `tests/Test_dashboard.py` | métricas. |
| `tests/test_personas.py` | personas/capacidades. |
| `tests/test_privacy_metadata.py` | privacidade do payload. |
| `tests/test_suggestions_workflow.py` | edição/revisão. |
| `tests/test_apply_service.py` | aplicação/auditoria. |
| `tests/test_analysis_exclusions.py` | isolamento de tabelas internas. |
| `tests/test_isolation.py` | isolamento de schema/role/armazenamento. |
| `tests/test_migration.py` | migração legada. |

## Onde mexer para...

| Objetivo | Arquivos |
|---|---|
| Adicionar uma regra | `advisor_service.py` + `tests/test_advisor.py` |
| Adicionar um campo na sugestão | `models/suggestion.py`, `schemas/schema.py`, `scripts/app_store_postgres.sql`, `_SQLITE_COLUMN_MIGRATIONS`, testes |
| Adicionar um endpoint | `api/v1/endpoints/*.py`, `router.py`, `schemas/schema.py`, docs/OpenAPI |
| Trocar o provedor de IA | `services/groq_advisor_service.py` (novo serviço), `api/v1/endpoints/advisor.py`, `privacy/metadata.py` |
| Suportar outro SGBD | `services/schema_service.py`, `db/permissions.py`, `services/change_apply_service.py`, docs |
| Mudar a matriz de personas | `core/personas.py`, `docs/personas-permissoes.md`, testes |
| Mudar o visual | `frontend/src/App.tsx`, `styles.css`, `table-drawer.css` |
| Trocar SQLite por PostgreSQL | `.env`, `scripts/app_store_postgres.sql`, `docs/persistencia-e-isolamento.md` |
