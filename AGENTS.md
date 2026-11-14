# AGENTS.md — Documentação dos Cinco Agentes

> Simulação acadêmica local. Todos os dados são sintéticos.
> Os agentes **não** têm acesso a sistemas bancários reais.

---

## Visão geral do contrato de agente

Todos os agentes implementam a interface `BaseAgent` definida em `backend/app/agents/base.py`:

```python
class BaseAgent:
    async def analyze(self, ctx: AgentContext) -> AgentResult: ...
```

**`AgentContext`** — snapshot imutável de todos os dados relevantes da operação:
- Dados da transação (valor, finalidade, dispositivo, beneficiário)
- Histórico comportamental do cliente (avg, max, horários típicos)
- Eventos contextuais recentes (últimas 24h)
- `analysis_id` — ID único para rastreabilidade por execução

**`AgentResult`** — saída estruturada de cada agente:

| Campo | Tipo | Descrição |
|---|---|---|
| `agent_name` | str | Nome do agente |
| `risk_score` | float | Score de risco [0.0–1.0] |
| `risk_level` | AgentRiskLevel | `low/medium/high/critical` |
| `recommended_action` | AgentRecommendedAction | `approve/request_confirmation/...` |
| `confidence` | float | Confiança da decisão [0.0–1.0] |
| `flags` | list[str] | Sinais detectados |
| `reasoning` | str | Justificativa em linguagem natural |
| `explanation` | str | Explicação para o usuário |
| `detected_signals` | list[str] | Sinais detectados (LLM) |
| `mode` | AgentMode | `RULES_MODE` ou `AI_MODE` |
| `model_used` | str | Modelo utilizado (`mock-rules` ou nome do LLM) |
| `execution_time_ms` | float | Tempo de execução em milissegundos |
| `status` | AgentStatus | `success/failure/timeout` |
| `evidence` | dict | Evidências estruturadas |

---

## Agente 1 — Orquestrador de Contexto e Intenção

**Arquivo:** `backend/app/agents/orchestrator_agent.py`

### Responsabilidade

Construir o `AgentContext`, identificar se a operação exige aprofundamento e coordenar em paralelo somente os especialistas necessários. Fraude e Comportamental formam a triagem mínima; Intenção e Inconsistência são ativados quando há contexto incomum. A consolidação pertence ao RiskAgent.

### Entradas

- Dados de domínio: `Transaction`, `Client`, `Beneficiary`, `BehavioralHistory`, lista de `ContextualEvent`
- Função `build_context_from_domain()` converte domínio → `AgentContext`

### Saídas

- `(AgentResult final, dict[str, AgentResult])` — resultado consolidado + mapa por agente

### Permissões

- ✅ Ler dados de domínio
- ✅ Construir AgentContext
- ✅ Coordenar execução paralela
- ❌ Modificar transações
- ❌ Alterar políticas
- ❌ Mover valores

### Tratamento de falhas

- `asyncio.TimeoutError` (limite configurado por `AGENT_PIPELINE_TIMEOUT_SECONDS`) → capturado em `BankService` → transação permanece `PENDING`
- `Exception` genérica → idem — **nunca aprovação automática**

---

## Agente 2 — Agente de Fraude

**Arquivo:** `backend/app/agents/fraud_agent.py`

### Responsabilidade

Análise **stand-alone** de indicadores clássicos de fraude. Execução paralela e independente dos demais. Combina heurísticas determinísticas (RULES_MODE) com análise LLM opcional (AI_MODE).

### Entradas

`AgentContext` com foco em:
- `is_new_recipient` — beneficiário novo
- `amount` vs `avg_transfer`, `max_transfer` — comparação com histórico
- `purpose` — finalidade da transferência
- `device_recognized` — reconhecimento do dispositivo
- `account_age_days` — idade da conta

### Heurísticas (RULES_MODE)

| Flag detectado | Condição | Impacto no score |
|---|---|---|
| `new_recipient_high_value` | Beneficiário novo + valor > 2× avg | +0.35 |
| `high_value_vs_avg` | Valor > 5× avg | +0.25 |
| `extreme_value_vs_avg` | Valor > 15× avg | +0.45 |
| `social_engineering_keyword` | Palavras: `urgente`, `seguro`, `bloqueado`, `banco`, `falha`, etc. | +0.55 |
| `device_not_recognized_high_value` | Dispositivo desconhecido + valor > max | +0.35 |
| `new_account_high_value` | Conta < 90 dias + valor > max histórico | +0.30 |
| `full_social_engineering_sequence` | Múltiplos sinais combinados | +0.60 |

### Saída

`AgentResult(risk_score=0.0–1.0, flags=[...], confidence=0.85, mode=RULES_MODE ou AI_MODE)`

### Peso na consolidação

**35%** do score final do RiskAgent quando todos os especialistas participam. Os pesos presentes são normalizados quando a triagem é reduzida.

### Modelo utilizado

- RULES_MODE: `mock-rules` (determinístico, sem IA)
- AI_MODE: provedor IBM configurado via `LLM_PROVIDER` (`bob` ou `watsonx`)

### Prompts de sistema

Definidos em `backend/app/agents/prompts/__init__.py` — `FRAUD_AGENT_SYSTEM_PROMPT`.
O prompt instrui o LLM a responder em JSON estruturado com `risk_level`, `explanation`, `detected_signals`.

### Tratamento de falhas

Se a LLM falhar ou expirar: usa resultado heurístico local, registra `status=FALLBACK_USED` e `mode=RULES_MODE`.

---

## Agente 3 — Agente de Inconsistência

**Arquivo:** `backend/app/agents/inconsistency_agent.py`

### Responsabilidade

Detectar **padrões de sequência suspeita** nos eventos contextuais recentes — indicadores de ataque coordenado ou manipulação sequencial.

### Entradas

`AgentContext` com foco em:
- `recent_events` — timeline de eventos das últimas 24h
- `recent_limit_change` — alteração de limite recente
- `is_new_recipient` — beneficiário novo
- `device_recognized` — dispositivo conhecido
- `purpose` — finalidade da transferência
- `amount` — valor

### Heurísticas (RULES_MODE)

| Flag detectado | Condição | Impacto no score |
|---|---|---|
| `recent_limit_change` | Limite alterado nas últimas 2h + transferência | +0.45 |
| `unknown_device_new_recipient` | Dispositivo desconhecido + beneficiário novo | +0.40 |
| `missing_purpose_high_value` | Finalidade vazia + valor > 5× avg | +0.35 |
| `suspicious_sequence_full` | Limite + beneficiário novo + transferência em sequência | +0.60 |
| `short_purpose_high_value` | Finalidade < 5 chars + valor alto | +0.20 |

### Saída

`AgentResult(risk_score=0.0–1.0, flags=[...], confidence=0.80, mode=RULES_MODE ou AI_MODE)`

### Peso na consolidação

**25%** do score final quando participa da análise completa.

### Prompts de sistema

`INCONSISTENCY_AGENT_SYSTEM_PROMPT` — análise de sequência de eventos.

### Tratamento de falhas

Idem ao Agente de Fraude — fallback para heurísticas locais.

---

## Agente 4 — Agente Comportamental

**Arquivo:** `backend/app/agents/behavioral_agent.py`

### Responsabilidade

Detectar **desvios em relação ao padrão histórico** do cliente — comportamentos que se afastam significativamente do perfil estabelecido.

### Entradas

`AgentContext` com foco em:
- `amount` vs `avg_transfer`, `max_transfer`, `min_transfer`
- `avg_monthly_tx` — frequência histórica
- `typical_hours` — horários típicos do cliente
- `is_known_beneficiary` — histórico com o beneficiário
- `account_age_days` — maturidade da conta
- `risk_profile` — perfil de risco cadastrado

### Heurísticas (RULES_MODE)

| Flag detectado | Condição | Impacto no score |
|---|---|---|
| `above_max_historical` | Valor > max histórico | +0.30 |
| `extreme_above_max` | Valor > 2× max histórico | +0.50 |
| `well_above_avg` | Valor > 4× média | +0.25 |
| `extreme_above_avg` | Valor > 10× média | +0.45 |
| `new_beneficiary_established_account` | Beneficiário novo + conta > 365 dias | +0.20 |
| `spike_on_low_risk_account` | Perfil `low` + valor > 3× avg | +0.25 |

### Saída

`AgentResult(risk_score=0.0–1.0, flags=[...], confidence=0.75, mode=RULES_MODE ou AI_MODE)`

### Peso na consolidação

**20%** do score final do RiskAgent.

### Prompts de sistema

`BEHAVIORAL_AGENT_SYSTEM_PROMPT` — análise de desvio comportamental.

### Tratamento de falhas

Idem — fallback para heurísticas locais.

---

## Especialista interno de Intenção — parte do Agente 1

**Arquivo:** `backend/app/agents/intention_agent.py`

O conceito de intenção pertence ao Orquestrador de Contexto e Intenção descrito na proposta. No código, ele foi isolado em um módulo interno para manter responsabilidade única e permitir testes independentes. É acionado quando valor, finalidade, destinatário, dispositivo ou sequência de eventos pedem segunda opinião. Seu peso máximo é **20%** e o texto informado pelo cliente é sempre tratado como dado, nunca como instrução.

---

## Agente 5 — Agente de Risco e Segurança

**Arquivo:** `backend/app/agents/risk_agent.py`

### Responsabilidade

Consolidar os especialistas selecionados, detectar divergências significativas e aplicar regras absolutas (`hard_rules`) que **não podem ser contornadas por LLM**.

### Entradas

- `AgentContext` — contexto da operação
- `sub_results: list[AgentResult]` — resultados dos especialistas selecionados

### Consolidação ponderada

```python
weighted_score = (
    fraud_score    × 0.35 +
    inconsistency  × 0.25 +
    behavioral     × 0.20 +
    intention      × 0.20
)
```

O cálculo divide pela soma dos pesos efetivamente presentes; portanto, a triagem mínima e a análise completa permanecem comparáveis.

Flags: união de todos os flags dos sub-agentes.

### Hard rules (invioláveis)

| Condição | Ação | Justificativa |
|---|---|---|
| `amount > R$ 50.000` | `hard_block=True` · score=1.0 | Limite máximo absoluto da simulação |

Hard rules são verificadas **antes** e **depois** da consolidação — independente do LLM.

### Detecção de divergência

```python
spread = max(sub_scores) - min(sub_scores)
if spread > 0.40:
    divergence_detected = True
```

Divergência sinalizada no `AgentResult` e propagada ao `DecisionEngine`.

### Saídas

```python
AgentResult(
    risk_score=0.0–1.0,    # score consolidado
    flags=[...],            # união de todos os flags
    confidence=0.90,
    mode=RULES_MODE | AI_MODE,
    execution_time_ms=...,
)
```

### Permissões especiais

- ✅ Aplicar hard rules (score máximo, bloqueio)
- ✅ Detectar divergência entre agentes
- ❌ Alterar políticas do Security Gateway
- ❌ Modificar transações diretamente

### Tratamento de falhas

Se qualquer sub-agente falhar e retornar resultado parcial, o RiskAgent usa os resultados disponíveis. Se nenhum sub-resultado estiver disponível, score conservador (0.85) é aplicado.

---

## Observações gerais sobre IA

### RULES_MODE vs AI_MODE

| Aspecto | RULES_MODE | AI_MODE |
|---|---|---|
| Dependência externa | Nenhuma | LLM configurado |
| Determinismo | Totalmente determinístico | Não determinístico |
| Velocidade | < 10ms por agente | Depende do provedor LLM |
| Auditabilidade | Total — lógica explícita | Parcial — LLM como "caixa preta" |
| Modo padrão | ✅ (LLM_PROVIDER=mock) | Requer configuração |

### O LLM não tem acesso a:

- Security Gateway (não pode alterar políticas)
- Banco de dados (somente leitura via AgentContext)
- DecisionEngine (não pode modificar limiares)
- Outras transações (apenas a transação corrente)
- Credenciais ou dados externos

### Rastreabilidade

Cada execução de agente registra `model_used`, `mode`, `execution_time_ms` e `analysis_id` no `AgentResult`, que é persistido em `risk_analyses` e referenciado em `audit_logs`.
