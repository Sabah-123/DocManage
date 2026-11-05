"""
evaluation/visualize.py
-----------------------
Génère des graphiques comparatifs à partir des résultats JSON des benchmarks.

Usage :
    cd backend
    python -m evaluation.visualize --results-dir evaluation/results --output-dir evaluation/plots
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("[WARN] matplotlib non installé. Installer avec : pip install matplotlib")


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _style():
    plt.rcParams.update({
        "figure.facecolor": "#1a1a2e",
        "axes.facecolor":   "#16213e",
        "axes.edgecolor":   "#0f3460",
        "axes.labelcolor":  "#e0e0e0",
        "xtick.color":      "#e0e0e0",
        "ytick.color":      "#e0e0e0",
        "text.color":       "#e0e0e0",
        "grid.color":       "#0f3460",
        "grid.linestyle":   "--",
        "grid.alpha":       0.5,
        "font.family":      "DejaVu Sans",
    })


COLORS = ["#e94560", "#0f3460", "#53d8fb", "#f5a623", "#7ed321", "#bd10e0"]


# ─────────────────────────────────────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────────────────────────────────────

def plot_ocr(results: dict, output_dir: str):
    _style()
    os.makedirs(output_dir, exist_ok=True)

    # ── Fig 1 : métriques globales + par moteur ───────────────────────────
    by_engine = results.get("by_engine") or results.get("latency_by_engine_ms", {})
    global_m = results.get("global_metrics", {})

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Benchmark OCR — DocManager", fontsize=14, fontweight="bold")

    metrics = ["CER_mean", "WER_mean", "Accuracy_mean"]
    labels_m = ["CER", "WER", "Accuracy"]
    colors_m = ["#e94560", "#f5a623", "#7ed321"]

    for ax, metric, label, color in zip(axes, metrics, labels_m, colors_m):
        val = global_m.get(metric, 0)
        ax.bar(["Global"], [val], color=color, alpha=0.85, width=0.4)
        ax.set_title(label, fontsize=11)
        ax.set_ylim(0, 1)
        ax.axhline(y=val, color="white", linestyle="--", alpha=0.3)
        ax.text(0, val + 0.02, f"{val:.3f}", ha="center", color="white", fontsize=12, fontweight="bold")
        ax.grid(axis="y")

    plt.tight_layout()
    out = os.path.join(output_dir, "ocr_global_metrics.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Graphique sauvegardé : {out}")

    # ── Fig 2 : CER/WER par document ─────────────────────────────────────
    samples = results.get("samples", [])
    if samples:
        fig, ax = plt.subplots(figsize=(max(10, len(samples)*0.8), 5))
        x = np.arange(len(samples))
        width = 0.35
        cers = [s["CER"] for s in samples]
        wers = [s["WER"] for s in samples]
        ax.bar(x - width/2, cers, width, label="CER", color="#e94560", alpha=0.85)
        ax.bar(x + width/2, wers, width, label="WER", color="#f5a623", alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels([s["file"][:15] for s in samples], rotation=45, ha="right", fontsize=8)
        ax.set_title("CER / WER par document", fontsize=12)
        ax.set_ylabel("Taux d'erreur")
        ax.legend()
        ax.grid(axis="y")
        plt.tight_layout()
        out2 = os.path.join(output_dir, "ocr_per_doc.png")
        plt.savefig(out2, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Graphique sauvegardé : {out2}")

    # ── Fig 3 : Latence par moteur ────────────────────────────────────────
    lat_engine = results.get("latency_by_engine_ms", {})
    if lat_engine:
        engines = list(lat_engine.keys())
        means = [lat_engine[e].get("mean_ms", 0) for e in engines]
        p95s  = [lat_engine[e].get("p95_ms", 0)  for e in engines]
        x = np.arange(len(engines))
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(x - 0.2, means, 0.4, label="Moy (ms)", color="#53d8fb", alpha=0.85)
        ax.bar(x + 0.2, p95s,  0.4, label="P95 (ms)", color="#e94560", alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(engines)
        ax.set_title("Latence OCR par moteur", fontsize=12)
        ax.set_ylabel("Temps (ms)")
        ax.legend()
        ax.grid(axis="y")
        plt.tight_layout()
        out3 = os.path.join(output_dir, "ocr_latency_engine.png")
        plt.savefig(out3, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Graphique sauvegardé : {out3}")


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def plot_classification(results: dict, output_dir: str):
    _style()
    os.makedirs(output_dir, exist_ok=True)

    # ── Fig 1 : Accuracy / F1 global ─────────────────────────────────────
    subj = results.get("subject_classification", {})
    typ  = results.get("type_classification", {})

    categories = ["Accuracy", "Macro F1", "Weighted F1"]
    subj_vals = [subj.get("accuracy", 0), subj.get("macro_f1", 0), subj.get("weighted_f1", 0)]
    type_vals = [typ.get("accuracy",  0), typ.get("macro_f1",  0), typ.get("weighted_f1",  0)]

    x = np.arange(len(categories))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - 0.2, subj_vals, 0.4, label="Sujet",         color="#53d8fb", alpha=0.9)
    ax.bar(x + 0.2, type_vals, 0.4, label="Type document",  color="#e94560", alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 1.1)
    ax.set_title("Métriques Classification", fontsize=13, fontweight="bold")
    ax.set_ylabel("Score")
    ax.legend()
    ax.grid(axis="y")
    for i, (s, t) in enumerate(zip(subj_vals, type_vals)):
        ax.text(i - 0.2, s + 0.02, f"{s:.2f}", ha="center", fontsize=9, color="white")
        ax.text(i + 0.2, t + 0.02, f"{t:.2f}", ha="center", fontsize=9, color="white")
    plt.tight_layout()
    out = os.path.join(output_dir, "clf_global.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Graphique sauvegardé : {out}")

    # ── Fig 2 : F1 par classe (sujet) ────────────────────────────────────
    per_class = subj.get("per_class", {})
    if per_class:
        labels = list(per_class.keys())
        f1s    = [per_class[l]["f1"] for l in labels]
        precs  = [per_class[l]["precision"] for l in labels]
        recs   = [per_class[l]["recall"] for l in labels]
        x = np.arange(len(labels))
        fig, ax = plt.subplots(figsize=(max(10, len(labels)*1.2), 5))
        w = 0.25
        ax.bar(x - w, precs, w, label="Precision", color="#53d8fb", alpha=0.85)
        ax.bar(x,     recs,  w, label="Recall",    color="#f5a623", alpha=0.85)
        ax.bar(x + w, f1s,   w, label="F1",        color="#7ed321", alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylim(0, 1.15)
        ax.set_title("Precision / Recall / F1 par matière", fontsize=12)
        ax.legend()
        ax.grid(axis="y")
        plt.tight_layout()
        out2 = os.path.join(output_dir, "clf_per_class.png")
        plt.savefig(out2, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Graphique sauvegardé : {out2}")

    # ── Fig 3 : Matrice de confusion ─────────────────────────────────────
    cm_data = results.get("confusion_matrix_subject", {})
    if cm_data:
        cm_labels = cm_data["labels"]
        matrix = np.array([[cm_data["matrix"][r][c] for c in cm_labels] for r in cm_labels])
        fig, ax = plt.subplots(figsize=(max(7, len(cm_labels)), max(6, len(cm_labels)-1)))
        im = ax.imshow(matrix, cmap="Blues")
        ax.set_xticks(range(len(cm_labels)))
        ax.set_yticks(range(len(cm_labels)))
        ax.set_xticklabels(cm_labels, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(cm_labels, fontsize=8)
        ax.set_xlabel("Prédit")
        ax.set_ylabel("Réel")
        ax.set_title("Matrice de Confusion — Sujet", fontsize=12, fontweight="bold")
        for r in range(len(cm_labels)):
            for c in range(len(cm_labels)):
                ax.text(c, r, str(matrix[r, c]),
                        ha="center", va="center",
                        color="white" if matrix[r, c] > matrix.max()/2 else "#333")
        plt.colorbar(im, ax=ax)
        plt.tight_layout()
        out3 = os.path.join(output_dir, "clf_confusion_matrix.png")
        plt.savefig(out3, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Graphique sauvegardé : {out3}")


# ─────────────────────────────────────────────────────────────────────────────
# RAG
# ─────────────────────────────────────────────────────────────────────────────

def plot_rag(results: dict, output_dir: str):
    _style()
    os.makedirs(output_dir, exist_ok=True)

    retrieval = results.get("retrieval", {})
    k_values  = results.get("k_values", [1, 3, 5])
    avg_pk = retrieval.get("avg_precision_at_k", {})
    avg_rk = retrieval.get("avg_recall_at_k", {})
    avg_nk = retrieval.get("avg_ndcg_at_k", {})

    # ── Fig 1 : P@k / R@k / nDCG@k ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(k_values))
    w = 0.25
    ks = [str(k) for k in k_values]
    pk_vals = [avg_pk.get(k, avg_pk.get(str(k), 0)) for k in k_values]
    rk_vals = [avg_rk.get(k, avg_rk.get(str(k), 0)) for k in k_values]
    nk_vals = [avg_nk.get(k, avg_nk.get(str(k), 0)) for k in k_values]
    ax.bar(x - w, pk_vals, w, label="Precision@k", color="#53d8fb", alpha=0.9)
    ax.bar(x,     rk_vals, w, label="Recall@k",    color="#f5a623", alpha=0.9)
    ax.bar(x + w, nk_vals, w, label="nDCG@k",      color="#7ed321", alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels([f"k={k}" for k in k_values])
    ax.set_ylim(0, 1.15)
    ax.set_title("Métriques Retrieval RAG", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(axis="y")

    map_val = retrieval.get("MAP", 0)
    mrr_val = retrieval.get("MRR", 0)
    ax.text(0.98, 0.95, f"MAP={map_val:.3f}  MRR={mrr_val:.3f}",
            transform=ax.transAxes, ha="right", va="top",
            color="#e94560", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round", facecolor="#16213e", alpha=0.8))
    plt.tight_layout()
    out = os.path.join(output_dir, "rag_retrieval.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Graphique sauvegardé : {out}")

    # ── Fig 2 : Latence par requête ───────────────────────────────────────
    samples = results.get("samples", [])
    if samples:
        times = [s.get("total_ms", 0) for s in samples]
        fig, ax = plt.subplots(figsize=(max(8, len(samples)*0.6), 4))
        ax.bar(range(len(times)), times, color="#e94560", alpha=0.8)
        ax.axhline(y=sum(times)/len(times), color="#53d8fb", linestyle="--", label=f"Moy={sum(times)/len(times):.0f}ms")
        ax.set_title("Latence par requête RAG (ms)", fontsize=12)
        ax.set_xlabel("Requête #")
        ax.set_ylabel("Temps (ms)")
        ax.legend()
        ax.grid(axis="y")
        plt.tight_layout()
        out2 = os.path.join(output_dir, "rag_latency.png")
        plt.savefig(out2, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Graphique sauvegardé : {out2}")


# ─────────────────────────────────────────────────────────────────────────────
# COMPARAISON MULTI-BENCHMARKS (dashboard)
# ─────────────────────────────────────────────────────────────────────────────

def plot_dashboard(ocr_res: dict, clf_res: dict, rag_res: dict, output_dir: str):
    """Un graphique récapitulatif de tous les modules."""
    _style()
    os.makedirs(output_dir, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("DocManager — Tableau de Bord Évaluation", fontsize=15, fontweight="bold")

    # OCR
    ax = axes[0]
    gm = ocr_res.get("global_metrics", {})
    metrics = ["Accuracy", "1-CER", "1-WER"]
    vals = [
        gm.get("Accuracy_mean", 0),
        max(0, 1 - gm.get("CER_mean", 1)),
        max(0, 1 - gm.get("WER_mean", 1)),
    ]
    bars = ax.bar(metrics, vals, color=["#7ed321", "#53d8fb", "#f5a623"], alpha=0.9, width=0.5)
    ax.set_ylim(0, 1.1)
    ax.set_title("Module OCR", fontsize=12, fontweight="bold")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02,
                f"{v:.2f}", ha="center", color="white", fontweight="bold")
    ax.grid(axis="y")

    # Classification
    ax = axes[1]
    subj = clf_res.get("subject_classification", {})
    metrics = ["Accuracy", "Macro F1", "Weighted F1"]
    vals = [subj.get("accuracy", 0), subj.get("macro_f1", 0), subj.get("weighted_f1", 0)]
    bars = ax.bar(metrics, vals, color=["#7ed321", "#53d8fb", "#f5a623"], alpha=0.9, width=0.5)
    ax.set_ylim(0, 1.1)
    ax.set_title("Module Classification", fontsize=12, fontweight="bold")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02,
                f"{v:.2f}", ha="center", color="white", fontweight="bold")
    ax.grid(axis="y")

    # RAG
    ax = axes[2]
    ret = rag_res.get("retrieval", {})
    metrics = ["MAP", "MRR", "P@3", "nDCG@3"]
    vals = [
        ret.get("MAP", 0),
        ret.get("MRR", 0),
        ret.get("avg_precision_at_k", {}).get(3, ret.get("avg_precision_at_k", {}).get("3", 0)),
        ret.get("avg_ndcg_at_k", {}).get(3, ret.get("avg_ndcg_at_k", {}).get("3", 0)),
    ]
    bars = ax.bar(metrics, vals, color=["#e94560", "#53d8fb", "#f5a623", "#7ed321"], alpha=0.9, width=0.5)
    ax.set_ylim(0, 1.1)
    ax.set_title("Module RAG", fontsize=12, fontweight="bold")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02,
                f"{v:.2f}", ha="center", color="white", fontweight="bold")
    ax.grid(axis="y")

    plt.tight_layout()
    out = os.path.join(output_dir, "dashboard_global.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  ✅ Dashboard global sauvegardé : {out}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_MATPLOTLIB:
        print("Installez matplotlib: pip install matplotlib numpy")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Visualisation benchmarks DocManager")
    parser.add_argument("--results-dir", default="evaluation/results")
    parser.add_argument("--output-dir",  default="evaluation/plots")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print("  GÉNÉRATION DES GRAPHIQUES")
    print(f"{'='*55}")

    ocr_path = os.path.join(args.results_dir, "ocr_results.json")
    clf_path = os.path.join(args.results_dir, "classification_results.json")
    rag_path = os.path.join(args.results_dir, "rag_results.json")

    ocr_res = clf_res = rag_res = None

    if os.path.exists(ocr_path):
        ocr_res = _load_json(ocr_path)
        print("\n[OCR]")
        plot_ocr(ocr_res, args.output_dir)

    if os.path.exists(clf_path):
        clf_res = _load_json(clf_path)
        print("\n[Classification]")
        plot_classification(clf_res, args.output_dir)

    if os.path.exists(rag_path):
        rag_res = _load_json(rag_path)
        print("\n[RAG]")
        plot_rag(rag_res, args.output_dir)

    if ocr_res and clf_res and rag_res:
        print("\n[Dashboard global]")
        plot_dashboard(ocr_res, clf_res, rag_res, args.output_dir)

    print(f"\n  Graphiques disponibles dans : {args.output_dir}/")
