"""
evaluation/benchmark_ocr.py
----------------------------
Benchmark du module OCR (Tesseract / PaddleOCR / pix2tex).

Usage :
    cd backend
    python -m evaluation.benchmark_ocr --dataset evaluation/data/ocr_dataset.json

Format du dataset JSON :
[
  {
    "image_path": "evaluation/data/images/doc1.png",
    "ground_truth": "Texte de référence exact...",
    "engine_expected": "tesseract"   # optionnel
  },
  ...
]
"""

import argparse
import json
import sys
import os
import time
from pathlib import Path
from typing import List, Dict

# Ajouter le répertoire backend au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.ocr_agent import extract_text
from evaluation.metrics import cer, wer, ocr_accuracy, latency_stats, Timer


def run_benchmark(dataset_path: str, output_path: str = None, verbose: bool = True) -> Dict:
    """
    Exécute le benchmark OCR sur le dataset et retourne les résultats.
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset: List[Dict] = json.load(f)

    results = []
    times_ms = []
    engine_times: Dict[str, List[float]] = {}

    print(f"\n{'='*60}")
    print(f"  BENCHMARK OCR — {len(dataset)} documents")
    print(f"{'='*60}\n")

    for i, sample in enumerate(dataset, 1):
        image_path = sample["image_path"]
        gt = sample["ground_truth"]
        ext = Path(image_path).suffix.lstrip(".")

        if not os.path.exists(image_path):
            print(f"  [SKIP] {image_path} introuvable")
            continue

        with open(image_path, "rb") as img_f:
            file_bytes = img_f.read()

        with Timer() as t:
            hyp, engine_used = extract_text(file_bytes, ext)

        elapsed = t.elapsed_ms
        times_ms.append(elapsed)
        engine_times.setdefault(engine_used, []).append(elapsed)

        c = cer(gt, hyp)
        w = wer(gt, hyp)
        acc = ocr_accuracy(gt, hyp)

        sample_result = {
            "id": i,
            "file": os.path.basename(image_path),
            "engine_used": engine_used,
            "engine_expected": sample.get("engine_expected", ""),
            "CER": round(c, 4),
            "WER": round(w, 4),
            "Accuracy": round(acc, 4),
            "latency_ms": round(elapsed, 2),
            "gt_chars": len(gt),
            "hyp_chars": len(hyp),
        }
        results.append(sample_result)

        if verbose:
            status = "✅" if acc >= 0.85 else "⚠️ " if acc >= 0.60 else "❌"
            print(f"  [{i:02d}] {status} {os.path.basename(image_path):<30} "
                  f"Engine: {engine_used:<12} CER={c:.3f}  WER={w:.3f}  "
                  f"Acc={acc:.3f}  {elapsed:.0f}ms")

    # ── Statistiques globales ──────────────────────────────────────────────
    global_lat = latency_stats(times_ms)
    engine_lat = {e: latency_stats(ts) for e, ts in engine_times.items()}

    avg_cer = sum(r["CER"] for r in results) / len(results) if results else 0
    avg_wer = sum(r["WER"] for r in results) / len(results) if results else 0
    avg_acc = sum(r["Accuracy"] for r in results) / len(results) if results else 0

    summary = {
        "n_docs": len(results),
        "global_metrics": {
            "CER_mean": round(avg_cer, 4),
            "WER_mean": round(avg_wer, 4),
            "Accuracy_mean": round(avg_acc, 4),
        },
        "latency_global_ms": global_lat,
        "latency_by_engine_ms": engine_lat,
        "samples": results,
    }

    print(f"\n{'─'*60}")
    print(f"  RÉSULTATS GLOBAUX")
    print(f"  CER moyen     : {avg_cer:.4f}  ({avg_cer*100:.1f}%)")
    print(f"  WER moyen     : {avg_wer:.4f}  ({avg_wer*100:.1f}%)")
    print(f"  Accuracy moy. : {avg_acc:.4f}  ({avg_acc*100:.1f}%)")
    print(f"  Latence moy.  : {global_lat.get('mean_ms',0):.0f} ms  "
          f"(p95={global_lat.get('p95_ms',0):.0f} ms)")
    print(f"{'─'*60}")

    for engine, lat in engine_lat.items():
        print(f"  Moteur [{engine}]: n={lat['n']} | "
              f"moy={lat['mean_ms']:.0f}ms | p95={lat.get('p95_ms',0):.0f}ms")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n  Résultats exportés → {output_path}")

    return summary


def generate_sample_dataset(output_path: str = "evaluation/data/ocr_dataset_sample.json"):
    """Génère un dataset de démonstration (à remplacer par de vraies données)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sample = [
        {
            "image_path": "evaluation/data/images/sample_text.png",
            "ground_truth": "Ceci est un texte de démonstration pour tester l'OCR.",
            "engine_expected": "tesseract"
        },
        {
            "image_path": "evaluation/data/images/sample_formula.png",
            "ground_truth": "$$E = mc^2$$",
            "engine_expected": "pix2tex"
        }
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
    print(f"Dataset exemple créé : {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark OCR DocManager")
    parser.add_argument("--dataset",  default="evaluation/data/ocr_dataset.json",
                        help="Chemin vers le dataset JSON")
    parser.add_argument("--output",   default="evaluation/results/ocr_results.json",
                        help="Chemin de sortie des résultats JSON")
    parser.add_argument("--generate-sample", action="store_true",
                        help="Génère un dataset exemple et quitte")
    args = parser.parse_args()

    if args.generate_sample:
        generate_sample_dataset()
        sys.exit(0)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    run_benchmark(args.dataset, args.output)
