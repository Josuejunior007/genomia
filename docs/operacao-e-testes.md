# Operação, testes e troubleshooting

## 1. Comandos do dia a dia

```bash
# Backend
uvicorn app.main:app --reload --port 8000

# Testes
python -m pytest -q
python -m pytest tests/test_privacy_metadata.py -q
python -m pytest tests/test_apply_service.py -q

# Validar a role read-only configurada
python -m scripts.check_read_only

# Exportar OpenAPI
python -m scripts.export_openapi

# Frontend
cd frontend
npm run dev
npm run build
```

## 2. Ambiente local com Docker Compose

O `docker-compose.yml` sobe PostgreSQL 16 e cria, na primeira inicialização:

- schema de exemplo (`scripts/init.sql`);
- role `genomia_reader` (senha `change_me_reader`);
- schema interno `genomai_app` (`scripts/app_store_postgres.sql`);
- role `genomia_app_writer` (senha `change_me_writer`).

```bash
docker compose up -d
```

`.env` local:

```dotenv
DATABASE_URL=postgresql+psycopg://genomia_reader:change_me_reader@localhost:5432/ai_manager
APP_DATABASE_URL=postgresql+psycopg://genomia_app_writer:change_me_writer@localhost:5432/ai_manager
APP_DB_SCHEMA=genomai_app
APP_DB_AUTO_CREATE=false
APP_STORE_REQUIRE_REMOTE=true
```

> Troque as senhas e não use esse compose em produção.

## 3. Testes automatizados

| Arquivo | O que cobre |
|---|---|
| `tests/test_advisor.py` | regras de PK, índice e FK. |
| `tests/test_schema_service.py` | reflection de tabela/colunas/chaves/índices. |
| `tests/test_table_data.py` | paginação, nulos, relacionamentos, serialização. |
| `tests/test_database_errors.py` | 503 padronizado. |
| `tests/test_read_only_role.py` | validação fail-closed da role. |
| `tests/test_personas.py` | aliases, matriz, 403. |
| `tests/test_privacy_metadata.py` | allowlist, redação, sensibilidade, payload. |
| `tests/test_suggestions_workflow.py` | criação, edição versionada, parcial. |
| `tests/test_apply_service.py` | preview, apply, auditoria, bloqueios. |
| `tests/test_analysis_exclusions.py` | tabelas internas fora do catálogo/IA. |
| `tests/test_isolation.py` | isolamento de schema/role/armazenamento. |
| `tests/test_migration.py` | normalização/leitura da migração legada. |
| `tests/Test_dashboard.py` | métricas. |

Saída esperada: `77 passed` (pode variar com novos testes).

## 4. Verificações manuais úteis

```bash
# Isolamento
curl http://127.0.0.1:8000/api/v1/system/storage | jq

# Política de privacidade
curl http://127.0.0.1:8000/api/v1/privacy/policy | jq

# Payload exato (não chama IA)
curl http://127.0.0.1:8000/api/v1/privacy/ai-payload | jq

# Catálogo (a tabela suggestions não deve aparecer)
curl http://127.0.0.1:8000/api/v1/catalog/tables | jq '.items[].name'

# Sugestões
curl 'http://127.0.0.1:8000/api/v1/suggestions?status=all' \
  -H 'X-GenomAI-Persona: leitor' | jq
```

## 5. Logs e observabilidade

- Uvicorn registra requisições e falhas.
- `ai_metadata_audits` registra hash/contagens de cada análise com IA.
- `apply_logs` registra SQL, persona, sucesso/falha e duração.
- Não logue payloads completos nem credenciais. O código evita expor
  credenciais em mensagens de erro.

## 6. Troubleshooting

### "Permissões do PostgreSQL não são somente leitura"
A role de `DATABASE_URL` tem escrita, criação ou membership. Use
`scripts/provision_read_only_role.sql` e rode `python -m scripts.check_read_only`.

Se a mensagem citar o schema `genomai_app`, provavelmente `DB_SCHEMA` foi
trocado por engano. O correto é:

```dotenv
DATABASE_URL=...role genomia_reader_app...
DB_SCHEMA=public

APP_DATABASE_URL=...role genomia_app_writer...
APP_DB_SCHEMA=genomai_app
```

`DATABASE_URL` é o banco **analisado** (leitura). `APP_DATABASE_URL` é o banco
**interno** (escrita). Nunca coloque a role de escrita em `DATABASE_URL`.

### "permission denied to alter role ... SUPERUSER"
No SQL Editor do Supabase, a role atual pode não ser SUPERUSER. Não use
`ALTER ROLE ... NOSUPERUSER/NOREPLICATION/NOBYPASSRLS`: a role já nasce com
esses atributos desligados. Use apenas:

```sql
alter role genomia_app_writer with login password 'sua_senha';
```

### "Não foi possível criar o schema interno"
A role de `APP_DATABASE_URL` não tem `CREATE SCHEMA`. Rode
`scripts/app_store_postgres.sql` como admin e use `APP_DB_AUTO_CREATE=false`.

### "A persona X não tem permissão"
A capacidade exigida não está na matriz. Use a persona correta no cabeçalho.
Lembre: o frontend também envia a persona selecionada.

### "Escrita desativada"
`DB_WRITE_ENABLED=false` ou `WRITE_DATABASE_URL` vazio. Configure uma role de DDL
dedicada e reinicie.

### "A sugestão precisa estar aprovada"
A aplicação só ocorre após `POST /review` com `decision=approved` (ou após
reabrir/editar e aprovar novamente).

### "Tabela não encontrada ... reservada ao armazenamento interno"
Você tentou criar sugestão para uma tabela em `ANALYSIS_EXCLUDED_TABLES`. Use
outra tabela ou revise a configuração.

### IA retorna 503/504
Verifique `AI_ENABLED`, `GROQ_API_KEY`, `GROQ_MODEL`, limites do provedor e
timeout. Nenhuma sugestão parcial é salva.

### Frontend vazio / API desconectada
Verifique `VITE_API_URL`, se o backend está em `8000` e se `CORS_ORIGINS` inclui
`http://localhost:5173`.

## 7. Deploy checklist

- [ ] Variáveis no secret manager, nunca no Git.
- [ ] `DATABASE_URL` read-only validada no startup.
- [ ] `APP_DATABASE_URL` PostgreSQL/schema `genomai_app`.
- [ ] `APP_DB_AUTO_CREATE=false` e `APP_STORE_REQUIRE_REMOTE=true`.
- [ ] `ANALYSIS_EXCLUDED_TABLES` revisado.
- [ ] `DB_WRITE_ENABLED=false` até o processo de aplicação estar maduro.
- [ ] Autenticação real substituindo a persona por cabeçalho.
- [ ] TLS/HTTPS e CORS restrito.
- [ ] Backup e retenção de auditoria.
- [ ] Testes e build do frontend verdes.
