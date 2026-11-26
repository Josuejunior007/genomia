# Guia do analista de dados

Este guia explica como usar o GenomAI no dia a dia, sem precisar ler código.

## 1. O que o GenomAI faz

- Lê a **estrutura** do banco (tabelas, colunas, tipos, chaves, índices,
  relacionamentos) e mostra um catálogo pesquisável.
- Aponta problemas estruturais com regras determinísticas.
- Pode pedir à IA uma análise complementar usando **apenas metadados**.
- Guarda as sugestões em um banco interno, com revisão humana.
- Permite editar, aprovar parcialmente, aprovar, rejeitar e — para perfis
  técnicos — aplicar mudanças aprovadas no banco.

O GenomAI **não lê os registros dos atendimentos para analisar**. A tela de
exploração mostra amostras quando você abre uma tabela, mas essas amostras nunca
são enviadas à IA.

## 2. Entrando e escolhendo a persona

No menu lateral, em **PERSONA ATIVA**, escolha:

| Persona | Use quando você... |
|---|---|
| Leitor | Só precisa consultar catálogo, análise e sugestões. |
| Analista de dados | Vai criar, editar e revisar sugestões. |
| Desenvolvedor | Vai aplicar mudanças aprovadas no banco. |
| Administrador | Precisa de acesso completo e auditoria. |

> A persona é uma demonstração de governança. O backend sempre valida; trocar o
> seletor não concede permissões que a sua identidade real não teria em produção.

## 3. Explorar o catálogo

1. Clique em **Explorador de tabelas**.
2. Pesquise por nome de tabela ou coluna.
3. Clique em uma tabela para abrir o painel lateral:
   - **Dados**: amostra paginada.
   - **Colunas**: tipos, nulabilidade e PK.
   - **Relacionamentos**: FKs de entrada e saída.
   - **Índices**: índices existentes.

As tabelas internas do GenomAI (por exemplo `suggestions`) **não aparecem** —
isso é intencional para a IA não analisar o próprio armazenamento.

## 4. Executar a análise

- **Análise estrutural → Regras**: executa as regras determinísticas.
- **Análise estrutural → Analisar com Groq**: envia somente metadados seguros e
  salva propostas como pendentes.
- **Metadados da IA**: abre a prévia exata do que seria enviado, com contagens e
  hash. Use isso para auditoria e para tirar dúvidas de privacidade.

Depois de uma análise com IA, um aviso mostra:
- quantas tabelas/colunas foram enviadas;
- quantas colunas sensíveis foram marcadas;
- quantos registros/defaults foram enviados (**sempre 0**).

## 5. Revisar sugestões

Em **Revisão de sugestões** você vê abas:

- **Pendentes** — aguardando decisão.
- **Parciais** — aprovadas em parte, precisando de ajuste.
- **Aprovadas** — prontas para aplicação (se você tiver permissão).
- **Rejeitadas** — descartadas; podem ser reabertas pela edição.
- **Todas**.

Cada cartão mostra tipo, tabela, coluna alvo (quando houver), versão, número de
revisões, confiança, descrição e justificativa.

### 5.1 Editar (inclusive após aprovação parcial)

1. Clique em **Editar**.
2. Ajuste tabela, tipo, coluna, descrição, justificativa, confiança ou SQL
   candidato.
3. Escreva um comentário explicando o ajuste (vai para o histórico).
4. Clique em **Salvar e reabrir**.

O que acontece:
- a versão aumenta (`v2`, `v3`...);
- uma cópia imutável vai para o histórico;
- a sugestão volta para **Pendente** para nova decisão;
- o status anterior fica registrado.

### 5.2 Aprovar parcialmente

Clique em **Parcial** e descreva o que foi aprovado e o que precisa de ajuste. A
sugestão fica em **Parciais** até ser editada e reenviada para decisão.

### 5.3 Aprovar ou rejeitar

- **Aprovar** registra a decisão. Nada é aplicado automaticamente.
- **Rejeitar** encerra a proposta. Para retomar, clique em **Reabrir** e edite.

## 6. Aplicar no banco (perfil técnico)

Só aparece para **desenvolvedor** ou **administrador**, e apenas para sugestões
aprovadas. O fluxo é:

1. Clique em **Aplicar no BD**.
2. Leia a prévia do SQL, os bloqueios e os avisos.
3. Confirme.

Regras:
- o SQL é gerado pelo servidor, não pela IA;
- `CREATE INDEX` e `COMMENT ON` são os tipos suportados automaticamente;
- a operação exige `DB_WRITE_ENABLED=true` e `WRITE_DATABASE_URL` configurada;
- toda tentativa fica em **auditoria** (`apply_logs`);
- se falhar, o erro aparece no cartão e na auditoria.

Se o botão não aparecer, verifique a persona e se a escrita está habilitada.

## 7. Privacidade: o que a IA vê

A IA vê somente:

- nome do schema e das tabelas;
- nomes, tipos, nulabilidade e PK das colunas;
- FKs e índices;
- uma marcação `sensitive` + categoria para colunas como `cpf`, `email`,
  `telefone`, `senha`, `prontuario`, `cartao`, `matricula` etc.

A IA **nunca** vê:

- linhas/registros;
- valores de colunas;
- valores padrão (`DEFAULT`);
- senhas, tokens, chaves ou hashes;
- tabelas do armazenamento interno do GenomAI.

Para provar, use **Metadados da IA** ou a rota `/api/v1/privacy/ai-payload`.

## 8. Perguntas frequentes

**As sugestões ficam salvas onde?**
No banco interno do GenomAI (`APP_DATABASE_URL`). Em desenvolvimento pode ser um
SQLite no servidor; em produção deve ser PostgreSQL no schema `genomai_app`.
Nunca ficam apenas no navegador.

**A IA pode alterar o banco sozinha?**
Não. Ela só propõe. Aplicar exige aprovação humana e persona técnica.

**Aprovar já aplica?**
Não. Aprovar registra a decisão. Aplicar é uma ação separada e auditada.

**Posso editar uma sugestão já aplicada?**
Não. O histórico fica preservado; para uma nova mudança, crie outra sugestão.

**Por que a tabela `suggestions` não aparece no catálogo?**
Porque é uma tabela interna do GenomAI (ou uma sobra legada no Supabase). Ela é
excluída para a IA não analisar o próprio armazenamento.

**Onde vejo o histórico de uma edição?**
No próprio modal de edição, em **Histórico de versões**.
