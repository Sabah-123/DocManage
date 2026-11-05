# DocManager — Rapport d'Évaluation

**Généré le :** 2026-05-17 04:22

---

## Résumé exécutif

| Module | CER | WER | Accuracy | Latence moy. |
|--------|-----|-----|----------|--------------|
| OCR | 0.5274 | 0.7881 | 0.4762 | 2978 ms |

| Module | Accuracy | Macro F1 | Weighted F1 | Latence moy. |
|--------|----------|----------|-------------|--------------|
| Classification (Sujet) | 1.0000 | 1.0000 | 1.0000 | 344 ms |
| Classification (Type) | 0.7059 | 0.4500 | 0.6588 | - |

| Module | MAP | MRR | Latence moy. |
|--------|-----|-----|--------------|
| RAG | 0.1528 | 0.2500 | 7475 ms |

---
## 1. Module OCR

### 1.1 Métriques globales

| Métrique | Valeur |
|----------|--------|
| CER_mean | 0.5274 |
| WER_mean | 0.7881 |
| Accuracy_mean | 0.4762 |

### 1.2 Métriques par moteur

| Moteur | n | CER moy. | WER moy. | Accuracy moy. | Latence moy. (ms) |
|--------|---|----------|----------|---------------|-------------------|
| paddle | 9 | - | - | - | 2978 |

### 1.3 Graphiques

![ocr_global_metrics.png](plots/ocr_global_metrics.png)
![ocr_per_doc.png](plots/ocr_per_doc.png)
![ocr_latency_engine.png](plots/ocr_latency_engine.png)

---
## 2. Module Classification

### 2.1 Métriques globales — Sujet

| Métrique | Valeur |
|----------|--------|
| accuracy | 1.0000 |
| macro_precision | 1.0000 |
| macro_recall | 1.0000 |
| macro_f1 | 1.0000 |
| weighted_f1 | 1.0000 |

### 2.2 Détail par matière

| Matière | Precision | Recall | F1 | Support |
|---------|-----------|--------|-----|---------|
| Autre | 1.000 | 1.000 | 1.000 | 5 |
| Biologie | 1.000 | 1.000 | 1.000 | 2 |
| Chimie | 1.000 | 1.000 | 1.000 | 1 |
| Informatique | 1.000 | 1.000 | 1.000 | 1 |
| Langues | 1.000 | 1.000 | 1.000 | 2 |
| Mathématiques | 1.000 | 1.000 | 1.000 | 2 |
| Physique | 1.000 | 1.000 | 1.000 | 1 |
| Économie | 1.000 | 1.000 | 1.000 | 3 |

### 2.3 Graphiques
![clf_global.png](plots/clf_global.png)
![clf_per_class.png](plots/clf_per_class.png)
![clf_confusion_matrix.png](plots/clf_confusion_matrix.png)

---
## 3. Module RAG

### 3.1 Métriques Retrieval

| Métrique | Valeur |
|----------|--------|
| MAP | 0.1528 |
| MRR | 0.2500 |
| Precision@1 | 0.2500 |
| Precision@3 | 0.0833 |
| Precision@5 | 0.0500 |
| Recall@1 | 0.1528 |
| Recall@3 | 0.1528 |
| Recall@5 | 0.1528 |
| nDCG@1 | 0.2500 |
| nDCG@3 | 0.1735 |
| nDCG@5 | 0.1735 |
| ROUGE-L F1 | 0.0795 |

### 3.2 Graphiques
![rag_retrieval.png](plots/rag_retrieval.png)
![rag_latency.png](plots/rag_latency.png)

---
## 4. Comparaison Baseline

### 4.1 OCR — Tesseract seul vs Multi-moteur

| Métrique | Baseline (Tesseract) | Système actuel | Gain |
|----------|---------------------|----------------|------|
| CER | 0.6540 | 0.5274 | -0.1266 |
| WER | 0.9332 | 0.7881 | -0.1451 |
| Accuracy | 0.3553 | 0.4762 | +0.1209 |

### 4.2 Classification — Mots-clés vs LLM Groq

| Tâche | Métrique | Baseline | Système actuel | Gain |
|-------|----------|----------|----------------|------|
| subject | accuracy | 0.5294 | 1.0000 | +0.4706 |
| subject | macro_f1 | 0.4445 | 1.0000 | +0.5555 |
| doc_type | accuracy | 0.5882 | 0.6471 | +0.0589 |
| doc_type | macro_f1 | 0.4583 | 0.4190 | -0.0393 |

---
## 5. Dashboard Global

![Dashboard](plots/dashboard_global.png)

---
*Rapport généré automatiquement par `evaluation/run_all.py`*