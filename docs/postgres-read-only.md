## Configurar acesso realmente somente leitura no PostgreSQL/Supabase

A configuração `DB_READ_ONLY=true` é apenas uma opção da aplicação: ela **não** restringe privilégios no PostgreSQL. A API deve conectar usando um papel dedicado sem privilégios de escrita, e não com a senha do usuário administrador, `postgres` ou `service_role`.

### 1. Criar o papel de leitura

1. Abra o **SQL Editor** do Supabase e conecte-se ao projeto correto com uma conta administrativa.
2. Abra `scripts/postgres_readonly.sql`.
3. Substitua `CHANGE_ME_USE_A_LONG_RANDOM_PASSWORD` por uma senha forte e exclusiva. Execute o script sem salvar a cópia preenchida no Git ou compartilhá-la.
4. Na consulta de verificação ao final do script, troque `public.alguma_tabela` por uma tabela real. Confirme `can_use_schema=true`, `can_create_in_schema=false` e que `can_insert_example`, `can_update_example` e `can_delete_example` sejam `false`.
5. Se as tabelas forem criadas por outro papel que não `postgres`, aplique `ALTER DEFAULT PRIVILEGES FOR ROLE <papel_criador> IN SCHEMA public GRANT SELECT ON TABLES TO genomai_readonly;` para cada papel criador. Privilégios padrão são específicos do papel que cria os objetos.

O papel recebe `USAGE` no schema e `SELECT` nas tabelas existentes de `public`; isso permite ao PostgreSQL expor metadados autorizados via `information_schema` e às consultas de introspecção do SQLAlchemy. Não recebe permissões de escrita. O script não concede acesso a outros schemas.

### 2. Apontar a API para o papel dedicado

Configure `DATABASE_URL` no seu `.env` local ou gerenciador de segredos usando as credenciais de `genomai_readonly` e o endpoint de conexão PostgreSQL do Supabase. Não use a senha administrativa nem credenciais `service_role`. Mantenha `DB_READ_ONLY=true`, mas lembre-se que esse sinalizador sozinho não impõe segurança.

Exemplo de formato (não é uma URL funcional; não coloque credenciais reais no repositório):

```text
DATABASE_URL=postgresql+psycopg://genomai_readonly:<SENHA>@<HOST>:5432/<BANCO>
DB_READ_ONLY=true
DB_SCHEMA=public
```

Use o host/porta e o modo de conexão indicados no painel do Supabase para o seu projeto (direct connection ou pooler). Codifique caracteres especiais da senha como URL encoding. Nunca faça commit do `.env`.

### 3. Limitações importantes

- Execute o script como administrador e valide as permissões com as consultas acima. A API não consegue se proteger de privilégios extras concedidos fora do repositório.
- O script remove privilégios explícitos de tabela/schema concedidos diretamente a `genomai_readonly`, mas não é uma auditoria completa de grants indiretos preexistentes. Prefira criar um papel novo e não o associe a outros papéis.
- O script configura novas tabelas criadas por `postgres`; para outros papéis criadores, configure os privilégios padrão de cada um.
- Se o projeto usa schemas além de `public`, configure-os explicitamente e limite o acesso ao mínimo necessário.
- Não desabilite Row Level Security (RLS). Privilégios de leitura SQL e políticas RLS são controles diferentes; valide as políticas e o comportamento com o papel efetivamente usado.
- A senha de exemplo no script é um marcador. Troque-a antes de executar e não comite o script preenchido.
