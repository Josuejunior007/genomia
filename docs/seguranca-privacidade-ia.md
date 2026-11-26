# Segurança e privacidade da IA

**Épico:** "Garantir que dados pessoais ou sensíveis não sejam enviados à IA,
utilizando apenas metadados seguros para gerar a documentação."

Este documento explica o que foi implementado, por que funciona e como verificar.

## 1. Modelo de ameaça

| Risco | Exemplo | Mitigação |
|---|---|---|
| Enviar registros de atendimento | `resumo_gsv` com relato pessoal | O construtor nunca lê linhas; o payload não tem campo de valores. |
| Enviar defaults | `DEFAULT '123.456.789-00'` | `default` não está na allowlist e é descartado. |
| Enviar segredos | `senha_hash`, tokens, chaves | Categoria `autenticacao` + redação + proibição de chaves. |
| Vazamento em identificador | coluna `cpf_12345678900` | Redação de e-mails, UUIDs, tokens, JWTs e 6+ dígitos. |
| IA analisar o próprio app | tabela `suggestions` | Exclusão por `ANALYSIS_EXCLUDED_TABLES`. |
| Prompt injection via metadados | nome de tabela com instrução | O system prompt manda não obedecer; o modelo não tem ferramentas. |
| Reprodução de dados em sugestões | IA inventar/colar valores | Prompt proíbe exemplos; colunas sensíveis marcadas; revisão humana. |
| Falta de rastreabilidade | "o que foi enviado?" | `/privacy/ai-payload` + hash em `ai_metadata_audits`. |

## 2. O que a IA recebe

A allowlist está em `app/privacy/metadata.py`:

- `schema_name`;
- tabela: `name`, `primary_key`, `foreign_keys`, `indexes`;
- coluna: `name`, `type`, `nullable`, `is_primary_key`, `sensitive`,
  `sensitivity_category`;
- FK: colunas, tabela/schema referenciados (sanitizados);
- índice: nome, colunas, `unique`.

Nada mais. Em particular, **não** há:

- `rows`, `records`, `values`, `sample`, `data`, `raw`;
- `default`/`defaults` (valores padrão);
- credenciais, tokens ou hashes de senha;
- nome do banco (`database` é excluído do contexto).

## 3. O que a IA nunca recebe

- Registros de `app_atendimento_*`, `atendimentos_unificados`,
  `bora_conversar_*` ou qualquer outra tabela.
- Strings de resumos, observações, telefones, nomes, e-mails, matrículas.
- Tabelas internas: `suggestions`, `suggestion_revisions`, `apply_logs`,
  `ai_metadata_audits`.
- O SQL candidato de uma sugestão anterior (o prompt só recebe achados
  determinísticos sanitizados).

## 4. Classificação de colunas sensíveis

Categorias e exemplos de nomes reconhecidos:

| Categoria | Exemplos de nome |
|---|---|
| `identificacao` | cpf, cnpj, rg, nome, nascimento, documento |
| `contato` | email, telefone, celular, whatsapp |
| `endereco` | endereco, cep, bairro, cidade, latitude |
| `saude` | saude, doenca, diagnostico, prontuario, exame, medicamento |
| `financeiro` | cartao, conta, pix, salario, renda |
| `autenticacao` | senha, password, token, secret, api_key, hash |
| `profissional` | matricula, funcionario, usuario, perfil |
| `biometria` | biometria, facial, iris, impressao_digital |

A classificação é conservadora: o objetivo é avisar o modelo e o revisor, não
garantir que todo nome esteja coberto.

### Pseudonimização opcional

Com `PRIVACY_MASK_SENSITIVE_IDENTIFIERS=true`, colunas sensíveis viram
`coluna_sensivel_01`, `coluna_sensivel_02` etc. Use quando o nome da coluna em si
for considerado sensível pela organização. O custo é perder parte da utilidade da
documentação automática.

## 5. Redação de identificadores

`sanitize_identifier` aplica, nesta ordem:

1. e-mails → `<email>`;
2. UUIDs → `<uuid>`;
3. tokens (`sk-...`, `ghp_...`, `glpat-...`) → `<token>`;
4. JWTs → `<jwt>`;
5. sequências de 6+ dígitos → `<numeros>` (configurável);
6. telefones → `<telefone>`;
7. caracteres de controle removidos;
8. tamanho máximo de 128 caracteres.

Isso protege contra nomes de tabela/coluna que contenham valores colados por
engano (migrações antigas, imports etc.).

## 6. Validação antes da rede

`assert_safe_payload` percorre o JSON recursivamente e falha se encontrar chaves
proibidas (`rows`, `default`, `values`, `password`, `secret`, `token`,
`api_key`...) ou strings acima de 4000 caracteres. A chamada do provedor
acontece **depois** dessa validação.

O `GroqAdvisorService` também sanitiza os achados determinísticos antes de
montá-los no prompt.

## 7. Auditoria sem duplicar dados

Cada análise grava `ai_metadata_audits`:

- provedor e modelo;
- SHA-256 do payload canônico;
- contagem de tabelas/colunas;
- colunas sensíveis marcadas;
- identificadores redigidos;
- campos removidos;
- tabelas excluídas;
- persona que disparou;
- status (`started`, `success`, `failed`).

O conteúdo do payload **não** é armazenado. Para reproduzir, use
`/api/v1/privacy/ai-payload` (que regenera a partir do schema atual).

## 8. Critérios de aceite do épico

| Critério | Evidência |
|---|---|
| [x] A IA recebe apenas metadados | `build_safe_schema_context` + allowlist |
| [x] Nenhum registro/valor/default é enviado | `assert_safe_payload` + testes |
| [x] Colunas sensíveis são identificadas | `classify_sensitive` + `sensitive` no payload |
| [x] Identificadores suspeitos são redigidos | `sanitize_identifier` (e-mail, UUID, token, dígitos) |
| [x] Tabelas internas do app não entram no payload | `ANALYSIS_EXCLUDED_TABLES` + testes |
| [x] É possível auditar o que foi enviado | hash em `ai_metadata_audits` + `/privacy/ai-payload` |
| [x] A interface mostra a prévia | botão **Metadados da IA** |
| [x] O comportamento é testado | `tests/test_privacy_metadata.py` |
| [x] Está documentado para analistas/devs/IA | este guia + guias específicos |

## 9. Como verificar

### Pela API

```bash
curl http://127.0.0.1:8000/api/v1/privacy/ai-payload | jq
```

Confira:

- `report.excluded_table_names` contém `suggestions` etc.
- `payload.tables[].columns[].sensitive` marca CPF/e-mail/saúde.
- Nenhum valor de registro aparece no JSON.
- No fluxo de análise (`POST /advisor/ai-analyze`), a resposta inclui
  `privacy.records_sent = 0` e `privacy.defaults_sent = 0`.

### Pela interface

**Análise estrutural → Metadados da IA** abre a prévia com contadores, política,
tabelas excluídas e o JSON completo.

### Por testes

```bash
python -m pytest tests/test_privacy_metadata.py -q
```

Os testes cobrem:

- defaults não aparecem;
- tabela interna excluída;
- FK para tabela interna removida;
- CPF/e-mail/saúde classificados;
- mascaramento opcional;
- redação de e-mail/dígitos/UUID;
- `assert_safe_payload` rejeita `rows`/`default`;
- relatório determinístico sanitizado.

## 10. Limitações e responsabilidades

- Nomes de colunas são metadados, mas podem ser sensíveis por si só; use
  `PRIVACY_MASK_SENSITIVE_IDENTIFIERS=true` se necessário.
- A classificação por nome não substitui uma política de dados formal.
- O provedor de IA ainda recebe os metadados; escolha um provedor com contrato
  de não retenção/treinamento adequado.
- A revisão humana é obrigatória antes de qualquer aplicação.
- A IA pode alucinar; por isso o SQL candidato nunca é executado e toda proposta
  é revisada.

## 11. LGPD / governança

O fluxo foi desenhado para minimização de dados:

- finalidade: documentação e melhoria estrutural;
- necessidade: apenas metadados;
- transparência: prévia e política acessíveis;
- segurança: roles separadas, TLS, secrets fora do Git;
- prestação de contas: hash/auditoria e histórico de decisões.

Antes de produção, valide com o jurídico/DPO o contrato do provedor de IA e a
base legal aplicável.
