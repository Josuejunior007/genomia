# Acesso read-only do PostgreSQL/Supabase

A API consulta metadados no schema configurado em `DB_SCHEMA`. `DB_READ_ONLY=true`
é apenas um indicador: a proteção real vem dos grants da role usada em
`DATABASE_URL`. O backend valida os grants no startup e recusa iniciar se
encontrar escrita, privilégios administrativos ou falta de leitura.

## Configurar no Supabase

1. No painel Supabase, abra **Database > Roles** e crie a role de login
   `genomia_reader_app` com senha forte. Ela não deve ser superuser, ter
   `CREATEDB`, `CREATEROLE`, `REPLICATION`, `BYPASSRLS`, nem herdar outras
   roles. Configure a senha pelo painel; não a escreva em SQL ou no Git.
2. Conecte ao banco como owner/admin e execute
   `scripts/provision_read_only_role.sql` usando o SQL Editor, DataGrip ou outro
   cliente PostgreSQL. O script contém SQL padrão, sem comandos `psql`. Ele
   assume banco `postgres` e schema `public`; se forem diferentes, substitua
   esses nomes literais e ajuste `DB_SCHEMA`.
3. Execute o comando `ALTER DEFAULT PRIVILEGES` como cada role que cria tabelas
   no schema. Privilégios padrão são específicos do owner que os define.
4. Configure a URL da role de runtime em `.env` local ou no secret manager:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://genomia_reader_app:<senha>@<host>:5432/postgres?sslmode=require
   DB_SCHEMA=public
   DB_READ_ONLY=true
   ```

   Substitua os campos de exemplo; não use a URL administrativa. Se a senha
   contiver caracteres especiais, faça URL-encode antes de colocá-la na URL.
5. Rode a checagem manual:

   ```bash
   python -m scripts.check_read_only
   ```

   O mesmo teste roda quando a API inicia.

## Se a role antiga já existir

O script não tenta alterar atributos administrativos de uma role existente.
No Supabase, o usuário conectado não tem superuser; uma role antiga com
`SUPERUSER` não pode ser corrigida com `ALTER ROLE` por essa conexão. Use a
role nova `genomia_reader_app` criada pelo painel e aplique os grants a ela.
Para diagnosticar a role antiga, consulte:

```sql
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication,
       rolbypassrls, rolinherit
FROM pg_roles
WHERE rolname IN ('genomia_reader', 'genomia_reader_app');
```

Não remova uma role antiga sem verificar antes se algum serviço a utiliza.

## O que a validação confirma

A checagem testa PostgreSQL e `information_schema`; confirma `USAGE` e
`SELECT` nas tabelas/visões do schema; rejeita falta de leitura, permissões de
criação, roles administrativas, memberships e privilégios efetivos de
INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER, incluindo grants por coluna.
Ela retorna código de saída diferente de zero em caso de falha.

O SQL concede SELECT nos objetos existentes. Para tabelas futuras, cada owner
que as criar precisa aplicar `ALTER DEFAULT PRIVILEGES`. Repita os grants para
outros schemas que a aplicação consultar.

## Limites

- Nenhum usuário ou segredo de produção foi criado pelo código. O provisionamento
  só ocorre quando um administrador o executa no projeto.
- RLS pode restringir linhas visíveis, mas não substitui grants read-only.
- Use outra conexão owner/admin para migrations de escrita e manutenção.
