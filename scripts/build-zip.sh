#!/usr/bin/env bash
# scripts/build-zip.sh — cria pacote ZIP para entrega acadêmica
# Exclui: .venv, node_modules, __pycache__, banco SQLite, credenciais, dist/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ZIP_NAME="adaptive_security_mvp_${TIMESTAMP}.zip"
OUTPUT="$ROOT_DIR/$ZIP_NAME"

cd "$ROOT_DIR"

echo "📦 Criando pacote ZIP para entrega: $ZIP_NAME"
echo "   Excluindo: .venv, node_modules, __pycache__, *.db, dist/, .env, logs"

zip -r "$OUTPUT" . \
  --exclude "*.git*" \
  --exclude ".venv/*" \
  --exclude "backend/.venv/*" \
  --exclude "*node_modules/*" \
  --exclude "*__pycache__/*" \
  --exclude "*.pyc" \
  --exclude "*.pyo" \
  --exclude "*.pyd" \
  --exclude "backend/data/*" \
  --exclude "*.db" \
  --exclude "*.sqlite" \
  --exclude "*.sqlite3" \
  --exclude "frontend/dist/*" \
  --exclude "backend/.env" \
  --exclude ".env" \
  --exclude "*.env.local" \
  --exclude ".pytest_cache/*" \
  --exclude ".ruff_cache/*" \
  --exclude ".mypy_cache/*" \
  --exclude "htmlcov/*" \
  --exclude "coverage.xml" \
  --exclude "*.egg-info/*" \
  --exclude "*.log" \
  --exclude "*.tmp" \
  --exclude ".DS_Store" \
  --exclude "*.zip"

SIZE=$(du -sh "$OUTPUT" | cut -f1)
echo ""
echo "✅ Pacote criado com sucesso!"
echo "   Arquivo: $ZIP_NAME"
echo "   Tamanho: $SIZE"
echo ""
echo "⚠️  Verifique se não há credenciais reais antes de compartilhar."
