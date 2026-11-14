# TEST_REPORT.md — Relatório de Testes

> Adaptive Security MVP — IBM AI Experiential Learning Lab
> Data de execução: 13/11/2026

---

## Resumo executivo

| Categoria | Resultado |
|---|---|
| Backend (pytest) | ✅ **210 passed**, 0 failed |
| Frontend (Vitest) | ✅ **79 passed**, 0 failed |
| TypeScript (`tsc --noEmit`) | ✅ **0 erros** |
| Build de produção (`vite build`) | ✅ **Sem erros** (`475,75 kB JS`, `17,44 kB CSS`) |
| Credenciais expostas | ✅ **Nenhuma encontrada** |
| APIs bancárias reais | ✅ **Nenhuma utilizada** |
| Operações financeiras reais | ✅ **Impossível pelo design** |

---

## 1. Testes do Backend

**Comando:** `cd backend && .venv/bin/pytest tests/ -q --tb=short`
**Resultado:** `210 passed`

### Arquivos de teste

| Arquivo | Testes | Status | O que cobre |
|---|---|---|---|
| `test_agents.py` | 33 | ✅ todos | Contratos de AgentResult, heurísticas individuais, flags detectados por cada agente, RULES_MODE vs AI_MODE |
| `test_pipeline_agents.py` | 26 | ✅ todos | Seleção adaptativa, fallback efetivo, cenário A/B/C, valores extremos, hard block e modo Bob |
| `test_pipeline_integration.py` | 12 | ✅ todos | Pipeline completo via mocks de sessão DB |
| `test_e2e_pipeline.py` | 27 | ✅ todos | E2E com banco SQLite em memória; confirmar fase 2, revisão humana, idempotência, timeout |
| `test_cards.py` | 4 | ✅ todos | Cartões, limites e pedidos de aumento |
| `test_financial_integrity.py` | 16 | ✅ todos | Liquidação, saldo, limite de crédito, extrato e idempotência financeira |
| `test_transactions.py` | 13 | ✅ todos | State machine, transições válidas e inválidas, persistência |
| `test_scenarios.py` | 13 | ✅ todos | Integridade dos 3 cenários seed após reset |
| `test_clients.py` | 10 | ✅ todos | CRUD de clientes, histórico comportamental |
| `test_metrics.py` | 26 | ✅ todos | Endpoint `/metrics/summary`, fórmulas TP/FP/TN/FN, Precisão/Recall/F1, distribuição de risco |
| `test_llm_client.py` | 14 | ✅ todos | Provedores permitidos, IBM Bob Shell, credenciais, retry, reset e contrato de resposta |
| `test_simulation.py` | 6 | ✅ todos | Simulação bancária: saldos, transações |
| `test_seed_reset.py` | 7 | ✅ todos | Seed idempotente, reset via endpoint, dados restaurados corretamente |
| `test_health.py` | 3 | ✅ todos | Health endpoint, versão, modo LLM |

### Warnings identificados

Nenhum warning emitido na execução final do pytest.

---

## 2. Testes do Frontend

**Comando:** `cd frontend && npm test -- --run`
**Resultado:** `79 passed`

| Arquivo | Testes | Status | O que cobre |
|---|---|---|---|
| `utils.test.ts` | 34 | ✅ todos | Parsing de AgentResult, mapeamento de risco, formatação BRL/data, parseJSON, parseFlags, riskColor, tipo GatewayResponse, tipos TransferInitiatedResponse |
| `metrics.test.ts` | 45 | ✅ todos | calcRate, pct, calcF1 (incluindo casos edge), isPositivePrediction, riskBucketIndex, computeRiskBuckets, tipos MetricsSummary/ClassificationMetrics |

---

## 3. Verificação TypeScript

**Comando:** `cd frontend && npx tsc --noEmit`
**Resultado:** **0 erros** — compilação limpa

---

## 4. Build de produção

**Comando:** `cd frontend && npm run build`
**Resultado:**
```
✓ 108 modules transformed.
dist/index.html                   0.67 kB │ gzip: 0.41 kB
dist/assets/index-*.css          17.44 kB │ gzip: 4.63 kB
dist/assets/index-*.js          475.75 kB │ gzip: 140.03 kB
```

---

## 5. Verificações de segurança

### 5.1 Credenciais expostas

**Verificação:** `grep -r "sk-\|api_key=" backend/app/ --include="*.py"`
**Resultado:** ✅ Nenhuma credencial real encontrada no código fonte.

O arquivo local `backend/.env` é ignorado pelo Git e pode conter credenciais de desenvolvimento. Ele não deve ser anexado, versionado ou copiado para relatórios. O `.env.example` não contém chaves reais.

### 5.2 APIs bancárias reais

**Verificação:** Inspeção de `bank_service.py`, `bank_simulation.py`
**Resultado:** ✅ Nenhuma chamada a APIs externas. Todo o código opera sobre SQLite local com dados sintéticos.

Declaração no código:
```python
# BankService: "Todas as operações são simuladas. Nenhum dinheiro real é movimentado."
```

### 5.3 Fail-safe (falha nunca resulta em aprovação)

**Verificado em:** `bank_service.py` linhas 279–331
```python
except asyncio.TimeoutError:
    pipeline_failed = True
    # Transação mantida como PENDING para revisão.

except Exception as exc:
    pipeline_failed = True
    # Falha crítica no pipeline: [...] Transação mantida como PENDING.
```

**Resultado:** ✅ Testado em `test_e2e_pipeline.py` — pipeline timeout → transação `PENDING`.

### 5.4 Ação não permitida no Gateway

**Verificado em:** `security_gateway.py` linhas 113–132
```python
if action not in allowed:
    unauthorized_action_attempted = True
    # Forçado para ação mais conservadora
```

**Resultado:** ✅ Testado em `test_agents.py` e `test_pipeline_integration.py`.

### 5.5 Agentes não podem modificar políticas

**Verificado:** Agentes recebem apenas `AgentContext` (read-only). Sem acesso ao `SecurityGateway`, `DecisionEngine` ou banco de dados.

**Resultado:** ✅ Por design — não há método exposto ao agente que permita alterar políticas.

### 5.6 Revisão humana não pode ser feita por IA

**Verificado em:** `security_gateway.py` linhas 249–255
```python
forbidden_ids = ["ai", "llm", "bot", "auto", "system", "agent", "model", "watsonx"]
if any(f in reviewer_id.lower() for f in forbidden_ids):
    return False, "a IA não pode simular revisão humana."
```

**Resultado:** ✅ Testado em `test_e2e_pipeline.py::test_human_review_blocked_for_ai_reviewer`.

---

## 6. Verificação de integridade dos cenários

| Cenário | External ID | Risco seed | Status seed | Verificado em |
|---|---|---|---|---|
| A | `txn-scenario-a` | low | released | `test_scenarios.py` ✅ |
| B | `txn-scenario-b` | medium | under_verification | `test_scenarios.py` ✅ |
| C | `txn-scenario-c` | critical | escalated_to_human | `test_scenarios.py` ✅ |

---

## 7. Problemas identificados e corrigidos

| # | Problema | Correção | Status |
|---|---|---|---|
| 1 | `src/pages/ui.tsx` ausente — todas as páginas importavam `'./ui'` de pasta que não existia | Criado `src/pages/ui.tsx` como re-export de `src/components/ui.tsx` | ✅ Corrigido |
| 2 | Componente `Btn` não aceitava prop `style` opcional | Adicionado `style?: CSSProperties` e spread no elemento | ✅ Corrigido |
| 3 | Banco SQLite desatualizado (coluna `idempotency_key` ausente após etapa 6) | DB excluído — recriado com esquema atualizado no próximo start | ✅ Corrigido |
| 4 | Importações não utilizadas em múltiplas páginas (erro TypeScript) | Removidos imports: `Badge`, `RiskBadge`, `InfoBox`, `RISK_COLOR`, etc. | ✅ Corrigido |
| 5 | `TransferInitiatedResponse` construído sem campos obrigatórios do Etapa 6 em `App.tsx` | Adicionados `idempotent`, `pipeline_failed`, `failure_reason` | ✅ Corrigido |
| 6 | Fixtures de tipo em `utils.test.ts` sem campos novos (`GatewayResponse`, `RiskAnalysisResponse`) | Campos `policy_version`, `divergence_detected`, `confirmation_purpose`, etc. adicionados | ✅ Corrigido |
| 7 | Propriedade CSS duplicada (`padding`) em `FormulaDocumentation` | Substituído por `paddingLeft`, `paddingTop`, etc. | ✅ Corrigido |

---

## 8. Limitações restantes

| # | Limitação | Impacto | Severidade |
|---|---|---|---|
| 1 | IBM Bob respondeu `Budget Exceeded` na validação ao vivo | A chave alcança o serviço, mas a inferência real depende de Bobcoins disponíveis; o sistema usa fallback auditável por regras | 🟠 Média |
| 2 | Métricas de tempo de agente ficam vazias nos dados seed | Seed não executa o pipeline — campo `execution_time_ms` é null | 🟡 Baixa |
| 3 | Apenas 3 cenários com rótulo de referência | F1/Precisão/Recall têm baixa significância estatística | 🟡 Baixa (documentado) |
| 4 | Sem autenticação de usuário | Qualquer pessoa com acesso à URL pode usar o sistema | 🟠 Média (aceitável para MVP) |
| 5 | Hard rule de R$ 50.000 não configurável via UI | Requer mudança no código Python | 🟡 Baixa |
| 6 | Frontend sem testes de integração com API real | Testes cobrem lógica de UI, não chamadas HTTP reais | 🟡 Baixa |
| 7 | LLM AI_MODE não testado em CI | Testes usam apenas mock — comportamento com LLM real não validado em testes automatizados | 🟠 Média (esperado para MVP) |

---

## 9. Estado final de cada componente

### Implementado e testado ✅

- 5 agentes de IA (heurísticas + LLM opcional)
- Execução paralela via `asyncio.gather`
- Decision Engine com limiares configuráveis
- Security Gateway com controle de política
- State machine de transação (12+ status)
- BankService: pipeline completo com idempotência e timeout
- Confirmação contextual (fase 2)
- Revisão humana com validação de reviewer_id
- Persistência SQLite async
- Seed determinístico com 3 cenários
- API REST: 9 routers, 25+ endpoints
- Painel de métricas com 10 indicadores + classificação
- 210 testes backend + 79 testes frontend

### Implementado com fallback; validação externa pendente de orçamento ⚠️

- Integração IBM Bob por `bob run` — autenticação alcançou o serviço, mas a assinatura respondeu `Budget Exceeded`
- Score AI_MODE (heurística + LLM) — lógica e contrato testados com dublês; resposta real depende de Bobcoins disponíveis

### Não implementado ❌

- Autenticação de usuário (JWT/sessão)
- Notificações em tempo real (WebSocket)
- Múltiplos bancos de dados / produção
- Relatórios exportáveis (PDF/CSV)
- Integração com sistemas legados bancários

---

## 10. LLM utilizado

**Modo de teste:** `RULES_MODE` — heurísticas determinísticas locais, sem chamadas externas.

Com `LLM_PROVIDER=bob`, o sistema tenta `AI_MODE`. Falha, timeout ou orçamento esgotado resultam em `FALLBACK_USED` e `RULES_MODE` efetivo, sem interromper a jornada.
