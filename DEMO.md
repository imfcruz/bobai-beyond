# DEMO.md — Roteiro de Demonstração

> Adaptive Security MVP — IBM AI Experiential Learning Lab
> Dados 100% sintéticos. Nenhuma operação financeira real é executada.

---

## 1. Preparação do ambiente

### Requisitos

- Python 3.11+ e Node.js 18+ instalados
- Projeto clonado e dependências instaladas (ver README.md)

### Verificação rápida

```bash
# Backend instalado?
cd backend && .venv/bin/python -c "import fastapi; print('OK')"

# Frontend instalado?
cd frontend && node -e "require('./package.json') && console.log('OK')"
```

### Limpar o banco para demo limpa (opcional)

```bash
rm -f backend/data/adaptive_security.db
```

O banco será recriado com os dados seed na próxima inicialização.

---

## 2. Inicialização

**Abra dois terminais** a partir da raiz do projeto:

**Terminal 1 — Backend:**
```bash
./scripts/start-backend.sh
```
Aguarde até ver: `Uvicorn running on http://0.0.0.0:8000`

**Terminal 2 — Frontend:**
```bash
./scripts/start-frontend.sh
```
Aguarde até ver: `Local: http://localhost:5173/`

**Abra no navegador:** http://localhost:5173

Você verá o **Painel (Dashboard)** com os 3 clientes sintéticos disponíveis.

---

## 3. Cenário A — Transferência Normal

**Objetivo:** Demonstrar que o sistema libera automaticamente operações legítimas de baixo risco.

### Como executar

1. Navegue para **`/scenarios`** (aba "📚 Cenários" na nav)
2. Clique em **"Executar Cenário A"**

_Ou manualmente:_
1. Acesse **`/transfer`**
2. Selecione: **Ana Costa** (`client-ana-costa`)
3. Beneficiário: **Fornecedor Alpha** (`ben-fornecedor-alpha`)
4. Valor: **R$ 1.200,00**
5. Finalidade: `Pagamento de serviços`
6. Clique em **"Analisar transferência"**

### O que acontece no pipeline

```
FraudAgent:         score ≈ 0.05  (beneficiário conhecido, valor normal)
InconsistencyAgent: score ≈ 0.05  (sem eventos suspeitos)
BehavioralAgent:    score ≈ 0.08  (dentro do padrão histórico)
RiskAgent:          score ≈ 0.06  (ponderado)
Decision Engine:    APPROVE (score < 0.30)
Security Gateway:   authorized=True
```

### Resultado esperado

- ✅ Status: **RELEASED** (liberada automaticamente)
- Nível de risco: **low** (verde)
- Nenhum flag ativado
- Score < 0.10

### O que destacar para a audiência

- "O pipeline executa 5 agentes em milissegundos"
- "A decisão é auditável — cada agente registrou seu score individualmente"
- "Nenhum dado foi enviado a um banco real"

---

## 4. Cenário B — Comportamento Incomum

**Objetivo:** Demonstrar que o sistema detecta desvios comportamentais e solicita confirmação contextual adicional.

### Como executar

1. Navegue para **`/scenarios`**
2. Clique em **"Executar Cenário B"**

_Ou manualmente:_
1. Acesse **`/transfer`**
2. Selecione: **Carlos Mendes** (`client-carlos-mendes`)
3. Beneficiário: **Escritório Beta** (`ben-escritorio-beta`)
4. Valor: **R$ 8.000,00**
5. Finalidade: `Investimento`
6. Clique em **"Analisar transferência"**

### O que acontece no pipeline

```
FraudAgent:         score ≈ 0.35  (valor 4× acima da média de Carlos)
InconsistencyAgent: score ≈ 0.30  (finalidade genérica para valor alto)
BehavioralAgent:    score ≈ 0.45  (acima do máximo histórico)
RiskAgent:          score ≈ 0.37  (ponderado)
Decision Engine:    REQUEST_CONFIRMATION (score 0.30–0.59)
Security Gateway:   authorized=True, requires_confirmation=True
```

### Resultado esperado

- ⚠️ Status: **AWAITING_CONFIRMATION**
- Nível de risco: **medium** (amarelo)
- Flags: `above_max_historical`, `high_value_vs_avg`
- O sistema solicita **confirmação contextual** (fase 2)

### Fase 2 — Confirmação contextual

Após o resultado, o sistema redireciona para `/confirm`:
1. O cliente deve confirmar **intenção genuína** da transferência
2. Perguntas contextuais: "Você iniciou esta transferência por conta própria?"
3. Se resposta indicar coerção → transação **rejeitada com flag `possible_coercion`**
4. Se resposta genuína → transação **liberada**

### O que destacar

- "O sistema não bloqueou automaticamente — pediu confirmação contextual"
- "A pergunta é diferente de uma senha: detecta coerção por engenharia social"
- "O cliente que está sendo manipulado responderá de forma diferente de quem age livremente"

---

## 5. Cenário C — Engenharia Social

**Objetivo:** Demonstrar a detecção de padrões típicos de engenharia social e a escalada para revisão humana.

### Como executar

1. Navegue para **`/scenarios`**
2. Clique em **"Executar Cenário C"**

_Ou manualmente:_
1. Acesse **`/transfer`**
2. Selecione: **Beatriz Santos** (`client-beatriz-santos`)
3. Beneficiário: **Empresa XPTO** (`ben-empresa-xpto`)
4. Valor: **R$ 25.000,00**
5. Finalidade: `Transferência urgente banco bloqueado`
6. Marque: **Dispositivo não reconhecido**
7. Clique em **"Analisar transferência"**

### O que acontece no pipeline

```
FraudAgent:         score ≈ 0.90  (palavras-chave: "urgente", "banco bloqueado")
                                   flags: social_engineering_keyword,
                                          full_social_engineering_sequence,
                                          device_not_recognized_high_value
InconsistencyAgent: score ≈ 0.80  (dispositivo desconhecido + beneficiário novo)
                                   flags: unknown_device_new_recipient,
                                          recent_limit_change
BehavioralAgent:    score ≈ 0.85  (valor 12× acima da média de Beatriz)
                                   flags: extreme_above_avg, extreme_above_max
RiskAgent:          score ≈ 0.87  (ponderado — acima do threshold critical)
Decision Engine:    ESCALATE_TO_HUMAN (score ≥ 0.85)
Security Gateway:   authorized=True, requires_human_review=True
```

### Resultado esperado

- 🚨 Status: **HUMAN_REVIEW_PENDING**
- Nível de risco: **critical** (vermelho)
- Múltiplos flags de engenharia social ativos
- Score ≈ 0.87+

### Revisão humana

1. Navegue para `/human-review`
2. Informe um **ID de revisor humano** (ex: `operador-joao-01`)
3. Selecione a transação
4. Aprove ou rejeite com justificativa
5. Status transita para `HUMAN_APPROVED` ou `HUMAN_REJECTED`

> **Atenção:** O sistema bloqueia `reviewer_id` com termos de IA (`bot`, `ai`, `agent`, etc.) — a revisão **deve ser humana**.

### O que destacar

- "O Agente de Fraude detectou três sinais simultâneos de engenharia social"
- "O sistema não bloqueou automaticamente — escalou para um humano"
- "A decisão final é do operador humano, com auditoria completa"
- "Toda a cadeia de decisão está registrada e pode ser auditada"

---

## 6. Resultados esperados por cenário

| Cenário | Score esperado | Status | Ação |
|---|---|---|---|
| A — Normal | < 0.15 | `released` | Liberada automaticamente |
| B — Incomum | 0.30–0.55 | `awaiting_confirmation` | Confirmação contextual |
| C — Engenharia social | > 0.85 | `human_review_pending` | Revisão humana obrigatória |

> Os scores exatos variam com `LLM_PROVIDER`. Com `mock` (padrão), os valores são determinísticos.

---

## 7. Painel de auditoria

Após executar os cenários, acesse `/audit` para demonstrar rastreabilidade:

### O que mostrar

1. **Aba Análises** → expand qualquer linha para ver resultado por agente
2. **Campos de interesse:**
   - `policy_version` → mostra que a decisão foi auditada
   - `execution_time_ms` → tempo de execução do pipeline
   - `divergence_detected` → se agentes discordaram
   - `agent_contributions` → peso de cada agente
3. **Clique em "▼ Detalhes"** para expandir resultado JSON completo por agente

### Ponto chave

> "Cada decisão é rastreável: quem decidiu, qual modelo, qual política, em quanto tempo."

---

## 8. Painel de métricas

Acesse `/metrics` para demonstrar análise agregada:

### O que mostrar

1. **Seção ① Indicadores de Volume** — total de transações analisadas
2. **Seção ③ Distribuição de Risco** — gráfico pizza por nível
3. **Seção ④ Distribuição de Ações** — gráfico de barras
4. **Seção ⑦ Avaliação de Classificação** — TP/FP/TN/FN dos cenários rotulados
   - Mostrar a **matriz de confusão** e **Precisão/Recall/F1**
   - Ler o aviso: *"Dados sintéticos — não representa desempenho real"*
5. **Seção ⑨ Documentação de Fórmulas** — mostrar transparência metodológica

### Ponto chave

> "Métricas calculadas em tempo real, do banco real. Nenhum valor inventado."
> "Os resultados são de um simulador — não afirmamos que reduziríamos fraudes no BB."

---

## 9. Reset da demonstração

Para recomeçar com dados limpos:

- Clique em **"🔄 Reset demo"** no cabeçalho da interface
- Ou execute: `curl -X POST http://localhost:8000/api/v1/demo/reset`

O reset preserva os dados estruturais (clientes, beneficiários) e reaplica as 3 transações seed.

---

## 10. Demonstração da API (opcional)

Para audiência técnica, mostrar a Swagger UI:

1. Acesse **http://localhost:8000/docs**
2. Demonstrar `POST /api/v1/transactions/` com body:
```json
{
  "client_external_id": "client-beatriz-santos",
  "beneficiary_external_id": "ben-empresa-xpto",
  "amount": "25000.00",
  "purpose": "Transferência urgente banco bloqueou",
  "device_recognized": false
}
```
3. Mostrar a resposta completa com todos os campos de cada agente

---

## Duração sugerida

| Etapa | Tempo |
|---|---|
| Contexto e arquitetura (slide) | 5 min |
| Cenário A — demo ao vivo | 3 min |
| Cenário B — demo ao vivo + fase 2 | 4 min |
| Cenário C — demo ao vivo + revisão humana | 5 min |
| Painel de auditoria | 3 min |
| Painel de métricas | 3 min |
| Perguntas | 5 min |
| **Total** | **~28 min** |
