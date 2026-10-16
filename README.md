## Como o backend funciona?

O fluxo é basicamente assim:

1. A API recebe uma requisição.
2. A rota correspondente chama o serviço necessário.
3. Quando precisa analisar o banco, o sistema lê os metadados do PostgreSQL, como tabelas, colunas, tipos, chaves e índices.
4. O analisador aplica algumas regras para encontrar possíveis pontos de atenção.
5. A API devolve o resultado em JSON para quem fez a requisição.

Por enquanto, o foco é na estrutura do banco. O sistema não precisa ler os registros dos atendimentos para fazer essa análise.

## O que cada parte faz?

### `app/main.py`

É onde a aplicação FastAPI é criada. Também registra as rotas e tem as rotas básicas para verificar se a API está funcionando e se consegue acessar o banco.

### `app/core/config.py`

Centraliza as configurações, como o nome da aplicação, a URL de conexão, o schema que será analisado e algumas opções do projeto. As informações de conexão ficam no arquivo `.env`, que não deve ser compartilhado nem enviado ao GitHub.

### `app/db/session.py`

Configura a conexão com o PostgreSQL usando SQLAlchemy. Também define recursos para abrir e fechar sessões quando forem necessários.

### `app/schemas/schema.py`

Define o formato dos dados usados pela API. Por exemplo, descreve como representar uma coluna, uma tabela, uma chave estrangeira, uma recomendação e o resultado de uma análise.

### `app/services/schema_service.py`

É a parte que consulta a estrutura do banco. Ela identifica as tabelas e coleta informações sobre as colunas, chaves primárias, chaves estrangeiras e índices. Depois organiza essas informações para os outros serviços utilizarem.

### `app/services/advisor_service.py`

É onde ficam as regras iniciais de análise. Atualmente, ele verifica situações como tabela sem chave primária, coluna de chave estrangeira sem índice identificado e alguns casos simples de nomenclatura. Quando encontra algo que merece atenção, monta uma recomendação.

Essas regras são programadas por nós, então ainda não é uma análise feita por IA generativa. A ideia é usar isso como uma primeira etapa antes de integrar um modelo de IA.

### `app/api/v1/router.py`

Organiza as rotas por funcionalidade, para o código não ficar todo concentrado em um único arquivo.

### `app/api/v1/endpoints/`

Essa pasta contém as rotas que podem ser chamadas pela API:

- `schema.py`: retorna a estrutura do banco.
- `advisor.py`: executa a análise e retorna as recomendações.
- `catalog.py`: permite pesquisar tabelas e consultar seus detalhes.
- `dashboard.py`: retorna alguns indicadores básicos.
- `demo.py`: demonstra um fluxo de revisão de sugestões, permitindo aprovar ou rejeitar uma sugestão.

### `tests/test_advisor.py`

Contém testes automatizados para verificar algumas regras do analisador, como a identificação de tabelas sem chave primária e a criação de sugestões de índice para colunas de chave estrangeira.

## O que já dá para demonstrar?

A documentação automática do FastAPI fica em `http://127.0.0.1:8000/docs`, depois de iniciar o projeto.

As principais rotas são:

| Rota | Para que serve |
|---|---|
| `GET /health` | Verifica se a API consegue acessar o banco. |
| `GET /api/v1/schema` | Mostra a estrutura do banco. |
| `GET /api/v1/advisor/analyze` | Executa as regras de análise. |
| `GET /api/v1/catalog/tables` | Lista e pesquisa tabelas. |
| `GET /api/v1/catalog/tables/{table_name}` | Mostra os detalhes de uma tabela. |
| `GET /api/v1/dashboard/metrics` | Mostra indicadores básicos. |
| `GET /api/v1/suggestions` | Lista sugestões usadas na demonstração. |
| `POST /api/v1/suggestions/{suggestion_id}/review` | Aprova ou rejeita uma sugestão demonstrativa. |

## Como executar

1. Abrir a pasta do projeto no VS Code ou na sua ide favorita.
2. Criar um ambiente virtual e instalar as dependências:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copiar `.env.example` para `.env` e colocar a URL de conexão do Supabase em `DATABASE_URL`.
4. Iniciar a API:

   ```bash
   uvicorn app.main:app --reload
   ```

5. Abrir `http://127.0.0.1:8000/docs` no navegador e testar as rotas.

## O que ainda falta desenvolver?

Essa versão é um MVP para validar a ideia e demonstrar a estrutura do backend. Ainda faltam algumas partes para chegar à proposta completa:

- Integrar uma IA generativa, como Azure OpenAI, para ajudar a sugerir descrições e interpretar nomes de tabelas e campos.
- Salvar as sugestões e as decisões de aprovação no banco, porque atualmente essa parte é apenas demonstrativa e fica na memória da aplicação.
- Implementar autenticação e permissões, se isso fizer parte do escopo final.
- Melhorar as métricas do dashboard para mostrar a cobertura real da documentação e da governança.
- Desenvolver ou conectar o frontend que vai apresentar o catálogo de forma mais visual.

As sugestões do sistema não são aplicadas automaticamente ao banco. A ideia é que sejam analisadas e validadas antes de qualquer mudança.

Também é importante configurar o acesso ao Supabase com permissões mínimas de leitura. A opção `DB_READ_ONLY` no arquivo de configuração, sozinha, não bloqueia alterações no banco.

## Resumindo

O que eu fiz até aqui foi montar a base do backend do GenomAI: conectar ao Supabase PostgreSQL, ler a estrutura do banco, disponibilizar um catálogo simples, aplicar algumas regras iniciais e demonstrar como as recomendações poderiam passar por uma revisão humana.

Escolhi começar por essa parte para manter o escopo controlado e ter algo que eu consiga executar e explicar na mentoria. Depois, a ideia é evoluir o projeto por etapas, principalmente com a integração de IA e a persistência das informações de governança.