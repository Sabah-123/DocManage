"""
evaluation/benchmark_rag.py
----------------------------
Benchmark du pipeline RAG (Retrieval-Augmented Generation).

Métriques évaluées :
  Retrieval : Precision@k, Recall@k, MAP, MRR, nDCG@k
  Generation : ROUGE-L, Cosine similarity (réponse vs référence)
  Latence    : temps retrieval, temps génération, temps total

Usage :
    cd backend
    python -m evaluation.benchmark_rag \
        --dataset evaluation/data/rag_dataset.json \
        --user-id 1

Format du dataset JSON :
[
  {
    "question": "Quelle est la définition de la dérivée ?",
    "relevant_doc_ids": [1, 3],          # IDs SQL des docs pertinents
    "reference_answer": "La dérivée est..."  # optionnel pour ROUGE
  },
  ...
]
"""

import argparse
import json
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.rag_agent import query_documents
from evaluation.metrics import (
    precision_at_k, recall_at_k, average_precision,
    mean_average_precision, mrr, ndcg_at_k,
    latency_stats, Timer
)


# ── ROUGE-L (sans dépendance externe) ──────────────────────────────────────

def _lcs_length(a: List[str], b: List[str]) -> int:
    """Longueur de la plus longue sous-séquence commune."""
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            curr[j] = prev[j - 1] + 1 if a[i-1] == b[j-1] else max(prev[j], curr[j-1])
        prev = curr
    return prev[n]


def rouge_l(reference: str, hypothesis: str) -> Dict[str, float]:
    """ROUGE-L : Precision, Recall, F1 basés sur LCS."""
    ref_tokens  = reference.lower().split()
    hyp_tokens  = hypothesis.lower().split()
    lcs = _lcs_length(ref_tokens, hyp_tokens)
    prec = lcs / len(hyp_tokens) if hyp_tokens else 0.0
    rec  = lcs / len(ref_tokens)  if ref_tokens  else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}


def run_benchmark(
    dataset_path: str,
    user_id: int,
    k_values: List[int] = [1, 3, 5],
    output_path: str = None,
    verbose: bool = True
) -> Dict:

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset: List[Dict] = json.load(f)

    retrieval_times = []
    generation_times = []
    total_times = []
    samples = []
    queries_map: List = []  # pour MAP/MRR

    rouge_scores = []

    print(f"\n{'='*65}")
    print(f"  BENCHMARK RAG — {len(dataset)} requêtes  (user_id={user_id})")
    print(f"  k évalués : {k_values}")
    print(f"{'='*65}\n")

    for i, sample in enumerate(dataset, 1):
        question    = sample["question"]
        relevant    = sample.get("relevant_doc_ids", [])
        reference   = sample.get("reference_answer", "")
        history     = sample.get("history", "")

        with Timer() as t_total:
            result = query_documents(
                question=question,
                user_id=user_id,
                top_k=max(k_values),
                history=history,
            )

        total_times.append(t_total.elapsed_ms)

        # Extraire les doc_ids réels des sources retournées
        sources = result.get("sources", [])
        retrieved_ids = []
        for s in sources:
            if s.doc_id and s.doc_id not in retrieved_ids:
                retrieved_ids.append(s.doc_id)

        # Métriques retrieval par k
        pk = {k: precision_at_k(relevant, retrieved_ids, k) for k in k_values}
        rk = {k: recall_at_k(relevant, retrieved_ids, k) for k in k_values}
        nk = {k: ndcg_at_k(relevant, retrieved_ids, k) for k in k_values}
        ap = average_precision(relevant, retrieved_ids)
        queries_map.append((relevant, retrieved_ids))

        # ROUGE-L si référence disponible
        rouge = rouge_l(reference, result.get("answer", "")) if reference else {}

        if rouge:
            rouge_scores.append(rouge["f1"])

        sample_result = {
            "id": i,
            "question": question,
            "n_sources": len(sources),
            "precision_at_k": pk,
            "recall_at_k": rk,
            "ndcg_at_k": nk,
            "average_precision": round(ap, 4),
            "rouge_l": rouge,
            "total_ms": round(t_total.elapsed_ms, 2),
            "answer_preview": result.get("answer", "")[:200],
        }
        samples.append(sample_result)

        if verbose:
            rouge_str = f"  ROUGE-L={rouge.get('f1', 0):.3f}" if rouge else ""
            pk_str = "  ".join(f"P@{k}={pk[k]:.2f}" for k in k_values)
            print(f"  [{i:02d}] {pk_str}{rouge_str}  {t_total.elapsed_ms:.0f}ms")
            print(f"       Q: {question[:70]}")

    # ── Statistiques globales ──────────────────────────────────────────────
    map_score  = mean_average_precision(queries_map)
    mrr_score  = mrr(queries_map)
    lat_total  = latency_stats(total_times)
    avg_rouge  = sum(rouge_scores) / len(rouge_scores) if rouge_scores else None

    avg_pk = {k: round(sum(s["precision_at_k"][k] for s in samples) / len(samples), 4)
              for k in k_values} if samples else {}
    avg_rk = {k: round(sum(s["recall_at_k"][k] for s in samples) / len(samples), 4)
              for k in k_values} if samples else {}
    avg_nk = {k: round(sum(s["ndcg_at_k"][k] for s in samples) / len(samples), 4)
              for k in k_values} if samples else {}

    summary = {
        "n_queries": len(dataset),
        "user_id": user_id,
        "k_values": k_values,
        "retrieval": {
            "MAP": round(map_score, 4),
            "MRR": round(mrr_score, 4),
            "avg_precision_at_k": avg_pk,
            "avg_recall_at_k": avg_rk,
            "avg_ndcg_at_k": avg_nk,
        },
        "generation": {
            "avg_rouge_l_f1": round(avg_rouge, 4) if avg_rouge is not None else "N/A",
        },
        "latency_ms": lat_total,
        "samples": samples,
    }

    print(f"\n{'─'*65}")
    print(f"  RÉSULTATS RAG")
    print(f"  MAP         : {map_score:.4f}")
    print(f"  MRR         : {mrr_score:.4f}")
    for k in k_values:
        print(f"  P@{k}={avg_pk.get(k,0):.4f}  R@{k}={avg_rk.get(k,0):.4f}  nDCG@{k}={avg_nk.get(k,0):.4f}")
    if avg_rouge is not None:
        print(f"  ROUGE-L F1  : {avg_rouge:.4f}")
    print(f"  Latence moy.: {lat_total.get('mean_ms',0):.0f} ms  "
          f"(p95={lat_total.get('p95_ms',0):.0f} ms)")
    print(f"{'─'*65}")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n  Résultats exportés → {output_path}")

    return summary


def generate_sample_dataset(output_path: str = "evaluation/data/rag_dataset_sample.json"):
    """Génère un dataset RAG de démonstration."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    samples = [
        {
            "question": "Quelle est la définition de la dérivée d'une fonction ?",
            "relevant_doc_ids": [1],
            "reference_answer": "La dérivée d'une fonction f en un point x est la limite du taux d'accroissement quand h tend vers 0."
        },
        {
            "question": "Comment fonctionne un algorithme de tri rapide ?",
            "relevant_doc_ids": [2],
            "reference_answer": "Le tri rapide (quicksort) utilise un pivot pour diviser le tableau en sous-tableaux, avec une complexité moyenne de O(n log n)."
        },
        {
            "question": "Quelles sont les lois de Newton ?",
            "relevant_doc_ids": [3],
            "reference_answer": "Les trois lois de Newton sont : l'inertie, F=ma, et l'action-réaction."
        }
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"Dataset exemple créé : {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark RAG DocManager")
    parser.add_argument("--dataset",  default="evaluation/data/rag_dataset.json")
    parser.add_argument("--output",   default="evaluation/results/rag_results.json")
    parser.add_argument("--user-id",  type=int, default=1, help="ID utilisateur ChromaDB")
    parser.add_argument("--k",        nargs="+", type=int, default=[1, 3, 5])
    parser.add_argument("--generate-sample", action="store_true")
    args = parser.parse_args()

    if args.generate_sample:
        generate_sample_dataset()
        sys.exit(0)

    run_benchmark(args.dataset, args.user_id, args.k, args.output)
