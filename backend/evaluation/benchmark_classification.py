"""
evaluation/benchmark_classification.py
----------------------------------------
Benchmark de l'agent de classification (sujet + type de document).

Usage :
    cd backend
    python -m evaluation.benchmark_classification \
        --dataset evaluation/data/classification_dataset.json

Format du dataset JSON :
[
  {
    "text": "Introduction aux dérivées. f'(x) = lim...",
    "subject": "Mathématiques",
    "doc_type": "Cours",
    "confidence_min": 0.6  # optionnel
  },
  ...
]
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.classification_agent import classify_document
from evaluation.metrics import classification_report, confusion_matrix, latency_stats, Timer


def run_benchmark(dataset_path: str, output_path: str = None, verbose: bool = True) -> Dict:
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset: List[Dict] = json.load(f)

    y_true_subject, y_pred_subject = [], []
    y_true_type,    y_pred_type    = [], []
    times_ms = []
    confidence_values = []
    samples = []

    print(f"\n{'='*65}")
    print(f"  BENCHMARK CLASSIFICATION — {len(dataset)} documents")
    print(f"{'='*65}\n")

    for i, sample in enumerate(dataset, 1):
        text = sample["text"]
        true_subject = sample["subject"]
        true_type    = sample["doc_type"]

        with Timer() as t:
            result = classify_document(text)

        elapsed = t.elapsed_ms
        times_ms.append(elapsed)
        confidence_values.append(result.confidence)

        pred_subject = result.subject
        pred_type    = result.doc_type

        subject_ok = pred_subject == true_subject
        type_ok    = pred_type    == true_type
        both_ok    = subject_ok and type_ok

        y_true_subject.append(true_subject)
        y_pred_subject.append(pred_subject)
        y_true_type.append(true_type)
        y_pred_type.append(pred_type)

        sample_result = {
            "id": i,
            "true_subject": true_subject,
            "pred_subject": pred_subject,
            "subject_ok": subject_ok,
            "true_type": true_type,
            "pred_type": pred_type,
            "type_ok": type_ok,
            "confidence": round(result.confidence, 3),
            "language": result.language,
            "latency_ms": round(elapsed, 2),
        }
        samples.append(sample_result)

        if verbose:
            status = "✅" if both_ok else ("⚠️ " if (subject_ok or type_ok) else "❌")
            print(f"  [{i:02d}] {status} Subj: {true_subject:<15}→{pred_subject:<15} "
                  f"Type: {true_type:<10}→{pred_type:<10} "
                  f"Conf={result.confidence:.2f}  {elapsed:.0f}ms")

    # ── Rapports ──────────────────────────────────────────────────────────
    report_subject = classification_report(y_true_subject, y_pred_subject)
    report_type    = classification_report(y_true_type, y_pred_type)
    cm_subject     = confusion_matrix(y_true_subject, y_pred_subject)
    cm_type        = confusion_matrix(y_true_type, y_pred_type)
    lat_stats      = latency_stats(times_ms)
    avg_conf       = sum(confidence_values) / len(confidence_values) if confidence_values else 0

    summary = {
        "n_docs": len(dataset),
        "subject_classification": report_subject,
        "type_classification": report_type,
        "confusion_matrix_subject": cm_subject,
        "confusion_matrix_type": cm_type,
        "latency_ms": lat_stats,
        "avg_confidence": round(avg_conf, 4),
        "samples": samples,
    }

    print(f"\n{'─'*65}")
    print(f"  RÉSULTATS — SUJET")
    print(f"  Accuracy   : {report_subject['accuracy']:.4f}  "
          f"({report_subject['accuracy']*100:.1f}%)")
    print(f"  F1 macro   : {report_subject['macro_f1']:.4f}")
    print(f"  F1 weighted: {report_subject['weighted_f1']:.4f}")
    print(f"\n  RÉSULTATS — TYPE DOCUMENT")
    print(f"  Accuracy   : {report_type['accuracy']:.4f}  "
          f"({report_type['accuracy']*100:.1f}%)")
    print(f"  F1 macro   : {report_type['macro_f1']:.4f}")
    print(f"  F1 weighted: {report_type['weighted_f1']:.4f}")
    print(f"\n  Confiance moy.: {avg_conf:.3f}")
    print(f"  Latence moy.  : {lat_stats.get('mean_ms',0):.0f} ms  "
          f"(p95={lat_stats.get('p95_ms',0):.0f} ms)")
    print(f"{'─'*65}")

    # Détail par classe sujet
    print(f"\n  Détail par matière :")
    for lbl, stats in report_subject["per_class"].items():
        print(f"    {lbl:<20} P={stats['precision']:.3f}  R={stats['recall']:.3f}  "
              f"F1={stats['f1']:.3f}  n={stats['support']}")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n  Résultats exportés → {output_path}")

    return summary


def generate_sample_dataset(output_path: str = "evaluation/data/classification_dataset_sample.json"):
    """Génère un dataset de démonstration."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    samples = [
        {
            "text": "Chapitre 1 : Les dérivées. Définition : la dérivée d'une fonction f en x0 est la limite du taux d'accroissement. Théorème fondamental du calcul intégral.",
            "subject": "Mathématiques",
            "doc_type": "Cours"
        },
        {
            "text": "Exercice 1 : Résoudre le système d'équations. Calculer la dérivée de f(x)=x²+3x. Trouver les extrema.",
            "subject": "Mathématiques",
            "doc_type": "Exercice"
        },
        {
            "text": "Introduction à Python. Les variables, fonctions, listes. Algorithme de tri rapide. Complexité O(n log n).",
            "subject": "Informatique",
            "doc_type": "Cours"
        },
        {
            "text": "Examen final de Physique. Durée : 3h. Barème : 20 points. Partie 1 : Thermodynamique. Calculer l'énergie cinétique.",
            "subject": "Physique",
            "doc_type": "Examen"
        },
        {
            "text": "Rapport de stage. Introduction. Objectifs du stage. Résultats obtenus. Analyse et conclusion. Recommandations.",
            "subject": "Autre",
            "doc_type": "Rapport"
        },
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"Dataset exemple créé : {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Classification DocManager")
    parser.add_argument("--dataset",  default="evaluation/data/classification_dataset.json")
    parser.add_argument("--output",   default="evaluation/results/classification_results.json")
    parser.add_argument("--generate-sample", action="store_true")
    args = parser.parse_args()

    if args.generate_sample:
        generate_sample_dataset()
        sys.exit(0)

    run_benchmark(args.dataset, args.output)
