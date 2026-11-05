# Agentic Doc Management — Backend

Système agentique de compréhension et gestion documentaire.  
Stack : FastAPI · LlamaIndex · Groq (Llama-3.3-70b) · multilingual-e5-base · ChromaDB · MinIO · spaCy

---

## Prérequis système

- Python 3.10+
- Docker & Docker Compose (pour MinIO)
- Tesseract 5 : `sudo apt install tesseract-ocr tesseract-ocr-fra`
- Poppler : `sudo apt install poppler-utils`
- Une clé API Groq (gratuite sur [console.groq.com](https://console.groq.com))

---

## Installation

### 1. Créer l'environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

### 3. Télécharger le modèle spaCy français

```bash
python -m spacy download fr_core_news_md
```

> Le modèle d'embedding `intfloat/multilingual-e5-base` (~280 Mo) est téléchargé
> automatiquement au premier démarrage via HuggingFace.

### 4. Démarrer MinIO

```bash
docker compose up -d
```

Console MinIO : http://localhost:9001 (login: `minioadmin` / `minioadmin`)

### 5. Configurer les variables d'environnement

```bash
cp .env.example .env
# Renseignez SECRET_KEY et GROQ_API_KEY
```

### 6. Démarrer le backend

```bash
uvicorn main:app --reload --port 8000
```

API : http://localhost:8000  
Swagger : http://localhost:8000/docs

---

## Structure du projet

```
backend/
├── main.py                      # Point d'entrée FastAPI
├── .env                         # Variables d'environnement (non commité)
├── .env.example                 # Template de configuration
├── requirements.txt
├── docker-compose.yml           # MinIO
├── core/
│   ├── config.py                # Settings Pydantic centralisés
│   └── database.py              # SQLAlchemy async
├── auth/
│   └── auth.py                  # JWT + bcrypt
├── agents/
│   ├── orchestrator_agent.py    # Orchestrateur ReAct (cœur du système)
│   ├── rag_agent.py             # LlamaIndex + ChromaDB + e5-base
│   ├── ocr_agent.py             # Tesseract + PaddleOCR + pix2tex
│   ├── classification_agent.py  # Classification par sujet via Groq
│   ├── nlp_agent.py             # spaCy — entités nommées
│   └── tools.py                 # Outils disponibles pour l'orchestrateur
├── storage/
│   └── minio_client.py          # Client MinIO
├── models/                      # Modèles SQLAlchemy + schémas Pydantic
└── routes/
    ├── documents.py             # Upload, liste, suppression
    ├── chat.py                  # Chat RAG + streaming SSE
    ├── subjects.py              # Gestion des sujets
    ├── dashboard.py             # Statistiques
    └── websocket.py             # Suivi upload en temps réel
```

---

## Endpoints principaux

### Auth
| Méthode | Route | Description |
|---|---|---|
| POST | `/auth/register` | Inscription |
| POST | `/auth/token` | Connexion → JWT |
| GET | `/auth/me` | Profil utilisateur |

### Documents
| Méthode | Route | Description |
|---|---|---|
| POST | `/documents/upload` | Upload + pipeline complet |
| GET | `/documents/` | Liste avec filtres |
| GET | `/documents/{id}` | Détail document |
| GET | `/documents/{id}/download-url` | URL presignée MinIO |
| DELETE | `/documents/{id}` | Supprimer (cascade) |

### Chat
| Méthode | Route | Description |
|---|---|---|
| POST | `/chat/stream` | Chat RAG avec streaming SSE |
| GET | `/chat/history` | Historique conversations |
| DELETE | `/chat/history` | Effacer l'historique |

### Dashboard & Sujets
| Méthode | Route | Description |
|---|---|---|
| GET | `/dashboard/stats` | Stats globales |
| GET | `/subjects/` | Liste des sujets |
| POST | `/subjects/` | Créer un sujet |

---

## Pipeline de traitement d'un document

```
Upload fichier (PDF / DOCX / IMG / TXT)
    ↓
MinIO docs-raw (stockage original)
    ↓
Agent OCR — routage automatique :
  • Texte imprimé   → Tesseract 5 (fr)
  • Manuscrit       → PaddleOCR
  • Formule math    → pix2tex → LaTeX
    ↓
Agent Classification (Groq / Llama-3.3-70b)
  → sujet, type, titre suggéré, langue
    ↓
MinIO docs-processed (texte extrait)
    ↓
LlamaIndex chunking (512 tokens / 50 overlap)
    ↓
Embedding multilingual-e5-base (768 dims)
    ↓
ChromaDB (vecteurs + métadonnées)
    ↓
Agent NLP spaCy (entités nommées)
    ↓
SQLite (métadonnées document)
    ↓
Statut : "ready" → interrogeable via chat RAG
```

---

## Budget RAM estimé

| Composant | RAM |
|---|---|
| Tesseract | ~200 Mo |
| PaddleOCR | ~800 Mo |
| pix2tex | ~600 Mo |
| multilingual-e5-base | ~280 Mo |
| ChromaDB | ~300 Mo |
| FastAPI + SQLite | ~150 Mo |
| **Total estimé** | **~2 330 Mo** |

> Le LLM (Groq) tourne dans le cloud — aucune RAM locale requise pour l'inférence.  
> Les modèles OCR sont chargés paresseusement (uniquement si nécessaire).
