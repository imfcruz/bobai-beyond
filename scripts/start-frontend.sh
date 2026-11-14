#!/usr/bin/env bash
# scripts/start-frontend.sh — inicia o servidor Vite em modo desenvolvimento

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
  echo "Instalando dependências Node.js..."
  npm ci
fi

echo "Iniciando frontend em http://localhost:5173 ..."
npm run dev
