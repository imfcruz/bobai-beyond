# Rastreabilidade entre proposta e protótipo

Esta matriz compara o escopo descrito na proposta acadêmica com o estado executável do repositório. “Atendido no MVP” significa demonstrável com dados sintéticos; não significa prontidão bancária de produção.

| Compromisso da proposta | Implementação no projeto | Estado |
|---|---|---|
| Orquestrador de contexto e intenção | `OrchestratorAgent` constrói o contexto, seleciona especialistas e usa o módulo interno `IntentionAgent` quando o caso pede aprofundamento | Atendido no MVP |
| Agente de fraude independente | `FraudAgent` executa avaliação própria e participa sempre da triagem | Atendido no MVP |
| Agente de inconsistência | `InconsistencyAgent` avalia sequência, mudança de limite, dispositivo e beneficiário quando há contexto incomum | Atendido no MVP |
| Agente comportamental | `BehavioralAgent` compara a operação com o histórico sintético do cliente | Atendido no MVP |
| Agente de risco e segurança | `RiskAgent` consolida resultados selecionados, detecta divergência e aplica regra absoluta | Atendido no MVP |
| Orquestração não rígida | Fraude + Comportamental formam o plano mínimo; Intenção + Inconsistência entram como segunda opinião contextual | Atendido no MVP |
| Security Gateway não tratado como sexto agente | `SecurityGateway` permanece camada determinística posterior ao motor de decisão | Atendido no MVP |
| Liberação, confirmação, verificação e revisão humana adaptativas | `DecisionEngine`, gateway e máquina de estados conduzem jornadas conforme score e política | Atendido no MVP |
| Falha nunca libera automaticamente | Timeout/erro mantém a transação pendente; falha da LLM usa regras e registra fallback | Atendido e testado |
| Participação humana em casos críticos | Ambiente do funcionário permite revisar transferências e pedidos de limite; IDs de IA não podem assinar revisão humana | Atendido no MVP |
| Simulação bancária integrada | Contas, Pix no débito/crédito, cartões, limite, liquidação, extrato e contatos operam sobre SQLite local | Atendido no MVP |
| Interface do cliente | Dashboard responsivo, troca de conta, cartão 3D, contatos, extrato e tutorial guiado | Atendido no MVP |
| Painel de auditoria e métricas | Visão geral, clientes, auditoria, métricas e cenários de demonstração | Atendido no MVP |
| Cenários A, B e C | Seeds e testes representam operação normal, incomum e possível engenharia social | Atendido e testado |
| Inferência com tecnologia IBM | Cliente do IBM Bob via modo não interativo, com chave somente no `.env` e fallback seguro | Integrado; validação ao vivo bloqueada por orçamento de Bobcoins |
| Autenticação e controle de acesso reais | Não há login, sessão ou autorização por papel | Fora do MVP / limitação declarada |
| Escala, alta disponibilidade e integrações bancárias reais | Persistência SQLite e execução local com dados sintéticos | Fora do MVP / evolução futura |

## Evidências de validação

- `210` testes de backend aprovados.
- `79` testes de frontend aprovados.
- build TypeScript/Vite concluído sem erros.
- jornadas principais inspecionadas em execução local: cliente, cartão, troca de perfil, visão geral, clientes, auditoria e métricas.
- `backend/.env` ignorado pelo Git; chave não aparece em argumentos, documentação ou logs.

## Leitura honesta do estado

O protótipo está fiel ao núcleo funcional da proposta e pronto para demonstração acadêmica local. Não é correto apresentá-lo como solução bancária pronta para produção. A autenticação real, a avaliação estatística com base ampla, a infraestrutura de produção e a validação ao vivo do enriquecimento IBM Bob continuam sendo limitações explícitas.
