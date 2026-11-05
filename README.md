# 🗂️ Agentic Doc Management

> Système intelligent de compréhension et gestion documentaire basé sur une architecture multi-agents (RAG, OCR, Classification, NLP).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama--3.3--70b-orange)

---

## 📋 Table des matières

- [Présentation](#-présentation)
- [Architecture](#-architecture)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Lancement](#-lancement)
- [API](#-api)
- [Structure du projet](#-structure-du-projet)

---

## 🎯 Présentation

**Agentic Doc Management** est une application web full-stack qui permet :
- d'**uploader et stocker** des documents (PDF, images, Word, etc.)
- d'**extraire automatiquement** leur contenu via OCR (Tesseract / PaddleOCR)
- de les **classifier intelligemment** par sujet grâce à Groq (Llama-3.3-70b)
- de les **indexer dans une base vectorielle** (ChromaDB) pour la recherche sémantique
- d'**interagir en langage naturel** via un chat RAG avec réponses en streaming

Le cœur du système est un **Orchestrateur Agentique** (boucle ReAct) qui sélectionne dynamiquement les outils adaptés à chaque requête.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│              Frontend (React + Vite)         │
│  Login · Dashboard · Upload · Chat · Profile │
└──────────────────────┬──────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────┐
│              Backend (FastAPI)               │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │     Orchestrator Agent (ReAct)       │   │
│  │  RAG Agent · OCR Agent · Class.Agent │   │
│  │           NLP Agent (spaCy)          │   │
│  └──────────────────────────────────────┘   │
│                                              │
│   SQLite      ChromaDB      MinIO            │
└──────────────────────┬──────────────────────┘
                       │
              Groq API (Llama-3.3-70b)
```

**Stack technique :**

| Couche | Technologie |
|---|---|
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Backend | FastAPI, SQLAlchemy, Alembic |
| LLM | Groq — Llama-3.3-70b-versatile |
| Embedding | intfloat/multilingual-e5-base (local, HuggingFace) |
| Base vectorielle | ChromaDB |
| OCR | Tesseract 5 + PaddleOCR + pix2tex |
| Stockage fichiers | MinIO (compatible S3) |
| Base de données | SQLite (aiosqlite) |

---

## 🛠️ Prérequis

| Outil | Version | Vérification |
|---|---|---|
| **Python** | 3.10+ | `python --version` |
| **Node.js** | 18+ | `node --version` |
| **Docker** | 20+ | `docker --version` |
| **Tesseract** | 5+ | `tesseract --version` |

### Installer Tesseract (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-fra poppler-utils
```

### Obtenir une clé API Groq (gratuit)

1. Créez un compte sur [console.groq.com](https://console.groq.com)
2. Générez une API Key
3. Renseignez-la dans `backend/.env`

---

## 🚀 Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/votre-username/docmanager_project.git
cd docmanager_project
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download fr_core_news_md
```

### 3. Frontend

```bash
cd ../frontend
npm install
```

### 4. Démarrer MinIO (stockage fichiers)

```bash
cd ../backend
docker compose up -d
```

---

## ⚙️ Configuration

```bash
cd backend
cp .env.example .env
```

Renseignez au minimum ces deux variables dans `backend/.env` :

```env
SECRET_KEY=une_clé_secrète_forte_de_32_caractères_minimum
GROQ_API_KEY=votre_clé_groq_ici
```

Les autres valeurs par défaut fonctionnent sans modification.

---

## ▶️ Lancement

**Terminal 1 — Backend :**
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend :**
```bash
cd frontend
npm run dev
```

| Service | URL |
|---|---|
| Application | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |

---

## 📡 API

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/auth/register` | Créer un compte |
| `POST` | `/auth/token` | Connexion (JWT) |
| `POST` | `/documents/upload` | Uploader un document |
| `GET` | `/documents/` | Lister les documents |
| `POST` | `/chat/stream` | Chat RAG (streaming SSE) |
| `GET` | `/dashboard/stats` | Statistiques |
| `WS` | `/ws/upload/{task_id}` | Suivi upload temps réel |

---

## 📁 Structure du projet

```
docmanager_project/
├── backend/
│   ├── agents/
│   │   ├── orchestrator_agent.py   # Boucle ReAct — cœur du système
│   │   ├── rag_agent.py            # Recherche sémantique (ChromaDB)
│   │   ├── ocr_agent.py            # Extraction texte (Tesseract/Paddle)
│   │   ├── classification_agent.py # Classification par sujet (Groq)
│   │   ├── nlp_agent.py            # Entités nommées (spaCy)
│   │   └── tools.py                # Outils de l'orchestrateur
│   ├── auth/                       # JWT + bcrypt
│   ├── core/                       # Config, DB, rate limiting
│   ├── models/                     # SQLAlchemy + Pydantic
│   ├── routes/                     # Endpoints FastAPI
│   ├── main.py
│   ├── requirements.txt
│   ├── docker-compose.yml
│   └── .env.example
│
└── frontend/
    └── src/
        ├── components/             # Composants UI réutilisables
        ├── pages/                  # Login, Chat, Upload, Dashboard, Profile
        └── store/                  # État global (Zustand)
```
