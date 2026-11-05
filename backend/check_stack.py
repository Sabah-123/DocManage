"""
Script de vérification de la stack avant démarrage.
Exécuter : python check_stack.py
"""
import sys
import subprocess

PASS = "✓"
FAIL = "✗"
WARN = "⚠"

results = []


def check(label: str, fn):
    try:
        msg = fn()
        results.append((PASS, label, msg or ""))
    except Exception as e:
        results.append((FAIL, label, str(e)))


# ── Python ───────────────────────────────────────────────────────────────────

check("Python version", lambda: (
    f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info >= (3, 11)
    else (_ for _ in ()).throw(Exception("Python 3.11+ requis"))
))

# ── Imports Python ───────────────────────────────────────────────────────────

def check_import(name, pip_name=None):
    try:
        __import__(name)
        return f"importé"
    except ImportError:
        raise Exception(f"pip install {pip_name or name}")

check("fastapi",           lambda: check_import("fastapi"))
check("uvicorn",           lambda: check_import("uvicorn"))
check("sqlalchemy",        lambda: check_import("sqlalchemy"))
check("minio",             lambda: check_import("minio"))
check("pytesseract",       lambda: check_import("pytesseract"))
check("cv2 (opencv)",      lambda: check_import("cv2", "opencv-python-headless"))
check("PIL (Pillow)",      lambda: check_import("PIL", "Pillow"))
check("fitz (PyMuPDF)",    lambda: check_import("fitz", "pymupdf"))
check("docx (python-docx)",lambda: check_import("docx", "python-docx"))
check("llama_index",       lambda: check_import("llama_index"))
check("chromadb",          lambda: check_import("chromadb"))
check("sentence_transformers", lambda: check_import("sentence_transformers"))
check("ollama",            lambda: check_import("ollama"))
check("langdetect",        lambda: check_import("langdetect"))
check("jose (python-jose)",lambda: check_import("jose", "python-jose[cryptography]"))
check("passlib",           lambda: check_import("passlib"))
check("aiosqlite",         lambda: check_import("aiosqlite"))

# ── spaCy modèle ─────────────────────────────────────────────────────────────

def check_spacy():
    import spacy
    try:
        spacy.load("fr_core_news_md")
        return "fr_core_news_md chargé"
    except OSError:
        try:
            spacy.load("fr_core_news_sm")
            return f"{WARN} fr_core_news_sm (md recommandé : python -m spacy download fr_core_news_md)"
        except OSError:
            raise Exception("python -m spacy download fr_core_news_md")

check("spaCy fr model", check_spacy)

# ── Tesseract ─────────────────────────────────────────────────────────────────

def check_tesseract():
    import pytesseract
    langs = pytesseract.get_languages()
    if "fra" not in langs:
        raise Exception("Pack langue 'fra' manquant : sudo apt install tesseract-ocr-fra")
    return f"langues : {', '.join(langs[:5])}..."

check("Tesseract + fra", check_tesseract)

# ── PaddleOCR (optionnel) ────────────────────────────────────────────────────

def check_paddle():
    try:
        import paddleocr
        return "disponible"
    except ImportError:
        return f"{WARN} non installé (pip install paddleocr paddlepaddle)"

check("PaddleOCR (manuscrit)", check_paddle)

# ── pix2tex (optionnel) ──────────────────────────────────────────────────────

def check_pix2tex():
    try:
        import pix2tex
        return "disponible"
    except ImportError:
        return f"{WARN} non installé (pip install pix2tex)"

check("pix2tex (formules)", check_pix2tex)

# ── Ollama ───────────────────────────────────────────────────────────────────

def check_ollama():
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        if "qwen2.5:3b" in result.stdout:
            return "qwen2.5:3b disponible"
        else:
            return f"{WARN} qwen2.5:3b non trouvé — exécuter : ollama pull qwen2.5:3b"
    except FileNotFoundError:
        raise Exception("Ollama non installé : https://ollama.com")
    except subprocess.TimeoutExpired:
        raise Exception("Ollama ne répond pas")

check("Ollama + qwen2.5:3b", check_ollama)

# ── MinIO (Docker) ───────────────────────────────────────────────────────────

def check_minio():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:9000/minio/health/live", timeout=3)
        return "en ligne sur :9000"
    except Exception:
        raise Exception("MinIO non démarré — exécuter : docker-compose up -d")

check("MinIO", check_minio)

# ── HuggingFace multilingual-e5-base ─────────────────────────────────────────

def check_embedding():
    import os
    from pathlib import Path
    # Vérifier cache HuggingFace
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    found = any("multilingual-e5" in str(p) for p in cache.rglob("*.json")) if cache.exists() else False
    if found:
        return "en cache local"
    return f"{WARN} sera téléchargé au 1er démarrage (~280 Mo)"

check("multilingual-e5-base (embedding)", check_embedding)

# ── Affichage des résultats ──────────────────────────────────────────────────

print()
print("=" * 60)
print("  Vérification de la stack DocManager")
print("=" * 60)
print()

all_ok = True
for status, label, msg in results:
    line = f"  {status}  {label}"
    if msg:
        line += f"  →  {msg}"
    print(line)
    if status == FAIL:
        all_ok = False

print()
if all_ok:
    print("  Tout est prêt. Démarrer avec : ./start.sh")
else:
    print("  Corriger les erreurs (✗) avant de démarrer.")
    print("  Les avertissements (⚠) sont optionnels.")
print()
