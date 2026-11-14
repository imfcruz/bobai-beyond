#!/usr/bin/env bash
# scripts/start-backend.sh — inicia o servidor FastAPI em modo desenvolvimento

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"

cd "$BACKEND_DIR"

if [ ! -x ".venv/bin/python3" ]; then
  echo "Criando ambiente virtual..."
  python3 -m venv .venv --clear --without-pip
  curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python3
  .venv/bin/pip install -e ".[dev]"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Arquivo .env criado a partir do .env.example"
fi

mkdir -p data

echo "Validando configuração e importações..."
.venv/bin/python3 -c "from app.main import app; assert app"

echo "Iniciando FastAPI em http://localhost:8000 ..."
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
