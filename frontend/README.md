# DocManager — Frontend

Interface React + Vite + Tailwind CSS pour le système de gestion documentaire agentique.

---

## Prérequis

- Node.js 18+
- Le backend FastAPI doit être démarré sur http://localhost:8000

---

## Installation et démarrage

```bash
npm install
npm run dev
```

L'application est disponible sur http://localhost:5173

---

## Pages

| Route | Description |
|-------|-------------|
| `/login` | Connexion / Inscription avec JWT |
| `/dashboard` | Statistiques, graphiques Recharts, activité récente |
| `/upload` | Drag & drop, barre de progression, polling statut |
| `/chat` | Chat conversationnel avec streaming SSE, rendu KaTeX |
| `/documents` | Arborescence par matière, filtres, rename, download |
| `/profile` | Info utilisateur, stack technique, déconnexion |

---

## Fonctionnalités clés

- **Streaming SSE** : réponses affichées token par token (comme ChatGPT)
- **KaTeX** : formules LaTeX rendues proprement dans le chat (`$$\frac{d}{dx}$$`)
- **Drag & drop** : upload multi-fichiers avec barre de progression
- **Polling automatique** : suivi du traitement OCR/classification en temps réel
- **Arborescence** : documents groupés par matière détectée automatiquement
- **Renommage inline** : double-clic sur le nom du document

---

## Structure

```
src/
├── pages/
│   ├── LoginPage.tsx        # Auth (login + register)
│   ├── DashboardPage.tsx    # Stats + graphiques
│   ├── UploadPage.tsx       # Upload + progression
│   ├── ChatPage.tsx         # Chat + streaming SSE
│   ├── DocumentsPage.tsx    # Liste + arborescence
│   └── ProfilePage.tsx      # Profil + stack info
├── components/
│   └── layout/
│       ├── Sidebar.tsx      # Navigation latérale
│       └── AppLayout.tsx    # Layout principal + guard JWT
├── store/
│   ├── authStore.ts         # Zustand : auth + JWT
│   └── documentsStore.ts    # Zustand : documents
├── lib/
│   └── api.ts               # Axios + types + helpers API
├── main.tsx                 # Routing React Router v6
└── index.css                # Tailwind + composants globaux
```
