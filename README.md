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
| `GET /api/v1/suggestions` | Lista sugestões persistidas (`status=pending`, `approved`, `rejected` ou `all`). |
| `POST /api/v1/suggestions` | Registra uma sugestão para revisão humana. |
| `POST /api/v1/suggestions/{suggestion_id}/review` | Aprova ou rejeita uma sugestão pendente. |

## Como executar

1. Abrir a pasta do projeto no VS Code ou na sua ide favorita.
2. Criar um ambiente virtual e instalar as dependências:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copiar `.env.example` para `.env` e configurar `DATABASE_URL` com uma role PostgreSQL somente leitura. `APP_DATABASE_URL` aponta para o banco controlado pelo GenomAI, que guarda sugestões e decisões (por padrão, SQLite local; em produção, configure um PostgreSQL dedicado). Nunca reutilize a role administrativa ou a role somente leitura do banco analisado para `APP_DATABASE_URL`.
4. Iniciar a API:

   ```bash
   uvicorn app.main:app --reload
   ```

5. Abrir `http://127.0.0.1:8000/docs` no navegador e testar as rotas.

### Interface web (React)

O frontend demonstrativo fica em `frontend/` e consome a API FastAPI. Com o backend
rodando na porta `8000`, em outro terminal:

Primeiro seleciona a pasta no front ende 
```bash
cd .\frontend
```
Agora você instala o npm
```bash
npm install
```
Agora você pode rodar a aplicação
```bash
npm run dev
```
Se não funcionar automatico pelo readme pegue o codigo e va escrevendo no terminal

Agora para encerrar a atividade, você primeiro encerra no o front, seleciona o terminal e digita "q" e da enter e depois você vai no terminal do back faz Control+c 

Abra `http://localhost:5173`. A URL da API pode ser alterada com `VITE_API_URL`
(veja `frontend/.env.example`). O `CORS_ORIGINS` padrão do backend já permite
`http://localhost:5173`.

O frontend apresenta métricas, exploração de tabelas e colunas, recomendações da
análise estrutural e revisão humana das sugestões persistidas.

## Limites atuais e próximos passos

Essa versão é um MVP para validar a ideia e demonstrar a estrutura do backend. Ainda faltam algumas partes para chegar à proposta completa:

- Integrar uma IA generativa, como Azure OpenAI, para ajudar a sugerir descrições e interpretar nomes de tabelas e campos.
- Integrar autenticação e permissões antes de disponibilizar a API fora do ambiente de desenvolvimento.
- Configurar `CORS_ORIGINS` com a origem real do frontend no ambiente de execução.
- Melhorar as métricas do dashboard para mostrar a cobertura real da documentação e da governança.
- Evoluir a interface com autenticação e fluxos de produção.

O projeto ainda não usa Power BI nem Microsoft Fabric. A documentação inicial os
cita como tecnologias possíveis para etapas futuras de visualização; nesta versão,
os indicadores são calculados pelo backend e mostrados diretamente pela interface
React. Uma integração com Fabric/Power BI pode ser avaliada se houver necessidade
de relatórios corporativos ou compartilhamento analítico fora do GenomAI.

As sugestões e decisões de revisão ficam persistidas no banco interno do GenomAI. As sugestões não são aplicadas automaticamente ao banco analisado. A integração com Gemini é opcional e permanece desativada até `AI_ENABLED=true` e `GEMINI_API_KEY` estarem configurados.

### Análise com Gemini

O botão **Analisar com Gemini** e a rota `POST /api/v1/advisor/ai-analyze` enviam ao Gemini apenas metadados do esquema (tabelas, colunas, tipos, chaves e índices). Valores padrão de colunas e registros do banco não são enviados. O modelo pode explicar problemas e propor documentação, índices ou relações com evidências, riscos e incertezas. As propostas são persistidas como pendentes e aparecem em **Revisão de sugestões**.

Para ativar a integração, instale as dependências atualizadas e configure no `.env` local:

```dotenv
AI_ENABLED=true
GEMINI_API_KEY=sua_chave_do_google_ai_studio
GEMINI_MODEL=gemini-2.5-flash
```

Mantenha a chave fora do Git. Disponibilidade e limites gratuitos dependem das condições atuais da conta e do modelo no Google AI Studio. A IA não executa mudanças, mesmo quando uma sugestão é aprovada; o fluxo atual somente registra a decisão humana. Qualquer SQL candidato é texto informativo para revisão.

Também é importante configurar o acesso ao Supabase com permissões mínimas de leitura. A opção `DB_READ_ONLY` no arquivo de configuração, sozinha, não bloqueia alterações no banco.

## Resumindo

O backend do GenomAI conecta ao PostgreSQL analisado com uma role somente leitura, lê a estrutura, disponibiliza um catálogo e aplica regras iniciais. Sugestões e decisões são persistidas separadamente no armazenamento interno da aplicação.

O frontend React já está conectado à API para apresentar o catálogo, a análise e a revisão humana. Próximos passos possíveis incluem autenticação, integração de IA para propor descrições e relações e, caso necessário, relatórios em Fabric/Power BI. A integração de IA deve usar as rotas de sugestão e preservar a revisão humana antes de qualquer mudança no banco analisado.
