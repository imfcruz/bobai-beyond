# BobIA — Segurança Adaptativa para Operações Financeiras

Protótipo acadêmico desenvolvido para o IBM AI Experiential Learning Lab. O sistema demonstra como uma arquitetura multiagente pode analisar transferências, identificar sinais de fraude e engenharia social, adaptar a jornada de segurança e encaminhar casos sensíveis para decisão humana.

Todos os clientes, saldos, cartões, beneficiários e transações são sintéticos. Nenhuma operação financeira real é executada e os resultados não representam desempenho de produção do Banco do Brasil ou de qualquer outra instituição.

## O que o protótipo entrega

- Experiência do cliente com contas sintéticas alternáveis.
- Pix com origem em saldo da conta ou limite do cartão de crédito.
- Saldo, limite disponível, reservas e lançamentos atualizados após cada decisão.
- Cartão interativo com visual tridimensional e solicitação de aumento de limite.
- Cadastro de contatos, favoritos e beneficiários de demonstração.
- Extrato derivado das movimentações efetivamente liquidadas.
- Pipeline multiagente para análise contextual de risco.
- Confirmação adicional para operações que exigem mais contexto.
- Revisão humana de transferências e pedidos de limite.
- Painel do funcionário com visão geral, clientes, auditoria, métricas e cenários.
- Trilha de auditoria com decisões, evidências e modo de execução.

## Arquitetura de análise

O orquestrador monta o contexto e seleciona os especialistas necessários para cada operação. Fraude e Comportamental formam a triagem mínima; Intenção e Inconsistência entram como segunda opinião quando há valor atípico, beneficiário novo, dispositivo desconhecido, mudança recente de limite, sequência de eventos ou finalidade sensível.

1. **Fraude:** avalia valor, beneficiário, mudanças recentes e sinais de engenharia social.
2. **Comportamental:** compara a operação com o histórico financeiro sintético do cliente.
3. **Intenção:** avalia a finalidade informada sem tratá-la isoladamente como prova.
4. **Inconsistência:** procura divergências entre contexto, comportamento e operação.

Os agentes selecionados executam em paralelo e, em seguida, o **Agente de Risco** consolida os resultados. O motor de decisão e o gateway de segurança produzem uma das jornadas:

| Nível | Jornada esperada |
|---|---|
| Baixo | Liberação automática |
| Médio | Confirmação contextual |
| Alto ou crítico | Revisão humana |
| Regra absoluta violada | Bloqueio |

Os agentes emitem recomendação e evidências; a decisão financeira é aplicada pelos serviços de domínio. Casos encaminhados para revisão continuam dependendo da ação do funcionário.

## Modos de execução

O backend separa explicitamente análise determinística de inferência com modelo:

| Configuração | Modo | Uso |
|---|---|---|
| `LLM_PROVIDER=mock` | `RULES_MODE` | Padrão local, testes e demonstração sem serviço externo |
| `LLM_PROVIDER=bob` | `AI_MODE` | IBM Bob Shell com chave Inference vinculada ao time |
| `LLM_PROVIDER=watsonx` | `AI_MODE` | Inferência com modelo IBM configurado no Watsonx |

No `RULES_MODE`, os resultados vêm de heurísticas determinísticas e nunca são apresentados como IA generativa. Com um provedor real, cada agente combina sua avaliação determinística com a resposta estruturada do modelo. Se a inferência falhar, expirar ou estiver sem saldo, o resultado registra `FALLBACK_USED` e o modo efetivo passa a `RULES_MODE`.

### IBM Bob e inferência do backend

O provedor `bob` usa o modo não interativo oficialmente documentado do IBM Bob Shell. A chave do tipo **Inference** já é vinculada à instância e ao time, portanto não exige que o projeto informe um modelo. O cliente limita cada execução a uma rodada, define teto de custo e desabilita MCP, subagentes e ferramentas de execução.

O Watsonx continua disponível como integração direta por SDK. A chave do IBM Bob não deve ser reutilizada como IBM Cloud API Key do Watsonx.

Credenciais reais pertencem exclusivamente ao arquivo local `backend/.env`, que é ignorado pelo Git. O arquivo `.env.example` contém apenas nomes de variáveis e valores de exemplo.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| API | FastAPI, Pydantic v2 e Uvicorn |
| Persistência | SQLAlchemy assíncrono e SQLite |
| Observabilidade | structlog e trilha de auditoria |
| Frontend | React 19, TypeScript e Vite |
| Comunicação | REST com axios |
| Testes | pytest, pytest-asyncio e Vitest |

## Requisitos

- Python 3.11 ou superior
- Node.js 18 ou superior
- npm 9 ou superior
- Git

## Instalação

Na raiz do repositório:

```bash
cd bobai-beyond
```

Prepare o backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
cd ..
```

Prepare o frontend:

```bash
cd frontend
npm install
cd ..
```

## Como executar

Abra dois terminais na raiz `bobai-beyond`.

Terminal 1 — backend:

```bash
./scripts/start-backend.sh
```

Terminal 2 — frontend:

```bash
./scripts/start-frontend.sh
```

Se os scripts ainda não tiverem permissão de execução:

```bash
chmod +x scripts/start-backend.sh scripts/start-frontend.sh
```

Endereços locais:

| Serviço | Endereço |
|---|---|
| Interface | `http://localhost:5173` |
| API | `http://localhost:8000` |
| Swagger | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |

O backend cria o banco SQLite e carrega os dados sintéticos de demonstração quando necessário.

## Configuração de IA IBM

### Opção 1 — IBM Bob

O Bob Shell exige Node.js 24 ou superior. Instale-o pelo procedimento oficial da IBM:

```bash
curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash
```

No arquivo local `backend/.env`, configure:

```dotenv
LLM_PROVIDER=bob
BOB_API_KEY=SUA_CHAVE_INFERENCE
BOB_TEAM_ID=
BOB_SHELL_COMMAND=bob
BOB_MAX_COST=0.05
BOB_TIMEOUT_SECONDS=90
AGENT_PIPELINE_TIMEOUT_SECONDS=195
AGENT_MODE=auto
```

Para uma chave do tipo **Inference**, mantenha `BOB_TEAM_ID` vazio. Chaves do tipo **General** exigem o identificador do time.

Valide a instalação antes de iniciar o backend:

```bash
bob --version
bob run --format json --max-turns 1 "Responda apenas: integração ativa"
```

Se o comando retornar `Budget Exceeded`, a chave foi aceita, mas a assinatura está sem Bobcoins disponíveis. O backend continuará funcional por regras e identificará o fallback na auditoria; para validar inferência real, é necessário restabelecer o orçamento no IBM Bob.

### Opção 2 — IBM Watsonx

Para usar o Watsonx, instale o SDK opcional no ambiente virtual:

```bash
cd backend
source .venv/bin/activate
pip install ibm-watsonx-ai
```

Depois, configure somente no arquivo local `backend/.env`:

```dotenv
LLM_PROVIDER=watsonx
LLM_API_KEY=SUA_CHAVE_IBM_CLOUD
LLM_MODEL=ID_DO_MODELO_IBM
WATSONX_PROJECT_ID=ID_DO_PROJETO
WATSONX_REGION=us-south
AGENT_MODE=auto
```

Não envie chaves em mensagens, capturas de tela, commits ou arquivos de exemplo. Para voltar à demonstração totalmente local:

```dotenv
LLM_PROVIDER=mock
LLM_MODEL=mock-model
AGENT_MODE=auto
```

## Fluxo recomendado de demonstração

1. Acesse `http://localhost:5173/bank`.
2. Escolha uma conta sintética e consulte saldo, limite e movimentações.
3. Abra **Contatos**, favorite um beneficiário e inicie um Pix.
4. Faça uma operação de baixo risco para observar a liberação automática.
5. Faça uma operação incomum para acionar confirmação ou revisão humana.
6. Abra **Cartões**, interaja com o cartão e solicite aumento de limite.
7. Alterne para o modo funcionário e analise o pedido pendente.
8. Volte à conta do cliente e confirme a atualização do limite.
9. Realize um Pix no crédito e observe o consumo do limite disponível.
10. Consulte o extrato, a auditoria e as métricas atualizadas.

## Testes e validação

Backend:

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

Análise estática do frontend:

```bash
cd frontend
npm run lint
```

O relatório detalhado da última validação está em `TEST_REPORT.md`. A quantidade exata de testes deve ser obtida pela execução da suíte, evitando manter números manuais desatualizados neste documento.

## Publicação em cinco contribuições

Esta seção descreve a entrega do código pelos cinco integrantes do grupo. Cada pacote contém código executável de uma responsabilidade específica. Cada integrante deve revisar o próprio pacote, usar sua própria identidade do Git e criar o próprio commit.

### Ordem obrigatória

Os pacotes devem ser aplicados e enviados nesta ordem:

1. Fernando — agentes e integração IBM.
2. Caio — domínio financeiro e API.
3. Arthur — experiência bancária do cliente.
4. Eduardo — integração e testes automatizados.
5. Denise — ambiente do funcionário, tutorial, scripts e documentação.

A ordem é necessária porque cada pacote parte do resultado do anterior. Se duas pessoas começarem a partir da mesma versão da branch `main`, o segundo push será recusado pelo Git para proteger o histórico. Cada pessoa deve aguardar o commit anterior aparecer no GitHub e então executar `git pull --rebase origin main` antes de extrair o próprio pacote.

Não use `git push --force` ou `git push -f`. Ter permissão de colaborador permite enviar commits, mas não transforma o force em um atalho seguro. Um push forçado pode apagar os commits dos colegas e prejudicar a comprovação das cinco contribuições.

### Preparação no Google Drive

O responsável pelo envio deve:

1. Enviar ao Drive o arquivo único `PACOTES_CONTRIBUICOES_BOBIA.zip`.
2. Compartilhar o arquivo com Fernando, Caio, Arthur, Eduardo e Denise.
3. Informar que o ZIP geral deve ser extraído em uma pasta temporária, fora do repositório.
4. Informar que cada pessoa deve usar somente o ZIP que começa com seu número e nome.
5. Adicionar os demais integrantes como colaboradores do repositório `imfcruz/bobai-beyond` com permissão de escrita.

Depois de baixar o arquivo do Drive, cada integrante terá estes pacotes:

| Ordem | Integrante | Pacote |
|---:|---|---|
| 1 | Fernando | `01_Fernando_agentes_ibm.zip` |
| 2 | Caio | `02_Caio_backend_financeiro.zip` |
| 3 | Arthur | `03_Arthur_experiencia_bancaria.zip` |
| 4 | Eduardo | `04_Eduardo_integracao_testes.zip` |
| 5 | Denise | `05_Denise_funcionario_tutorial_docs.zip` |

### Preparação do clone

A opção mais rápida e segura é cada integrante fazer um clone novo quando chegar sua vez:

```bash
git clone https://github.com/imfcruz/bobai-beyond.git
cd bobai-beyond
git switch main
git pull --rebase origin main
```

Quem já possui um clone pode reutilizá-lo, desde que não tenha alterações locais pendentes:

```bash
cd bobai-beyond
git switch main
git status --short
git pull --rebase origin main
```

Se `git status --short` mostrar arquivos inesperados, não continue nem use force. Um clone novo evita misturar alterações antigas com o pacote da contribuição.

Confira a identidade que será registrada no commit:

```bash
git config user.name
git config user.email
```

Se necessário, configure a identidade somente nesse clone. Use o e-mail cadastrado e verificado na conta do GitHub:

```bash
git config user.name "SEU NOME"
git config user.email "SEU EMAIL DO GITHUB"
```

Extraia somente o ZIP do integrante dentro da raiz do clone, onde estão `README.md`, `backend` e `frontend`. Não extraia o ZIP geral dentro do repositório. Depois confira:

```bash
git status --short
git diff --check
```

### 1. Fernando — agentes e IBM — 20%

Engloba agentes especialistas, orquestrador, configuração dos modos de execução, IBM Bob, IBM Watsonx e fallback seguro.

```bash
git add backend/app/__init__.py backend/app/agents backend/app/core/__init__.py backend/app/core/config.py backend/app/services/__init__.py backend/app/services/llm_client.py
git diff --cached --stat
git commit -m "feat(agents): implementar orquestracao adaptativa com IBM Bob"
git push origin main
```

### 2. Caio — domínio financeiro e API — 20%

Engloba contas, beneficiários, Pix, cartões, limites, liquidação, extrato, persistência, endpoints, auditoria e revisão humana.

```bash
git add backend/app/api backend/app/core/errors.py backend/app/core/logging.py backend/app/db backend/app/main.py backend/app/models backend/app/repositories backend/app/schemas backend/app/services/bank_service.py backend/app/services/bank_simulation.py backend/app/services/card_service.py backend/app/services/decision_engine.py backend/app/services/metrics_service.py backend/app/services/security_gateway.py backend/app/services/seed_service.py backend/app/services/settlement_service.py backend/app/utils backend/pyproject.toml
git diff --cached --stat
git commit -m "feat(bank): completar dominio financeiro API e revisao humana"
git push origin main
```

### 3. Arthur — experiência bancária — 20%

Engloba dashboard do cliente, Pix, cartão 3D, contatos, favoritos, extrato, design system, responsividade e ícones.

```bash
git add frontend
git diff --cached --stat
git commit -m "feat(client): implementar experiencia bancaria responsiva"
git push origin main
```

Nesse momento somente os arquivos do pacote do Arthur estarão modificados em `frontend`; os arquivos dos pacotes posteriores ainda não terão sido extraídos.

### 4. Eduardo — integração e qualidade — 20%

Engloba cliente HTTP de produção, contratos TypeScript, tipos de métricas e suítes automatizadas de backend e frontend.

```bash
git add backend/tests frontend/src/services frontend/src/test frontend/src/types
git diff --cached --stat
git commit -m "test(integration): conectar API e validar jornadas automatizadas"
git push origin main
```

### 5. Denise — funcionário, tutorial e entrega — 20%

Engloba roteamento principal, painel do funcionário, gestão de clientes, gráficos, tutorial guiado, transição de perfis, scripts de inicialização e documentação final.

```bash
git add .gitignore AGENTS.md ARCHITECTURE.md CONTRIBUTION_PLAN.md DEMO.md PROPOSAL_TRACEABILITY.md README.md TEST_REPORT.md backend/.env.example scripts frontend
git diff --cached --stat
git commit -m "feat(employee): finalizar painel tutorial e documentacao"
git push origin main
```

No bloco da Denise, `git add frontend` seleciona somente os arquivos novos do painel do funcionário, tutorial e roteamento. Os arquivos dos blocos anteriores já estarão limpos e rastreados.

### Se o push for recusado

Uma recusa com mensagem `non-fast-forward` normalmente significa que o commit anterior chegou ao GitHub depois que o integrante preparou seu pacote. Preserve o commit local e execute:

```bash
git pull --rebase origin main
git push origin main
```

Se o rebase informar conflito, pare e resolva o conflito antes de continuar. Não use `--force`. Não existe um comando seguro de “forçar para o link” que substitua clone, pull e rebase mantendo as contribuições dos colegas.

### Conferência depois do quinto push

No GitHub, confirme que a branch `main` mostra os cinco commits e os cinco autores. Em seguida, faça uma validação limpa:

```bash
git pull --rebase origin main
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests -q
cd ../frontend
npm install
npm run build
npm test -- --run
```

Na validação preparada para a entrega, o resultado esperado foi `210` testes de backend, `79` testes de frontend e build concluído sem erros.

## Endpoints principais

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/api/v1/health` | Estado da API e modo de execução |
| `GET` | `/api/v1/clients/` | Lista de clientes sintéticos |
| `GET` | `/api/v1/clients/{id}` | Dados da conta selecionada |
| `GET` | `/api/v1/clients/{id}/statement` | Extrato financeiro consolidado |
| `GET` | `/api/v1/clients/{id}/limits` | Limite Pix e disponibilidade |
| `POST` | `/api/v1/clients/{id}/limits` | Solicitação de alteração do limite Pix |
| `GET` | `/api/v1/beneficiaries/client/{id}` | Contatos e favoritos do cliente |
| `PATCH` | `/api/v1/beneficiaries/{id}/favorite` | Alteração de favorito |
| `POST` | `/api/v1/transactions/` | Início de transferência e análise |
| `POST` | `/api/v1/transactions/{id}/confirm` | Confirmação contextual |
| `POST` | `/api/v1/transactions/{id}/human-review/{action}` | Decisão humana sobre transferência |
| `GET` | `/api/v1/cards/client/{id}` | Cartões do cliente |
| `POST` | `/api/v1/cards/{id}/limit-requests` | Pedido de aumento do limite de crédito |
| `GET` | `/api/v1/cards/limit-requests` | Fila de pedidos de limite |
| `POST` | `/api/v1/cards/limit-requests/{id}/review/{action}` | Decisão humana sobre pedido de limite |
| `GET` | `/api/v1/audit/` | Trilha de auditoria |
| `GET` | `/api/v1/metrics/summary` | Métricas agregadas da demonstração |
| `POST` | `/api/v1/demo/reset` | Restauração dos dados sintéticos |

A especificação completa e sempre atualizada fica disponível no Swagger da própria aplicação.

## Estrutura do repositório

```text
bobai-beyond/
├── backend/
│   ├── app/
│   │   ├── agents/          # agentes especializados e orquestração
│   │   ├── api/             # endpoints REST
│   │   ├── core/            # configuração e tratamento de erros
│   │   ├── models/          # modelos persistidos
│   │   ├── repositories/    # acesso aos dados
│   │   ├── schemas/         # contratos da API
│   │   └── services/        # domínio bancário, liquidação, cartões e LLM
│   ├── tests/
│   └── .env.example
├── frontend/
│   └── src/
│       ├── components/
│       ├── layouts/
│       ├── pages/bank/      # experiência do cliente
│       ├── pages/admin/     # experiência do funcionário
│       ├── services/
│       └── types/
├── scripts/
├── ARCHITECTURE.md
├── AGENTS.md
├── DEMO.md
├── PROPOSAL_TRACEABILITY.md
├── CONTRIBUTION_PLAN.md
└── TEST_REPORT.md
```

## Limitações conhecidas

1. Não há autenticação, autorização por perfil ou gestão real de sessão.
2. O modo funcionário é acessível diretamente e serve apenas à demonstração local.
3. O SQLite não representa uma arquitetura adequada para concorrência em produção.
4. O modo padrão usa regras determinísticas; IA generativa exige configuração externa válida.
5. Os cenários e dados são sintéticos e insuficientes para afirmar eficácia antifraude real.
6. Não há integração com Pix, cartões, core bancário ou sistemas do Banco do Brasil.
7. A confirmação contextual ainda usa um contrato simplificado de demonstração.
8. A solução não passou por avaliação formal de segurança, privacidade, acessibilidade ou carga.
9. O modo IBM Bob depende do Bob Shell instalado, internet e saldo disponível na assinatura.

## Segurança de credenciais

- Nunca versionar `backend/.env`.
- Nunca inserir chaves diretamente em arquivos Python ou TypeScript.
- Usar chaves com o menor escopo possível e prazo de expiração adequado.
- Revogar imediatamente qualquer segredo exposto em chat, imagem, log ou commit.
- Manter apenas placeholders no `.env.example`.

## Documentação complementar

- `ARCHITECTURE.md`: componentes, fluxo e decisões técnicas.
- `AGENTS.md`: responsabilidades e contratos dos agentes.
- `DEMO.md`: roteiro de apresentação.
- `TEST_REPORT.md`: evidências de validação e limitações dos testes.
- `PROPOSAL_TRACEABILITY.md`: matriz entre os compromissos da proposta e o que é demonstrável.
- `CONTRIBUTION_PLAN.md`: divisão em cinco blocos de 20% com validação e commits sugeridos.
