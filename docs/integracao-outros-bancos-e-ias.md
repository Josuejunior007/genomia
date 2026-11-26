# Integração com outros bancos e outras IAs

O GenomAI foi desenhado com fronteiras claras para facilitar portabilidade. Este
guia mostra o que é portável, o que é específico de PostgreSQL e como adicionar
um novo banco ou provedor de IA sem quebrar os invariantes de segurança.

## 1. Fronteiras do código

| Camada | Arquivo | Portabilidade |
|---|---|---|
| Reflection de metadados | `app/services/schema_service.py` | Alta (SQLAlchemy Inspector). |
| Leitura de linhas/FKs | `app/services/table_data_service.py` | Alta (quoting do dialeto). |
| Regras | `app/services/advisor_service.py` | Média (usa quoting PostgreSQL no SQL sugerido). |
| Permissões read-only | `app/db/permissions.py` | **Baixa** (catálogo `pg_*`). |
| Aplicação de mudanças | `app/services/change_apply_service.py` | Média (`CREATE INDEX` portável; `COMMENT ON` PostgreSQL). |
| Privacidade | `app/privacy/metadata.py` | Totalmente portável. |
| Provedor de IA | `app/services/groq_advisor_service.py` | Substituível por interface. |
| Armazenamento interno | `app/models/`, `scripts/app_store_postgres.sql` | SQLAlchemy; SQL de referência PostgreSQL. |

## 2. Adicionar MySQL/MariaDB

O nome histórico do repositório é `mariadb_ai_manager`, e existe um schema de
exemplo em `scripts/init.sql` (DDL compatível com PostgreSQL/MariaDB). Porém, a
versão atual **exige PostgreSQL** no banco analisado por causa de:

- `validate_read_only` consultar `pg_roles`, `pg_auth_members`, `pg_class`;
- `COMMENT ON` (aplicação de documentação);
- sintaxe de introspecção de permissões.

Para portar:

1. Crie `app/db/permissions_mysql.py` com um `validate_read_only` baseado em
   `SHOW GRANTS FOR CURRENT_USER()` / `information_schema.USER_PRIVILEGES`.
   Rejeite `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `GRANT`.
2. Ajuste `app/services/advisor_service.py` para usar o quoting do dialeto
   (`engine.dialect.identifier_preparer`) em vez de `"` fixo.
3. Em `change_apply_service.py`, para documentação use
   `ALTER TABLE ... COMMENT = '...'` / `ALTER TABLE ... MODIFY COLUMN ... COMMENT`.
   Para índices, `CREATE INDEX` já é compatível.
4. Ajuste `SchemaService` se o inspector não retornar FKs/índices como esperado
   (teste com `tests/test_schema_service.py`).
5. O armazenamento interno pode continuar em PostgreSQL; não é necessário migrar
   o banco de sugestões para o mesmo SGBD do banco analisado.
6. Atualize `docs/database-read-only.md` e os scripts de provisionamento.

> Não use a role administrativa do MySQL/MariaDB. Crie uma role só com `SELECT`
> e `SHOW VIEW` (quando necessário).

## 3. Adicionar SQL Server / Oracle

As mesmas ideias se aplicam, mudando:

- introspecção de permissões (`sys.database_permissions`, `DBA_SYS_PRIVS`);
- quoting (`[ ]` / `"`);
- DDL de comentário (`sp_addextendedproperty` / `COMMENT ON`);
- paginação (o SQLAlchemy já abstrai `LIMIT/OFFSET` na maioria dos casos, mas
  valide).

Sempre adicione testes com um banco real ou container; não confie apenas no
inspector.

## 4. Adicionar outro provedor de IA

Implemente uma classe com o contrato abaixo e injete no endpoint
`ai-analyze`:

```python
class MyProviderService:
    def analyze(
        self,
        safe_context: SafeSchemaContext | dict,
        deterministic: AnalysisReport | dict,
    ) -> GroqAnalysis:
        # 1. assert_safe_payload(safe_context)
        # 2. montar prompt
        # 3. chamar o provedor
        # 4. validar JSON no schema esperado
        ...
```

Requisitos:

- reutilizar `build_safe_schema_context` (a rota já faz);
- reutilizar `assert_safe_payload` antes da rede;
- devolver `summary` + lista de sugestões com `table`, `kind`, `column_name`,
  `description`, `confidence`, `evidence`, `risks_and_uncertainty`,
  `suggested_sql`;
- registrar `AiMetadataAudit` com hash/contagens;
- não enviar `SchemaSnapshot` cru;
- não executar nada.

Para provedores que não suportam JSON Schema estrito, valide a saída com
Pydantic e descarte itens inválidos. Nunca use a saída do modelo para montar SQL
executável.

## 5. Usar a API como integração

Um agente/integração externa deve:

1. consultar `/api/v1/privacy/policy`;
2. consultar `/api/v1/privacy/ai-payload` para inspecionar;
3. criar/revisar sugestões via API;
4. nunca aplicar sem uma persona autorizada e confirmação humana.

O contrato está em [api-reference.md](api-reference.md) e
[docs/openapi.json](openapi.json).

## 6. Adaptar o armazenamento interno

Se a organização já tem um PostgreSQL/Supabase, use o schema `genomai_app`.
Se usa outro SGBD para o app:

- os modelos SQLAlchemy são portáveis;
- `scripts/app_store_postgres.sql` é a referência de DDL;
- a migração leve de SQLite em `app/db/app_session.py` precisa de um equivalente;
- `schema` em `app_table_args` pode ser adaptado para o conceito do SGBD
  (database/schema).

Mantenha a regra: **armazenamento interno isolado do banco analisado**.

## 7. Checklist de portabilidade

- [ ] Validador de permissões específico do SGBD, fail-closed.
- [ ] Quoting de identificadores via dialeto.
- [ ] DDL de aplicação testado no SGBD.
- [ ] Testes de reflection (PK, FK, índice, tipo).
- [ ] Testes de paginação e valores nulos.
- [ ] Privacidade intacta (mesmo payload seguro).
- [ ] Documentação atualizada.
