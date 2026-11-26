# Documentação do GenomAI

Este diretório é a fonte de verdade para três públicos diferentes. Cada guia é
autossuficiente, mas todos compartilham os mesmos invariantes de segurança.

## Comece por aqui

| Se você é... | Leia | Para quê |
|---|---|---|
| Analista de dados / product owner | [Guia do analista](guia-analista-dados.md) | Entender o fluxo, revisar, editar e aprovar sugestões. |
| Desenvolvedor / SRE | [Guia do desenvolvedor](guia-desenvolvedor.md) | Rodar, configurar, estender, testar e implantar. |
| Agente de IA / integração | [Guia para IA](guia-ia.md) | Contrato de dados, endpoints, invariantes e exemplos. |
| Arquiteto | [Visão geral](visao-geral-arquitetura.md) | Decisões, fluxo de dados e limites. |
| Segurança / privacidade | [Privacidade da IA](seguranca-privacidade-ia.md) | Prova técnica do épico de dados sensíveis. |
| DBA | [Persistência e isolamento](persistencia-e-isolamento.md) | Schemas, roles, migração e backup. |

## Referências

- [Referência da API](api-reference.md) — todos os endpoints, personas e erros.
- [Mapa do código](mapa-do-codigo.md) — papel de cada arquivo e onde mexer.
- [OpenAPI exportado](openapi.json) — contrato legível por máquina.
- [Personas e permissões](personas-permissoes.md) — matriz e integração com auth.
- [Integração com outros bancos e IAs](integracao-outros-bancos-e-ias.md) — como
  portar o projeto para MySQL/MariaDB, SQL Server, Oracle ou outro provedor.
- [Operação e testes](operacao-e-testes.md) — comandos, troubleshooting, checklist.
- [Decisões de arquitetura](decisoes-arquiteturais.md) — ADRs.

## Invariantes que valem para todos os guias

1. O banco analisado é acessado por uma role **somente leitura**.
2. Sugestões, revisões e auditorias ficam no **armazenamento interno**, em
   conexão e schema separados.
3. A IA recebe **somente** o payload de `build_safe_schema_context`.
4. A IA **nunca** executa SQL e **nunca** recebe linhas, defaults ou segredos.
5. Aplicar uma mudança exige persona `desenvolvedor`/`administrador`, sugestão
   aprovada, `DB_WRITE_ENABLED=true` e SQL gerado pelo servidor.
6. Toda aplicação é auditada em `apply_logs`; todo envio à IA é auditado em
   `ai_metadata_audits` por hash/contagens.
7. Tabelas internas do GenomAI são excluídas da análise por
   `ANALYSIS_EXCLUDED_TABLES`.
