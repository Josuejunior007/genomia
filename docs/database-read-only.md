# Acesso read-only do PostgreSQL/Supabase

A API precisa consultar metadados de tabelas no schema configurado em `DB_SCHEMA`.
`DB_READ_ONLY=true` é apenas uma indicação da aplicação; a barreira real é a role
PostgreSQL usada em `DATABASE_URL`.

## Provisionar a role

1. Conecte ao banco alvo como owner/admin usando uma conexão privada e TLS.
2. Execute `scripts/provision_read_only_role.sql` com `psql`. O script pede a
   senha de forma oculta e não grava credenciais no repositório. Para um schema
   diferente de `public`, edite `target_schema` no início do script e configure
   o mesmo nome em `DB_SCHEMA`.
3. No Supabase, se a política do projeto não permitir criar roles com `psql`,
   crie a role de login pelo painel **Database > Roles**. Depois conecte-se com
   uma role administrativa e execute o restante do script; nesse caso, comente
   a linha `\\password genomia_reader` no script se a senha já foi definida
   no painel.
4. Execute o comando de `ALTER DEFAULT PRIVILEGES` como cada role que cria
   tabelas no schema. Privilégios padrão são específicos do owner que os define.
5. Garanta que `genomia_reader` não seja membro de outras roles. O script usa
   `NOINHERIT`; a validação rejeita qualquer membership, atributo administrativo,
   permissões públicas de escrita ou grants preexistentes.
6. Use a conexão da role de runtime na configuração da API e rode a validação:

   ```bash
   python -m scripts.check_read_only
   ```

Configure `.env` localmente (ou o secret manager do deploy), sem commitar o arquivo:

```dotenv
DATABASE_URL=postgresql+psycopg://genomia_reader:<senha>@<host>:5432/<database>?sslmode=require
DB_SCHEMA=public
DB_READ_ONLY=true
```

Substitua os campos entre sinais de menor/maior com os dados do projeto; não use
a URL da role administrativa. Proteja e faça rotação da senha pelo secret manager.

## O que a validação confirma

O comando verifica se a conexão é PostgreSQL, testa a consulta a
`information_schema`, confirma `USAGE` e ausência de `CREATE` no schema e no
banco, e rejeita roles administrativas, memberships e privilégios efetivos de
INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER (inclusive grants por coluna)
nas tabelas do schema. O backend executa a mesma validação no startup e não
inicia se a checagem falhar. O comando retorna código de saída diferente de zero
quando falha.

O SQL concede SELECT nas tabelas existentes e registra privilégios padrão para
tabelas futuras criadas pelos owners configurados. Objetos criados por outros
owners exigem repetir o ajuste de privilégios padrão para cada owner.

## Limites

- O script não cria nem altera usuários reais de produção até ser executado por
  uma pessoa com acesso administrativo. Nenhuma credencial é criada neste projeto.
- A validação cobre o schema configurado e os privilégios PostgreSQL observáveis
  pela sessão. Se a aplicação consultar outros schemas, adapte e valide cada um.
- RLS pode restringir linhas visíveis, mas não substitui grants read-only. A role
  de runtime nunca deve herdar permissões administrativas.
- Não rode migrations de escrita com a URL da API; use uma conexão separada de
  owner/admin para operações de manutenção.
