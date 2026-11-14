# Divisão técnica do grupo

O projeto foi separado em cinco blocos de responsabilidade, com **20% para cada integrante**. Todos os blocos contêm código executável. A porcentagem representa responsabilidade técnica, revisão e capacidade de apresentação, não quantidade idêntica de linhas.

Cada integrante deve revisar o próprio pacote, executar a validação indicada e criar o commit com sua conta pessoal do GitHub.

## Fernando — 20% — agentes e IBM

- Orquestrador adaptativo.
- Agentes de fraude, intenção, inconsistência, comportamento e risco.
- Integração IBM Bob e IBM Watsonx.
- Configuração de modos de execução e fallback seguro.

Commit sugerido:

```bash
git add backend/app/__init__.py backend/app/agents backend/app/core/__init__.py backend/app/core/config.py backend/app/services/__init__.py backend/app/services/llm_client.py
git diff --cached --stat
git commit -m "feat(agents): implementar orquestracao adaptativa com IBM Bob"
git push origin main
```

## Caio — 20% — domínio financeiro e API

- Contas, beneficiários, Pix, cartões e limites.
- Liquidação, reservas e extrato.
- Endpoints REST, persistência e revisão humana.
- Auditoria, métricas e cenários sintéticos.

Commit sugerido:

```bash
git add backend/app/api backend/app/core/errors.py backend/app/core/logging.py backend/app/db backend/app/main.py backend/app/models backend/app/repositories backend/app/schemas backend/app/services/bank_service.py backend/app/services/bank_simulation.py backend/app/services/card_service.py backend/app/services/decision_engine.py backend/app/services/metrics_service.py backend/app/services/security_gateway.py backend/app/services/seed_service.py backend/app/services/settlement_service.py backend/app/utils backend/pyproject.toml
git diff --cached --stat
git commit -m "feat(bank): completar dominio financeiro API e revisao humana"
git push origin main
```

## Arthur — 20% — experiência bancária

- Dashboard do cliente e troca de contas.
- Jornada de Pix, contatos e favoritos.
- Cartão 3D, limite e extrato.
- Design system, responsividade e ícones vetoriais.

Commit sugerido:

```bash
git add frontend
git diff --cached --stat
git commit -m "feat(client): implementar experiencia bancaria responsiva"
git push origin main
```

## Eduardo — 20% — integração e qualidade

- Cliente HTTP e contratos TypeScript da API.
- Tipos de métricas e respostas financeiras.
- Testes unitários, E2E e de integridade financeira.
- Isolamento dos testes para impedir chamadas externas.

Commit sugerido:

```bash
git add backend/tests frontend/src/services frontend/src/test frontend/src/types
git diff --cached --stat
git commit -m "test(integration): conectar API e validar jornadas automatizadas"
git push origin main
```

## Denise — 20% — ambiente do funcionário e entrega

- Roteamento principal da aplicação.
- Painel do funcionário, gestão de clientes e gráficos.
- Tutorial guiado e transição entre perfis.
- Scripts de execução, documentação e aderência à proposta.

Commit sugerido:

```bash
git add .gitignore AGENTS.md ARCHITECTURE.md CONTRIBUTION_PLAN.md DEMO.md PROPOSAL_TRACEABILITY.md README.md TEST_REPORT.md backend/.env.example scripts frontend
git diff --cached --stat
git commit -m "feat(employee): finalizar painel tutorial e documentacao"
git push origin main
```

## Ordem obrigatória

1. Fernando.
2. Caio.
3. Arthur.
4. Eduardo.
5. Denise.

Cada pessoa deve executar `git pull --rebase origin main` imediatamente antes de extrair o próprio pacote. O grupo não deve usar `git push --force` nem versionar `.env`, chaves, bancos SQLite, `.venv`, `node_modules` ou arquivos ZIP.
