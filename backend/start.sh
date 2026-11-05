#!/bin/bash
set -e

echo "======================================"
echo "  DocManager — Démarrage du système"
echo "======================================"

# ── Vérifications prérequis ──────────────────────────────────────────────────

check_command() {
  if ! command -v "$1" &>/dev/null; then
    echo "ERREUR : '$1' n'est pas installé."
    echo "  → $2"
    exit 1
  fi
}

check_command docker  "Installer Docker : https://docs.docker.com/get-docker/"
check_command python3 "Installer Python 3.11+"
check_command tesseract "sudo apt install tesseract-ocr tesseract-ocr-fra"

echo ""
echo "▶ Prérequis OK"

# ── MinIO ────────────────────────────────────────────────────────────────────

echo ""
echo "▶ Démarrage MinIO..."
cd backend
docker-compose up -d minio
echo "  Attente de MinIO..."
until curl -s -f http://localhost:9000/minio/health/live > /dev/null; do
    sleep 1
done
echo "  Console MinIO : http://localhost:9001 (minioadmin / minioadmin)"

# ── Backend Python ───────────────────────────────────────────────────────────

echo ""
echo "▶ Environnement Python..."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "  Virtualenv créé"
fi

source .venv/bin/activate

pip install -q --upgrade pip
pip install -q -r requirements.txt

# Vérifier spaCy
if ! python3 -c "import spacy; spacy.load('fr_core_news_md')" 2>/dev/null; then
  echo "  Téléchargement du modèle spaCy français..."
  python3 -m spacy download fr_core_news_md
fi

echo "  Dépendances Python : OK"

# ── Répertoires ──────────────────────────────────────────────────────────────

mkdir -p data/chroma

# ── Démarrage FastAPI ────────────────────────────────────────────────────────

echo ""
echo "▶ Démarrage du backend FastAPI..."
echo "  API : http://localhost:8000"
echo "  Docs : http://localhost:8000/docs"
echo ""

if [ "$APP_ENV" = "production" ]; then
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
else
    uvicorn main:app --host 0.0.0.0 --port 8000
fi
