# GenomAI — Backend demonstrativo (Supabase / PostgreSQL)

Backend FastAPI para apresentação de mentoria. Lê metadados do schema configurado no Supabase PostgreSQL, executa regras determinísticas e oferece endpoints demonstrativos para catálogo, métricas e revisão humana.

## O que funciona neste MVP
- `/health`: testa a conexão com `SELECT 1`.
- `GET /api/v1/schema`: lista tabelas, colunas, tipos, PKs, FKs e índices.
- `GET /api/v1/advisor/analyze`: aponta tabelas sem PK, possíveis índices ausentes em colunas de FK e alertas simples de nomenclatura.
- `GET /api/v1/catalog/tables?q=termo`: pesquisa por nome de tabela ou coluna.
- `GET /api/v1/catalog/tables/{table_name}`: detalhes de uma tabela.
- `GET /api/v1/dashboard/metrics`: indicadores básicos.
- `GET /api/v1/suggestions`: fila de sugestões de demonstração.
- `POST /api/v1/suggestions/{id}/review`: aprova/rejeita sugestão em memória para demonstrar o fluxo.

## Limites importantes para explicar na mentoria
- A conexão real é somente para leitura no fluxo da aplicação; configure também um usuário PostgreSQL/Supabase com privilégios mínimos de leitura. Não use credenciais de administrador em produção.
- A fila de sugestões é de demonstração e fica na memória: reiniciar a API restaura o estado inicial. Ainda não há tabelas de auditoria nem persistência de revisões.
- A IA generativa/Azure OpenAI ainda não está conectada. As sugestões de revisão são exemplos ilustrativos; a análise estrutural do Advisor é determinística.
- O dashboard apresenta métricas técnicas básicas, não uma medição real de documentação de negócio aprovada.
- Nenhuma recomendação SQL é executada. O SQL é apenas texto para revisão humana.

## Como executar no Windows / VS Code
1. Extraia o ZIP e abra a pasta `mariadb_ai_manager`.
2. Instale Python 3.11 ou superior.
3. No terminal:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Copie `.env.example` para `.env` e configure `DATABASE_URL` com a URI PostgreSQL do Supabase. Em geral, adapte a URI para começar com `postgresql+psycopg://`. Se a senha tiver caracteres especiais, use URL-encoding.
5. Ajuste `DB_SCHEMA=public` se suas tabelas estiverem em outro schema.
6. Rode:
   ```bash
   uvicorn app.main:app --reload
   ```
7. Abra `http://127.0.0.1:8000/docs` para testar os endpoints.

## Rotas principais
| Método | Rota | Objetivo |
|---|---|---|
| GET | `/health` | Conectividade |
| GET | `/api/v1/schema` | Metadados do banco |
| GET | `/api/v1/advisor/analyze` | Recomendações determinísticas |
| GET | `/api/v1/catalog/tables` | Busca no catálogo |
| GET | `/api/v1/catalog/tables/{table_name}` | Detalhes de tabela |
| GET | `/api/v1/dashboard/metrics` | Métricas básicas |
| GET | `/api/v1/suggestions` | Fila demonstrativa |
| POST | `/api/v1/suggestions/{id}/review` | Revisão humana demonstrativa |

## Exemplo de revisão
`POST /api/v1/suggestions/1/review`
```json
{"decision":"approved","comment":"Descrição revisada pela equipe."}
```
Use `decision` com `approved` ou `rejected`.

## Segurança
Não commite `.env`, não compartilhe a URI do banco nem credenciais. Use conexão SSL conforme indicado pelo Supabase. A API não lê linhas de negócio: trabalha com metadados estruturais.
