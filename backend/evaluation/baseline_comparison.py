"""
evaluation/baseline_comparison.py
-----------------------------------
Compare les performances du système actuel vs une baseline naïve.

Baseline OCR         → Tesseract seul (sans routing multi-moteur)
Baseline Classif.    → Classification par mots-clés uniquement (sans LLM)
Baseline RAG         → Recherche BM25 textuelle (sans embeddings)

Usage :
    cd backend
    python -m evaluation.baseline_comparison \
        --ocr-dataset  evaluation/data/ocr_dataset.json \
        --clf-dataset  evaluation/data/classification_dataset.json \
        --output       evaluation/results/baseline_comparison.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.metrics import cer, wer, classification_report, latency_stats, Timer


# ─────────────────────────────────────────────────────────────────────────────
# BASELINE OCR : Tesseract seul
# ─────────────────────────────────────────────────────────────────────────────

def baseline_ocr_tesseract(dataset: List[Dict]) -> Dict:
    """Baseline OCR : Tesseract pur sur toutes les images (sans routing)."""
    from agents.ocr_agent import _load_image, _ocr_tesseract
    results = []
    times_ms = []

    for sample in dataset:
        image_path = sample["image_path"]
        gt = sample["ground_truth"]
        if not os.path.exists(image_path):
            continue
        with open(image_path, "rb") as f:
            file_bytes = f.read()
        import numpy as np
        arr = np.frombuffer(file_bytes, np.uint8)
        import cv2
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            continue
        with Timer() as t:
            hyp = _ocr_tesseract(image)
        times_ms.append(t.elapsed_ms)
        results.append({
            "CER": cer(gt, hyp),
            "WER": wer(gt, hyp),
            "Accuracy": max(0.0, 1.0 - cer(gt, hyp)),
        })

    if not results:
        return {}

    avg = lambda key: round(sum(r[key] for r in results) / len(results), 4)
    return {
        "n": len(results),
        "CER_mean": avg("CER"),
        "WER_mean": avg("WER"),
        "Accuracy_mean": avg("Accuracy"),
        "latency": latency_stats(times_ms),
    }


# ─────────────────────────────────────────────────────────────────────────────
# BASELINE CLASSIFICATION : mots-clés seuls
# ─────────────────────────────────────────────────────────────────────────────

def baseline_classification_keywords(dataset: List[Dict]) -> Dict:
    """Baseline classification : keyword matching seul (pas de LLM)."""
    from agents.classification_agent import _keyword_classify
    y_true_s, y_pred_s = [], []
    y_true_t, y_pred_t = [], []
    times_ms = []

    for sample in dataset:
        true_s = sample["subject"]
        true_t = sample["doc_type"]
        with Timer() as t:
            result = _keyword_classify(sample["text"], "fr")
        times_ms.append(t.elapsed_ms)
        y_true_s.append(true_s)
        y_pred_s.append(result.subject)
        y_true_t.append(true_t)
        y_pred_t.append(result.doc_type)

    rep_s = classification_report(y_true_s, y_pred_s)
    rep_t = classification_report(y_true_t, y_pred_t)
    return {
        "subject": {
            "accuracy": rep_s["accuracy"],
            "macro_f1": rep_s["macro_f1"],
            "weighted_f1": rep_s["weighted_f1"],
        },
        "doc_type": {
            "accuracy": rep_t["accuracy"],
            "macro_f1": rep_t["macro_f1"],
            "weighted_f1": rep_t["weighted_f1"],
        },
        "latency": latency_stats(times_ms),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SYSTÈME ACTUEL
# ─────────────────────────────────────────────────────────────────────────────

def current_ocr(dataset: List[Dict]) -> Dict:
    """Système actuel : routing multi-moteur (Tesseract + PaddleOCR + pix2tex)."""
    from agents.ocr_agent import extract_text
    results = []
    times_ms = []

    for sample in dataset:
        image_path = sample["image_path"]
        gt = sample["ground_truth"]
        ext = Path(image_path).suffix.lstrip(".")
        if not os.path.exists(image_path):
            continue
        with open(image_path, "rb") as f:
            file_bytes = f.read()
        with Timer() as t:
            hyp, _ = extract_text(file_bytes, ext)
        times_ms.append(t.elapsed_ms)
        results.append({
            "CER": cer(gt, hyp),
            "WER": wer(gt, hyp),
            "Accuracy": max(0.0, 1.0 - cer(gt, hyp)),
        })

    if not results:
        return {}
    avg = lambda key: round(sum(r[key] for r in results) / len(results), 4)
    return {
        "n": len(results),
        "CER_mean": avg("CER"),
        "WER_mean": avg("WER"),
        "Accuracy_mean": avg("Accuracy"),
        "latency": latency_stats(times_ms),
    }


def current_classification(dataset: List[Dict]) -> Dict:
    """Système actuel : classification LLM (Groq)."""
    from agents.classification_agent import classify_document
    y_true_s, y_pred_s = [], []
    y_true_t, y_pred_t = [], []
    times_ms = []

    for sample in dataset:
        true_s = sample["subject"]
        true_t = sample["doc_type"]
        with Timer() as t:
            result = classify_document(sample["text"])
        times_ms.append(t.elapsed_ms)
        y_true_s.append(true_s)
        y_pred_s.append(result.subject)
        y_true_t.append(true_t)
        y_pred_t.append(result.doc_type)

    rep_s = classification_report(y_true_s, y_pred_s)
    rep_t = classification_report(y_true_t, y_pred_t)
    return {
        "subject": {
            "accuracy": rep_s["accuracy"],
            "macro_f1": rep_s["macro_f1"],
            "weighted_f1": rep_s["weighted_f1"],
        },
        "doc_type": {
            "accuracy": rep_t["accuracy"],
            "macro_f1": rep_t["macro_f1"],
            "weighted_f1": rep_t["weighted_f1"],
        },
        "latency": latency_stats(times_ms),
    }


# ─────────────────────────────────────────────────────────────────────────────
# RAPPORT COMPARATIF
# ─────────────────────────────────────────────────────────────────────────────

def print_comparison_ocr(baseline: Dict, current: Dict):
    def delta(curr, base, key):
        d = curr.get(key, 0) - base.get(key, 0)
        sign = "▲" if d > 0 else "▼"
        color_good = key == "Accuracy_mean"
        return f"{sign} {abs(d):.4f}"

    print(f"\n  {'Métrique':<20} {'Baseline':>12} {'Système actuel':>15} {'Delta':>10}")
    print(f"  {'─'*60}")
    for key, label in [("CER_mean","CER moyen"),("WER_mean","WER moyen"),("Accuracy_mean","Accuracy moy.")]:
        b = baseline.get(key, 0)
        c = current.get(key, 0)
        d = c - b
        sign = "▲" if d > 0 else "▼"
        print(f"  {label:<20} {b:>12.4f} {c:>15.4f} {sign} {abs(d):.4f}")
    bl = baseline.get("latency", {}).get("mean_ms", 0)
    cl = current.get("latency", {}).get("mean_ms", 0)
    print(f"  {'Latence moy.(ms)':<20} {bl:>12.0f} {cl:>15.0f} {'▲' if cl>bl else '▼'} {abs(cl-bl):.0f}")


def print_comparison_clf(baseline: Dict, current: Dict):
    print(f"\n  {'Métrique':<25} {'Baseline':>12} {'Système actuel':>15} {'Delta':>10}")
    print(f"  {'─'*65}")
    for task, label in [("subject","Sujet"),("doc_type","Type doc")]:
        b = baseline.get(task, {})
        c = current.get(task, {})
        for key, kl in [("accuracy","Accuracy"),("macro_f1","Macro F1"),("weighted_f1","Weighted F1")]:
            bv = b.get(key, 0)
            cv = c.get(key, 0)
            d = cv - bv
            sign = "▲" if d >= 0 else "▼"
            print(f"  {label+' '+kl:<25} {bv:>12.4f} {cv:>15.4f} {sign} {abs(d):.4f}")


def run_comparison(
    ocr_dataset_path: str = None,
    clf_dataset_path: str = None,
    output_path: str = "evaluation/results/baseline_comparison.json"
) -> Dict:

    report = {}

    print(f"\n{'='*65}")
    print("  COMPARAISON BASELINE vs SYSTÈME ACTUEL")
    print(f"{'='*65}")

    if ocr_dataset_path and os.path.exists(ocr_dataset_path):
        print("\n[1/2] Chargement dataset OCR...")
        with open(ocr_dataset_path) as f:
            ocr_data = json.load(f)
        print("  Baseline Tesseract...")
        bl_ocr = baseline_ocr_tesseract(ocr_data)
        print("  Système actuel (multi-moteur)...")
        cur_ocr = current_ocr(ocr_data)
        print("\n  ── OCR ──")
        print_comparison_ocr(bl_ocr, cur_ocr)
        report["ocr"] = {"baseline": bl_ocr, "current": cur_ocr}

    if clf_dataset_path and os.path.exists(clf_dataset_path):
        print("\n[2/2] Chargement dataset Classification...")
        with open(clf_dataset_path) as f:
            clf_data = json.load(f)
        print("  Baseline mots-clés...")
        bl_clf = baseline_classification_keywords(clf_data)
        print("  Système actuel (LLM)...")
        cur_clf = current_classification(clf_data)
        print("\n  ── Classification ──")
        print_comparison_clf(bl_clf, cur_clf)
        report["classification"] = {"baseline": bl_clf, "current": cur_clf}

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Rapport exporté → {output_path}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comparaison Baseline DocManager")
    parser.add_argument("--ocr-dataset", default=None)
    parser.add_argument("--clf-dataset", default=None)
    parser.add_argument("--output",      default="evaluation/results/baseline_comparison.json")
    args = parser.parse_args()
    run_comparison(args.ocr_dataset, args.clf_dataset, args.output)
