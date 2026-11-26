# Referência da API

Base: `http://127.0.0.1:8000`  
OpenAPI: `GET /docs` · `GET /openapi.json` · [docs/openapi.json](openapi.json)

## Convenções

- JSON UTF-8.
- Persona no cabeçalho `X-GenomAI-Persona`:
  `leitor`, `analista`, `desenvolvedor`, `administrador`.
- Sem cabeçalho: `DEFAULT_PERSONA` (padrão `leitor`).
- Erros de validação: HTTP 422 com `detail` (lista).
- Erros de permissão: HTTP 403 com `detail` (string).
- Banco indisponível: HTTP 503 com `{"detail": "...", "code": "database_unavailable"}`.
- Operação bloqueada: HTTP 409 com `detail` (string ou objeto `ApplyPreview`).

## Health

### `GET /`
Identifica a API.

### `GET /health`
Verifica a conexão com o banco analisado.

```json
{"status":"ok","database":"connected","engine":"PostgreSQL"}
```

## Schema e catálogo

### `GET /api/v1/schema`
Retorna `SchemaSnapshot` com tabelas do schema configurado, exceto as internas.

### `GET /api/v1/catalog/tables?q=`
Lista tabelas. `q` busca em nome de tabela/coluna (máx. 80 caracteres).

```json
{
  "count": 1,
  "items": [
    {
      "name": "app_atendimento_status",
      "schema": "public",
      "columns_count": 3,
      "primary_key": ["cd_status"],
      "foreign_keys_count": 0
    }
  ]
}
```

### `GET /api/v1/catalog/tables/{table_name}`
Retorna `TableInfo` ou 404.

### `GET /api/v1/catalog/tables/{table_name}/rows?limit=25&offset=0`
Retorna `TableRows` com registros paginados. `limit` entre 1 e 200. Somente
leitura. Amostras **não** são enviadas à IA.

### `GET /api/v1/catalog/tables/{table_name}/relationships`
Retorna FKs de saída e entrada (`TableRelationships`).

## Análise

### `GET /api/v1/dashboard/metrics`
Persona mínima: `leitor`. Retorna cobertura de metadados, tabelas sem PK e
contagens de sugestões (`pending`, `partially_approved`, `approved`, `rejected`,
`reviewed`, `total`).

### `GET /api/v1/advisor/analyze`
Executa regras determinísticas.

```json
{
  "summary": "7 tabela(s) analisada(s); 3 recomendação(ões) encontrada(s).",
  "tables_analyzed": 7,
  "recommendations": [
    {
      "severity": "high",
      "table": "app_atendimento_registro",
      "category": "primary_key",
      "message": "Tabela sem chave primária...",
      "suggested_sql": null,
      "evidence": "..."
    }
  ]
}
```

### `POST /api/v1/advisor/ai-analyze`
Persona mínima: `analista`.

- Exige `AI_ENABLED=true` e `GROQ_API_KEY`.
- Constrói o payload seguro, registra `ai_metadata_audits`, chama o provedor e
  persiste propostas `pending`.
- HTTP 503 se IA desativada/sem chave; 504 timeout; 502 erro do provedor.

Resposta:

```json
{
  "summary": "...",
  "suggestions_created": 2,
  "duplicates_skipped": 1,
  "suggestions": [ ... ],
  "human_review_required": true,
  "database_changes_applied": false,
  "privacy": {
    "policy": "safe-metadata-v1",
    "payload_sha256": "…",
    "tables_sent": 7,
    "columns_sent": 65,
    "sensitive_columns_flagged": 11,
    "redacted_identifiers": 0,
    "excluded_tables": ["suggestions", "..."],
    "records_sent": 0,
    "defaults_sent": 0
  }
}
```

## Sugestões

### `GET /api/v1/suggestions?status=&table=&q=&limit=&offset=`
Persona mínima: `leitor`.

`status`: `pending | approved | rejected | partially_approved | all` (padrão
`pending`). Retorna `Suggestion[]`.

### `POST /api/v1/suggestions`
Persona mínima: `analista`.

```json
{
  "table": "app_atendimento_status",
  "kind": "index",
  "column_name": "ativo",
  "description": "Criar índice para filtros por ativo.",
  "confidence": 0.7,
  "rationale": "A coluna não é a primeira de um índice.",
  "suggested_sql": "CREATE INDEX ...;"
}
```

`kind` ∈ `documentation | relationship | index | integrity | naming | review`.
Tabela/coluna são validadas contra o snapshot; tabelas internas retornam 422.

### `PATCH /api/v1/suggestions/{id}`
Persona mínima: `analista`.

Campos opcionais: `table`, `kind`, `column_name`, `description`, `confidence`,
`rationale`, `suggested_sql`, `comment`, `reopen` (padrão `true`).

- Gera uma versão em `suggestion_revisions`.
- Com `reopen=true`, o status volta para `pending` e `previous_status` guarda o
  anterior.
- Sugestão já aplicada retorna 409.

### `POST /api/v1/suggestions/{id}/review`
Persona mínima: `analista`.

```json
{"decision":"approved","comment":"Ok"}
```

`decision` ∈ `approved | rejected | partially_approved`. Retorna
`{id, status, comment, reviewed_by, reviewed_at, version}`.
No-op (ex.: aprovar duas vezes) retorna 409; sugestão aplicada retorna 409.

### `GET /api/v1/suggestions/{id}/revisions`
Persona mínima: `leitor`. Retorna o histórico imutável, em ordem de versão.

### `GET /api/v1/suggestions/{id}/apply-preview`
Persona mínima: `desenvolvedor`.

```json
{
  "suggestion_id": 42,
  "action": "index",
  "sql": "CREATE INDEX \"genomai\".\"idx_...\" ON \"public\".\"tabela\" (\"coluna\");",
  "can_apply": true,
  "blockers": [],
  "warnings": ["SQL gerado pelo servidor ..."]
}
```

Bloqueios comuns: sugestão não aprovada, já aplicada, tipo não suportado,
`DB_WRITE_ENABLED=false`, sem `WRITE_DATABASE_URL`, coluna ausente, índice
redundante, `COMMENT ON` fora do PostgreSQL.

### `POST /api/v1/suggestions/{id}/apply`
Persona mínima: `desenvolvedor`.

Retorna `ApplyResponse`:

```json
{
  "suggestion_id": 42,
  "action": "index",
  "success": true,
  "sql": "CREATE INDEX ...;",
  "error": null,
  "applied_at": "2026-11-26T12:00:00Z",
  "applied_by": "desenvolvedor",
  "log_id": 7
}
```

Se a execução falhar, `success=false` e `error` é preenchido; a tentativa é
auditada. Bloqueios retornam HTTP 409 com `detail` no formato `ApplyPreview`.

### `GET /api/v1/apply-logs?suggestion_id=&limit=50`
Persona mínima: `desenvolvedor`. Lista `ApplyLog[]`.

## Personas e sistema

### `GET /api/v1/personas`
Persona mínima: `leitor`.

```json
[
  {
    "id": "analista",
    "label": "Analista de dados",
    "description": "Cria, edita e revisa sugestões...",
    "capabilities": ["read", "review", "suggest"]
  }
]
```

### `GET /api/v1/system/storage`
Persona mínima: `leitor`. Mostra banco analisado, armazenamento interno,
isolamento, avisos e configuração de IA. Não expõe credenciais.

## Privacidade

### `GET /api/v1/privacy/policy`
Persona mínima: `leitor`. Lista campos permitidos, nunca enviados, categorias
sensíveis, flags e tabelas excluídas.

### `GET /api/v1/privacy/ai-payload`
Persona mínima: `leitor`. Gera o payload **sem chamar o provedor**:

```json
{
  "payload": {"schema_name":"public","tables":[...],"policy":"safe-metadata-v1"},
  "report": {
    "tables_included": 7,
    "tables_excluded": 0,
    "columns_included": 65,
    "sensitive_columns": 11,
    "redacted_identifiers": 0,
    "removed_fields": 0,
    "masked_sensitive_identifiers": false,
    "excluded_table_names": ["suggestions", "..."],
    "notice": "Somente metadados estruturais..."
  },
  "sha256": "...",
  "policy": { ... }
}
```

### `GET /api/v1/privacy/audits?limit=20`
Persona mínima: `leitor`. Lista hashes/contagens; **não** retorna o payload.

## Códigos de erro

| Código | Quando |
|---|---|
| 400 | Persona inválida. |
| 403 | Persona sem a capacidade exigida. |
| 404 | Sugestão/tabela não encontrada. |
| 409 | Conflito de estado (já revisada, já aplicada, aplicação bloqueada). |
| 422 | Validação de entrada/tabela/coluna/tipo. |
| 502 | Provedor de IA falhou. |
| 503 | Banco/IA indisponível ou desativada. |
| 504 | Timeout do provedor de IA. |
