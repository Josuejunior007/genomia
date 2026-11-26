# Persistência e isolamento

## 1. O problema que motivou esta mudança

O GenomAI começou com as sugestões em um SQLite local (`genomai_app.db`). Em
algum momento, a tabela `public.suggestions` também existiu no Supabase. Como ela
estava no schema analisado, a IA a leu e gerou uma sugestão sobre o índice dela —
ou seja, a IA passou a analisar o **próprio armazenamento de sugestões**.

A correção tem três camadas independentes:

1. **Conexão separada** (`APP_DATABASE_URL` ≠ `DATABASE_URL`).
2. **Schema separado** (`genomai_app` ≠ `public`).
3. **Exclusão explícita** (`ANALYSIS_EXCLUDED_TABLES`).

## 2. As três conexões

| Variável | Papel | Role | Escrita |
|---|---|---|---|
| `DATABASE_URL` | Banco analisado (catálogo, metadados, amostras) | `genomia_reader` | Nunca |
| `APP_DATABASE_URL` | Sugestões, revisões, auditorias | `genomia_app_writer` | Sim, no schema interno |
| `WRITE_DATABASE_URL` | Aplicar mudanças aprovadas | role de DDL dedicada | Sim, apenas DDL permitido |

Nunca reutilize a role read-only para `APP_DATABASE_URL` nem a role de escrita
interna para o banco analisado.

## 3. O schema interno

Em PostgreSQL, todas as tabelas do app ficam em `genomai_app`:

```text
genomai_app.suggestions
genomai_app.suggestion_revisions
genomai_app.apply_logs
genomai_app.ai_metadata_audits
```

Cada tabela tem um propósito:

- `suggestions`: estado atual da proposta.
- `suggestion_revisions`: histórico imutável de edições.
- `apply_logs`: tentativas de aplicação (sucesso/falha, SQL, persona, duração).
- `ai_metadata_audits`: hash/contagens do payload enviado à IA (sem conteúdo).

## 4. Configuração no Supabase (passo a passo)

O banco do GenomAI já usa uma role read-only. Para o armazenamento interno, crie
uma role de escrita separada e o schema `genomai_app`.

1. No **SQL Editor** do Supabase, conectado como owner/admin, execute
   `scripts/app_store_postgres.sql`.
2. Crie a role `genomia_app_writer` e defina a senha. Use `psql` com
   `scripts/provision_app_store_role.sql` (que pede a senha de forma oculta) ou,
   se estiver no SQL Editor web, crie a role em **Database > Roles** e execute
   somente os `GRANT`/`ALTER` do script (o meta-comando `\password` não funciona
   no editor web). Não commite a senha.
3. No `.env` (ou secret manager), configure:

   ```dotenv
   APP_DATABASE_URL=postgresql+psycopg://genomia_app_writer:<senha>@<host>:5432/<db>?sslmode=require
   APP_DB_SCHEMA=genomai_app
   APP_DB_AUTO_CREATE=false
   APP_STORE_REQUIRE_REMOTE=true
   ```

   **Não altere `DATABASE_URL` nem `DB_SCHEMA`.** Eles continuam apontando para
   o banco analisado: `DATABASE_URL` com a role `genomia_reader_app` e
   `DB_SCHEMA=public`. O writer vai somente em `APP_DATABASE_URL`, e o schema
   interno somente em `APP_DB_SCHEMA`.

4. Reinicie a API. Em `/api/v1/system/storage`, `app_store.backend` deve ser
   `postgresql`, `app_store.schema` deve ser `genomai_app` e
   `isolation.valid` deve ser `true`.
5. Migre as sugestões existentes:

   ```bash
   python -m scripts.migrate_app_store --sqlite ./genomai_app.db --dry-run
   python -m scripts.migrate_app_store --sqlite ./genomai_app.db
   ```

> A role `genomia_reader_app` atual é **somente leitura** e não pode criar o
> schema. É necessário um acesso administrativo ao projeto Supabase para rodar os
> dois scripts.

## 5. Por que a IA não mistura os dados

Fluxo do snapshot:

```text
SchemaService(engine=análise, schema=DB_SCHEMA)
  -> inspector.get_table_names(schema=DB_SCHEMA)
  -> remove ANALYSIS_EXCLUDED_TABLES
  -> SchemaSnapshot
  -> build_safe_schema_context
  -> allowlist de metadados
  -> assert_safe_payload
  -> provedor de IA
```

O armazenamento interno:

- não é lido por `SchemaService`;
- não é lido por `GroqAdvisorService`;
- não entra em `/privacy/ai-payload`;
- não aparece em `/catalog/tables`;
- não entra em `/dashboard/metrics`;
- não é usado para gerar SQL de aplicação.

Além disso, no startup:

- se `APP_DB_SCHEMA == DB_SCHEMA`, a API falha;
- se as duas conexões usam a mesma role, a API falha;
- se `APP_STORE_REQUIRE_REMOTE=true` e o armazenamento é SQLite, a API falha.

## 6. Tabela legada `public.suggestions`

Se o seu Supabase ainda tem `public.suggestions`, ela é excluída da análise por
`ANALYSIS_EXCLUDED_TABLES`. Você pode:

1. Migrar os dados com `scripts/migrate_app_store.py` (revise os nomes de
   tabela; versões antigas podem ter nomes normalizados sem `_`).
2. Depois de validar, remover a tabela legada com uma role administrativa:

   ```sql
   -- Faça backup antes. Exemplo; ajuste o nome.
   DROP TABLE IF EXISTS public.suggestions;
   ```

   Só faça isso quando tiver certeza de que nenhuma outra aplicação usa a tabela.

Enquanto ela existir, a exclusão por nome impede a contaminação.

## 7. SQLite como fallback de desenvolvimento

O SQLite é útil para rodar sem infraestrutura. Ele **não** é o recomendado para
produção porque:

- não tem concorrência/roles como PostgreSQL;
- fica em um único arquivo do servidor;
- não tem backup gerenciado nem replicação;
- não demonstra o isolamento por schema/role.

Use `APP_STORE_REQUIRE_REMOTE=true` para impedir o deploy acidental com SQLite.

## 8. Migração de esquema

O arquivo `scripts/app_store_postgres.sql` é a referência para PostgreSQL. Se
você adicionar uma coluna:

1. Atualize o modelo em `app/models/`.
2. Atualize `scripts/app_store_postgres.sql`.
3. Adicione a coluna em `_SQLITE_COLUMN_MIGRATIONS` em `app/db/app_session.py`.
4. Adicione um teste de migração/uso.

O startup executa `Base.metadata.create_all` (idempotente) e a migração leve de
SQLite. Ele **não** faz ALTER TABLE em PostgreSQL; use o SQL de migração.

## 9. Backup e retenção

- Faça backup do schema `genomai_app` junto com o banco.
- `apply_logs` e `ai_metadata_audits` são trilhas de auditoria; defina retenção
  conforme a política da organização.
- O payload da IA não é armazenado; só o hash. Se precisar reproduzir uma
  análise, guarde o snapshot/versionamento do schema separadamente.

## 10. Checklist rápido

- [ ] `APP_DATABASE_URL` aponta para PostgreSQL com schema `genomai_app`.
- [ ] `APP_DB_SCHEMA` ≠ `DB_SCHEMA`.
- [ ] `genomia_app_writer` não tem acesso ao schema `public`.
- [ ] `genomia_reader` não tem escrita em lugar nenhum.
- [ ] `ANALYSIS_EXCLUDED_TABLES` cobre as tabelas internas/legadas.
- [ ] `/api/v1/system/storage` mostra `isolation.valid=true`.
- [ ] `python -m scripts.migrate_app_store ... --dry-run` mostra o esperado.
- [ ] Backup do schema interno configurado.
