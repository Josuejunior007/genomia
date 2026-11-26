# Personas e permissões

## 1. Matriz

| Capacidade | `leitor` | `analista` | `desenvolvedor` | `administrador` |
|---|:---:|:---:|:---:|:---:|
| `read` — catálogo, análise, sugestões, histórico | ✅ | ✅ | ✅ | ✅ |
| `suggest` — criar e editar sugestões | — | ✅ | ✅ | ✅ |
| `review` — aprovar/rejeitar/parcial | — | ✅ | ✅ | ✅ |
| `apply` — aplicar no banco | — | — | ✅ | ✅ |
| `audit` — consultar `apply-logs` | — | — | ✅ | ✅ |

A matriz é aplicada por `app/core/personas.py` e pelas dependencies
`require_capability(...)` em cada rota. O frontend apenas esconde botões; o
backend sempre valida.

## 2. Cabeçalho

```http
X-GenomAI-Persona: analista
```

Valores aceitos: `leitor`, `analista`, `desenvolvedor`, `administrador`.
Aliases aceitos: `viewer`, `analyst`, `developer`, `admin`, `data_analyst`, `dev`.

Sem cabeçalho, vale `DEFAULT_PERSONA` (padrão `leitor`). Persona inválida →
HTTP 400. Capacidade ausente → HTTP 403.

## 3. Exemplos

### Analista cria e revisa

```bash
curl -X POST http://127.0.0.1:8000/api/v1/suggestions \
  -H 'Content-Type: application/json' \
  -H 'X-GenomAI-Persona: analista' \
  -d '{"table":"app_atendimento_status","kind":"documentation","description":"Documentar a tabela.","confidence":0.8,"rationale":"Metadados insuficientes de negócio."}'
```

### Leitor não pode revisar

```bash
curl -X POST http://127.0.0.1:8000/api/v1/suggestions/1/review \
  -H 'Content-Type: application/json' \
  -H 'X-GenomAI-Persona: leitor' \
  -d '{"decision":"approved"}'
# HTTP 403
```

### Desenvolvedor aplica

```bash
curl http://127.0.0.1:8000/api/v1/suggestions/1/apply-preview \
  -H 'X-GenomAI-Persona: desenvolvedor'
```

## 4. Por que "respeitar personas" importa

- Separa **quem decide** (analista) de **quem executa** (desenvolvedor).
- Impede que uma IA ou um usuário leitor altere o banco.
- Mantém trilha de auditoria: `reviewed_by`, `edited_by`, `applied_by`.
- Permite evoluir para autenticação real sem mudar a lógica de negócio.

## 5. Integração com autenticação real

O MVP usa um cabeçalho para demonstrar a governança. Em produção:

1. Substitua `get_persona` por uma dependency que valide um JWT/OIDC.
2. Mapeie o claim de role/grupo para `Persona`.
3. Mantenha `require_capability` nas rotas.
4. Remova o seletor de persona do frontend (ou torne-o somente leitura).
5. Registre o `sub`/e-mail do usuário em `reviewed_by`/`applied_by` em vez do
   nome da persona.

Exemplo de dependency:

```python
from fastapi import Depends, HTTPException
from app.core.personas import Persona

def get_persona_from_token(token: str = Depends(oauth2_scheme)) -> Persona:
    claims = verify_jwt(token)  # sua implementação
    role = claims.get("role")
    try:
        return Persona(role)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Role não autorizada.") from exc
```

## 6. Testes

```bash
python -m pytest tests/test_personas.py -q
```

Cobrem aliases, matriz e bloqueio de `apply` para analista. Testes de rota
também verificam 403 para leitor (veja `tests/Test_dashboard.py` e
`tests/test_database_errors.py` como referência de TestClient).
