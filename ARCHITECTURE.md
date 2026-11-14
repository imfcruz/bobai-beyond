# ARCHITECTURE.md — Arquitetura Técnica do Adaptive Security MVP

> Simulação acadêmica local. Todos os dados são sintéticos.
> Nenhuma operação financeira real é executada.

---

## 1. Visão Geral

Este documento descreve a arquitetura técnica do **Adaptive Security MVP**, prova de conceito acadêmica de segurança adaptativa para operações financeiras digitais, desenvolvida para o IBM AI Experiential Learning Lab.

A solução demonstra como uma **arquitetura multiagente** pode analisar o **contexto completo** de uma operação financeira — e não apenas a validade técnica — para identificar situações de possível engenharia social.

```
┌────────────────────────────────────────────────────────────────────┐
│                     INTERFACE DO CLIENTE                           │
│          React 19 + TypeScript + Vite  ← :5173                    │
│                                                                    │
│  Dashboard │ Transferência │ Análise │ Cenários │ Auditoria        │
│  Confirmação │ Revisão Humana │ Métricas                           │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ HTTP REST (axios)
┌─────────────────────────────▼──────────────────────────────────────┐
│                    FASTAPI BACKEND  :8000                          │
│                Python 3.12 + Uvicorn                               │
│                                                                    │
│  POST /api/v1/transactions/  →  BankService.initiate_transfer()    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │           AGENTE ORQUESTRADOR (1)                            │  │
│  │  build_context_from_domain() · run_full_pipeline()           │  │
│  └──────┬─────────────────┬──────────────────┬──────────────────┘  │
│         │  seleção adaptativa + asyncio.gather                   │
│  ┌──────▼──────┐  ┌────────▼──────┐  ┌──────▼──────┐             │
│  │  FRAUDE (2) │  │INCONSISTÊNCIA │  │COMPORTAMENTAL│             │
│  │  (sempre)   │  │ (contextual)  │  │ (sempre) (4) │             │
│  └──────┬──────┘  └────────┬──────┘  └──────┬──────┘             │
│         │         INTENÇÃO (apoio interno do agente 1)            │
│         └─────────────────┴──────────────────┘                    │
│                            │ AgentResult[] (sub_results)           │
│              ┌─────────────▼────────────┐                         │
│              │  RISCO E SEGURANÇA (5)   │                         │
│              │  Consolidação ponderada  │                         │
│              │  Hard rules (>R$50k)     │                         │
│              └─────────────┬────────────┘                         │
│                            │ AgentResult final                     │
│              ┌─────────────▼────────────┐                         │
│              │   DECISION ENGINE        │                         │
│              │  score → nível → ação    │                         │
│              └─────────────┬────────────┘                         │
│                            │ Decision                              │
│              ┌─────────────▼────────────┐                         │
│              │   SECURITY GATEWAY       │                         │
│              │  Política · Rastreabilidade│                        │
│              └───┬──────┬──────┬────────┘                         │
│               RELEASE VERIFY ESCALATE/BLOCK                       │
│                                                                    │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────────────┐    │
│  │ SIMULAÇÃO    │  │  AUDITORIA  │  │  INTEGRAÇÃO LLM       │    │
│  │ BANCÁRIA     │  │  LOGS       │  │  mock/bob/watsonx     │    │
│  │ (sintética)  │  │             │  │                       │    │
│  └──────────────┘  └─────────────┘  └───────────────────────┘    │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              BANCO SQLite (aiosqlite)                       │  │
│  │  clients · beneficiaries · transactions · risk_analyses     │  │
│  │  contextual_events · behavioral_history · audit_logs        │  │
│  └─────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. Os Cinco Agentes

### 2.1 Agente Orquestrador de Contexto e Intenção

- **Arquivo:** `backend/app/agents/orchestrator_agent.py`
- **Responsabilidade:** Construir o `AgentContext`, selecionar os especialistas necessários e coordená-los em paralelo via `asyncio.gather`. Fraude e Comportamental são a triagem mínima; Intenção e Inconsistência entram diante de contexto incomum. Não movimenta valores nem decide sozinho.
- **Método principal:** `run_full_pipeline(ctx)` → `(AgentResult, dict[str, AgentResult])`
- **Permissões:** Somente coordenar. Sem autorização para modificar dados ou movimentar valores.
- **Falha:** Se `asyncio.gather` falhar → transação permanece `PENDING`. Nunca aprovado automaticamente.

### 2.2 Agente de Fraude

- **Arquivo:** `backend/app/agents/fraud_agent.py`
- **Execução:** Paralela — independente dos demais via `asyncio.gather`
- **Heurísticas:**
  1. Beneficiário novo + valor elevado
  2. Valor muito acima da média histórica (flags `high_value_vs_avg` e `extreme_value_vs_avg`)
  3. Palavras-chave de engenharia social na finalidade (`seguro`, `urgente`, `banco bloqueou`, etc.)
  4. Dispositivo não reconhecido + valor alto (`device_not_recognized_high_value`)
  5. Conta nova + valor acima do máximo histórico (`new_account_high_value`)
- **Peso na consolidação do RiskAgent:** 35%
- **Saída:** `AgentResult(risk_score, flags, reasoning, confidence=0.85, mode)`

### 2.3 Agente de Inconsistência

- **Arquivo:** `backend/app/agents/inconsistency_agent.py`
- **Execução:** Paralela com Fraude e Comportamental
- **Padrões detectados:**
  1. Alteração de limite recente → transferência imediata (`recent_limit_change`)
  2. Dispositivo não reconhecido + beneficiário novo (`unknown_device_new_recipient`)
  3. Finalidade ausente com valor alto (`missing_purpose_high_value`)
  4. Sequência suspeita: limite + novo beneficiário + transferência
  5. Finalidade muito curta ou genérica para valor elevado
- **Peso na consolidação:** 25%

### 2.4 Agente de Intenção

- **Arquivo:** `backend/app/agents/intention_agent.py`
- **Execução:** Paralela quando o orquestrador identifica necessidade de aprofundamento contextual.
- **Responsabilidade:** Verificar coerência entre finalidade declarada, valor, destinatário e contexto, tratando o texto como dado e nunca como ordem.
- **Peso na consolidação:** 20%

### 2.5 Agente Comportamental

- **Arquivo:** `backend/app/agents/behavioral_agent.py`
- **Execução:** Paralela
- **Desvios detectados:**
  1. Valor acima do máximo histórico pessoal (`above_max_historical`)
  2. Valor muito acima (2x do máximo, `extreme_above_max`)
  3. Valor muito acima da média (4x e 10x, `well_above_avg`, `extreme_above_avg`)
  4. Beneficiário nunca utilizado em conta com histórico longo (`new_beneficiary_established_account`)
  5. Spike em conta de baixo risco (`spike_on_low_risk_account`)
- **Peso na consolidação:** 20%

### 2.6 Agente de Risco e Segurança

- **Arquivo:** `backend/app/agents/risk_agent.py`
- **Responsabilidade:** Consolidar os resultados dos especialistas selecionados, normalizando os pesos disponíveis, e aplicar regras absolutas (`hard_rules`).
- **Hard rules:**
  - Valor > R$ 50.000 → `hard_block=True` → score forçado para 1.0 → `BLOCK`
- **Pesos máximos:** Fraude 35% + Inconsistência 25% + Comportamental 20% + Intenção 20%. Quando um especialista não é acionado, os pesos presentes são normalizados.
- **Detecção de divergência:** Se spread entre agentes > 0.40 → `divergence_detected=True`
- **Saída:** `AgentResult` com score final + flags consolidados + `execution_time_ms`

---

## 3. Fluxo de Dados

```
1. Usuário seleciona cliente + beneficiário + valor + finalidade (frontend)
2. Frontend envia POST /api/v1/transactions/

3. BankService.initiate_transfer():
   ├── Valida valor (Decimal, > 0, ≤ R$ 999.999.999,99)
   ├── Verifica idempotency_key (evita duplicação)
   ├── Valida cliente, beneficiário, limite
   ├── Cria Transaction (PENDING) + ContextualEvent + RiskAnalysis (IN_PROGRESS)
   └── build_context_from_domain() → AgentContext

4. asyncio.wait_for(OrchestratorAgent.run_full_pipeline(), timeout configurável):
   ├── Seleciona Fraude + Comportamental como triagem mínima
   ├── Adiciona Intenção + Inconsistência quando o contexto é incomum
   ├── asyncio.gather(especialistas selecionados)  ← PARALELO
   └── RiskAgent.analyze(sub_results=[...])  ← aguarda os selecionados

5. DecisionEngine.make_decision(risk_result, sub_results):
   ├── Detecta divergência (spread > 0.40)
   └── score → RiskLevel → RecommendedAction → TransactionStatus

6. SecurityGateway.evaluate(decision):
   ├── Verifica se ação é permitida para o nível de risco
   ├── Ação não permitida → forçado para ação mais conservadora
   └── GatewayResponse(authorized, final_status, requires_*)

7. BankService persiste:
   ├── RiskAnalysis: resultado JSON de cada agente + flags + policy_version
   ├── Transaction: novo status + risk_score + risk_level
   └── AuditLog: rastreabilidade completa (correlation_id, execution_time_ms, ...)

8. Frontend exibe:
   ├── Resultado: liberada / confirmação requerida / escalada / bloqueada
   ├── Score de risco (barra visual)
   ├── Flags detectados
   ├── Resultado individual de cada agente (expansível)
   └── Reasoning do Security Gateway
```

---

## 4. Motor de Decisão

**Arquivo:** `backend/app/services/decision_engine.py`
**Versão da política:** `v1.0.0` (rastreada em todos os registros)

| Risk Score | Nível | Ação | Status da Transação |
|---|---|---|---|
| < 0.30 | `low` | `APPROVE` | `RELEASED` |
| 0.30–0.59 | `medium` | `REQUEST_CONFIRMATION` | `AWAITING_CONFIRMATION` |
| 0.60–0.84 | `high` | `REQUEST_CONFIRMATION` | `AWAITING_CONFIRMATION` |
| ≥ 0.85 | `critical` | `ESCALATE_TO_HUMAN` | `HUMAN_REVIEW_PENDING` |
| `hard_block=True` | `critical` | `BLOCK` | `REJECTED` |

**Detecção de divergência:** Quando dois ou mais agentes discordam fortemente (spread > 0,40), o motor sinaliza `divergence_detected=True` e aplica a política mais conservadora.

Limiares configuráveis via variáveis de ambiente:
```
RISK_THRESHOLD_LOW=0.3
RISK_THRESHOLD_MEDIUM=0.6
RISK_THRESHOLD_HIGH=0.85
```

---

## 5. Security Gateway

**Arquivo:** `backend/app/services/security_gateway.py`

O Gateway **não é um agente** — é uma camada de controle de política sem LLM.

**Regras de ação permitida por nível:**

| Nível | Ações permitidas |
|---|---|
| `low` | Somente `APPROVE` |
| `medium` | Somente `REQUEST_CONFIRMATION` |
| `high` | `REQUEST_CONFIRMATION` ou `ESCALATE_TO_HUMAN` |
| `critical` | `ESCALATE_TO_HUMAN` ou `BLOCK` |

**Garantias de segurança:**
1. `BLOCK` → `authorized=False` — transação **nunca** prossegue
2. `ESCALATE_TO_HUMAN` → `requires_human_review=True`
3. Ação não permitida para o nível → registrada como `unauthorized_action_attempted=True` + forçada para ação conservadora
4. Falha no pipeline → transação permanece `PENDING` — **nunca aprovada automaticamente**
5. Revisão humana só é aceita com `reviewer_id` sem identificadores de IA (`bot`, `ai`, `agent`, etc.)

---

## 6. Estado de Transações

State machine com transições explícitas (`VALID_TRANSITIONS`):

```
PENDING
  ├── → UNDER_VERIFICATION
  ├── → AWAITING_CONFIRMATION
  ├── → HUMAN_REVIEW_PENDING
  ├── → ESCALATED_TO_HUMAN
  ├── → RELEASED
  └── → REJECTED

AWAITING_CONFIRMATION
  ├── → RELEASED      (confirmação aceita)
  └── → REJECTED      (confirmação recusada / coerção detectada)

HUMAN_REVIEW_PENDING / ESCALATED_TO_HUMAN
  ├── → HUMAN_APPROVED
  └── → HUMAN_REJECTED

RELEASED / REJECTED / HUMAN_APPROVED / HUMAN_REJECTED / BLOCKED
  └── (terminais — nenhuma transição adicional permitida)
```

---

## 7. Persistência

**Tecnologia:** SQLite via SQLAlchemy 2.x async + aiosqlite

| Tabela | Descrição |
|---|---|
| `clients` | 3 clientes sintéticos com perfil de risco e histórico |
| `beneficiaries` | 10 contatos por cliente (conhecidos, favoritos, novos e suspeitos) |
| `transactions` | Cada transferência com `idempotency_key` e state machine |
| `risk_analyses` | Resultado completo do pipeline: JSON por agente + divergência |
| `contextual_events` | Timeline de eventos (login, limite, cadastro de beneficiário, etc.) |
| `behavioral_history` | Estatísticas históricas do cliente (avg, max, horários típicos) |
| `audit_logs` | Trilha completa: componente, ação, resultado, reasoning, correlation_id |

**Seed determinístico:** 3 clientes · 30 contatos · 3 transações seed · 3 análises seed · 10+ eventos contextuais. IDs estáveis entre resets.

---

## 8. Integração com LLM

**Arquivo:** `backend/app/services/llm_client.py`

Padrão de abstração: Factory + interface `BaseLLMClient`.

| Provider | Modo dos agentes | Observação |
|---|---|---|
| `mock` | `RULES_MODE` — heurísticas determinísticas | Padrão — sem dependências externas |
| `watsonx` | `AI_MODE` — IBM Granite | Requer `LLM_API_KEY` + `WATSONX_PROJECT_ID` |

Com provedor real: score = heurística × 0.70 + LLM × 0.30.

O sistema funciona **completamente** com `mock` — todos os 204 testes usam mock.

---

## 9. Interface do Cliente

**Tecnologia:** React 19 + TypeScript ~7.0 + Vite 8.3 + react-router-dom 7.x

| Rota | Tela | Funcional? |
|---|---|---|
| `/` | Dashboard: cliente, saldo, histórico | ✅ Sim |
| `/transfer` | Formulário de transferência | ✅ Sim |
| `/analysis` | Resultado do pipeline por agente | ✅ Sim |
| `/confirm` | Confirmação contextual (fase 2) | ✅ Sim |
| `/scenarios` | 3 cenários pré-configurados A/B/C | ✅ Sim |
| `/audit` | Painel de auditoria completo | ✅ Sim |
| `/human-review` | Interface de revisão humana | ✅ Sim |
| `/metrics` | Painel de métricas calculadas | ✅ Sim |

---

## 10. Princípios de Design

### Princípio do menor privilégio

| Componente | Analisa | Recomenda | Executa |
|---|---|---|---|
| Agente de Fraude | ✅ | ✅ (score+flags) | ❌ |
| Agente de Inconsistência | ✅ | ✅ (score+flags) | ❌ |
| Agente Comportamental | ✅ | ✅ (score+flags) | ❌ |
| Agente Orquestrador | Coordena | ✅ (agrega) | ❌ |
| Agente de Risco | ✅ | ✅ (consolida) | ❌ (hard rules apenas) |
| Decision Engine | ❌ | ✅ (ação final) | ❌ |
| Security Gateway | ❌ | ❌ | ✅ (aplica política) |
| LLM | ✅ | ✅ (score parcial) | ❌ (sem acesso ao Gateway) |

### Fail-safe

- Pipeline timeout → `PENDING` (nunca `RELEASED`)
- Exceção no agente → pipeline falha → `PENDING`
- Ação não permitida no Gateway → mais conservadora + `unauthorized_action_attempted=True`
- Hard block (>R$50k) → `BLOCK` independente do LLM

### Auditabilidade total

Toda decisão do pipeline registra em `audit_logs`:
- `component` + `agent_name`
- `event` + `result` + `reasoning`
- `risk_score` + `flags`
- `correlation_id` — rastreia toda a operação
- `policy_version` — versão da política aplicada
- `execution_time_ms` — tempo de execução
- `agent_contributions` — peso de cada agente na decisão

---

## 11. Stack Técnica

| Camada | Tecnologia | Versão |
|---|---|---|
| Backend framework | FastAPI | 0.115+ |
| Servidor ASGI | Uvicorn | 0.34+ |
| Validação | Pydantic v2 | 2.10+ |
| ORM | SQLAlchemy async | 2.0+ |
| Banco de dados | SQLite + aiosqlite | — |
| Logging | structlog | 24.4+ |
| Frontend | React + TypeScript | 19 + ~7.0 |
| Build tool | Vite | 8.3+ |
| HTTP client (FE) | axios | 1.x |
| Roteamento (FE) | react-router-dom | 7.x |
| Testes backend | pytest + pytest-asyncio | 204 testes |
| Testes frontend | Vitest | 79 testes |
