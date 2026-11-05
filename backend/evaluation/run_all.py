"""
evaluation/run_all.py
----------------------
Lance tous les benchmarks, la comparaison baseline et la visualisation
en un seul pipeline, puis génère un rapport Markdown.

Usage :
    cd backend
    python -m evaluation.run_all \
        --ocr-dataset  evaluation/data/ocr_dataset.json \
        --clf-dataset  evaluation/data/classification_dataset.json \
        --rag-dataset  evaluation/data/rag_dataset.json \
        --user-id 1

    # Pour générer les datasets exemples d'abord :
    python -m evaluation.run_all --generate-samples
"""

import argparse
import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = "evaluation/results"
PLOTS_DIR   = "evaluation/plots"
DATA_DIR    = "evaluation/data"


def _ensure_dirs():
    for d in [RESULTS_DIR, PLOTS_DIR, DATA_DIR]:
        os.makedirs(d, exist_ok=True)


def _load_json(path: str) -> Optional[Dict]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def generate_samples():
    """Génère des datasets exemples pour les 3 modules."""
    from evaluation.benchmark_ocr import generate_sample_dataset as gen_ocr
    from evaluation.benchmark_classification import generate_sample_dataset as gen_clf
    from evaluation.benchmark_rag import generate_sample_dataset as gen_rag

    _ensure_dirs()
    gen_ocr(os.path.join(DATA_DIR, "ocr_dataset.json"))
    gen_clf(os.path.join(DATA_DIR, "classification_dataset.json"))
    gen_rag(os.path.join(DATA_DIR, "rag_dataset.json"))
    print("\n✅ Datasets exemples créés dans evaluation/data/")
    print("   → Remplacez les données par vos documents réels avant l'évaluation.")


def run_ocr_benchmark(dataset_path: str) -> Optional[Dict]:
    if not os.path.exists(dataset_path):
        print(f"  [SKIP OCR] Dataset introuvable : {dataset_path}")
        return None
    from evaluation.benchmark_ocr import run_benchmark
    return run_benchmark(dataset_path, os.path.join(RESULTS_DIR, "ocr_results.json"))


def run_clf_benchmark(dataset_path: str) -> Optional[Dict]:
    if not os.path.exists(dataset_path):
        print(f"  [SKIP CLF] Dataset introuvable : {dataset_path}")
        return None
    from evaluation.benchmark_classification import run_benchmark
    return run_benchmark(dataset_path, os.path.join(RESULTS_DIR, "classification_results.json"))


def run_rag_benchmark(dataset_path: str, user_id: int) -> Optional[Dict]:
    if not os.path.exists(dataset_path):
        print(f"  [SKIP RAG] Dataset introuvable : {dataset_path}")
        return None
    from evaluation.benchmark_rag import run_benchmark
    return run_benchmark(dataset_path, user_id,
                         output_path=os.path.join(RESULTS_DIR, "rag_results.json"))


def run_baseline(ocr_path: str, clf_path: str) -> Optional[Dict]:
    from evaluation.baseline_comparison import run_comparison
    return run_comparison(
        ocr_dataset_path=ocr_path if os.path.exists(ocr_path) else None,
        clf_dataset_path=clf_path if os.path.exists(clf_path) else None,
        output_path=os.path.join(RESULTS_DIR, "baseline_comparison.json")
    )


def run_visualize():
    from evaluation.visualize import HAS_MATPLOTLIB
    if not HAS_MATPLOTLIB:
        print("\n  [SKIP PLOTS] matplotlib non installé. `pip install matplotlib numpy`")
        return
    from evaluation.visualize import plot_ocr, plot_classification, plot_rag, plot_dashboard, _load_json

    ocr_r = _load_json(os.path.join(RESULTS_DIR, "ocr_results.json"))
    clf_r = _load_json(os.path.join(RESULTS_DIR, "classification_results.json"))
    rag_r = _load_json(os.path.join(RESULTS_DIR, "rag_results.json"))

    if ocr_r: plot_ocr(ocr_r, PLOTS_DIR)
    if clf_r: plot_classification(clf_r, PLOTS_DIR)
    if rag_r: plot_rag(rag_r, PLOTS_DIR)
    if ocr_r and clf_r and rag_r:
        plot_dashboard(ocr_r, clf_r, rag_r, PLOTS_DIR)


def generate_markdown_report(
    ocr_res: Optional[Dict],
    clf_res: Optional[Dict],
    rag_res: Optional[Dict],
    baseline_res: Optional[Dict],
) -> str:
    """Génère un rapport Markdown complet."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# DocManager — Rapport d'Évaluation",
        f"",
        f"**Généré le :** {now}",
        f"",
        f"---",
        f"",
        f"## Résumé exécutif",
        f"",
    ]

    if ocr_res:
        gm = ocr_res.get("global_metrics", {})
        lines.append(f"| Module | CER | WER | Accuracy | Latence moy. |")
        lines.append(f"|--------|-----|-----|----------|--------------|")
        lat = ocr_res.get("latency_global_ms", {})
        lines.append(f"| OCR | {gm.get('CER_mean',0):.4f} | {gm.get('WER_mean',0):.4f} | "
                     f"{gm.get('Accuracy_mean',0):.4f} | {lat.get('mean_ms',0):.0f} ms |")
        lines.append("")

    if clf_res:
        subj = clf_res.get("subject_classification", {})
        typ  = clf_res.get("type_classification", {})
        lat  = clf_res.get("latency_ms", {})
        lines.append(f"| Module | Accuracy | Macro F1 | Weighted F1 | Latence moy. |")
        lines.append(f"|--------|----------|----------|-------------|--------------|")
        lines.append(f"| Classification (Sujet) | {subj.get('accuracy',0):.4f} | "
                     f"{subj.get('macro_f1',0):.4f} | {subj.get('weighted_f1',0):.4f} | "
                     f"{lat.get('mean_ms',0):.0f} ms |")
        lines.append(f"| Classification (Type) | {typ.get('accuracy',0):.4f} | "
                     f"{typ.get('macro_f1',0):.4f} | {typ.get('weighted_f1',0):.4f} | - |")
        lines.append("")

    if rag_res:
        ret = rag_res.get("retrieval", {})
        lat = rag_res.get("latency_ms", {})
        lines.append(f"| Module | MAP | MRR | Latence moy. |")
        lines.append(f"|--------|-----|-----|--------------|")
        lines.append(f"| RAG | {ret.get('MAP',0):.4f} | {ret.get('MRR',0):.4f} | "
                     f"{lat.get('mean_ms',0):.0f} ms |")
        lines.append("")

    # ── Section OCR ───────────────────────────────────────────────────────
    if ocr_res:
        lines += [
            "---", "## 1. Module OCR", "",
            "### 1.1 Métriques globales", "",
            "| Métrique | Valeur |",
            "|----------|--------|",
        ]
        gm = ocr_res.get("global_metrics", {})
        for k, v in gm.items():
            lines.append(f"| {k} | {v:.4f} |")
        lines.append("")
        lines.append("### 1.2 Métriques par moteur")
        lines.append("")
        lines.append("| Moteur | n | CER moy. | WER moy. | Accuracy moy. | Latence moy. (ms) |")
        lines.append("|--------|---|----------|----------|---------------|-------------------|")
        for engine, data in ocr_res.get("latency_by_engine_ms", {}).items():
            lines.append(f"| {engine} | {data.get('n','-')} | - | - | - | {data.get('mean_ms',0):.0f} |")
        lines.append("")
        lines.append("### 1.3 Graphiques")
        lines.append("")
        for img in ["ocr_global_metrics.png", "ocr_per_doc.png", "ocr_latency_engine.png"]:
            if os.path.exists(os.path.join(PLOTS_DIR, img)):
                lines.append(f"![{img}](plots/{img})")
        lines.append("")

    # ── Section Classification ─────────────────────────────────────────────
    if clf_res:
        lines += [
            "---", "## 2. Module Classification", "",
            "### 2.1 Métriques globales — Sujet", "",
            "| Métrique | Valeur |",
            "|----------|--------|",
        ]
        subj = clf_res.get("subject_classification", {})
        for k in ["accuracy","macro_precision","macro_recall","macro_f1","weighted_f1"]:
            if k in subj:
                lines.append(f"| {k} | {subj[k]:.4f} |")
        lines.append("")
        lines.append("### 2.2 Détail par matière")
        lines.append("")
        lines.append("| Matière | Precision | Recall | F1 | Support |")
        lines.append("|---------|-----------|--------|-----|---------|")
        for lbl, s in subj.get("per_class", {}).items():
            lines.append(f"| {lbl} | {s['precision']:.3f} | {s['recall']:.3f} | "
                         f"{s['f1']:.3f} | {s['support']} |")
        lines.append("")
        lines.append("### 2.3 Graphiques")
        for img in ["clf_global.png", "clf_per_class.png", "clf_confusion_matrix.png"]:
            if os.path.exists(os.path.join(PLOTS_DIR, img)):
                lines.append(f"![{img}](plots/{img})")
        lines.append("")

    # ── Section RAG ──────────────────────────────────────────────────────
    if rag_res:
        lines += [
            "---", "## 3. Module RAG", "",
            "### 3.1 Métriques Retrieval", "",
            "| Métrique | Valeur |",
            "|----------|--------|",
        ]
        ret = rag_res.get("retrieval", {})
        lines.append(f"| MAP | {ret.get('MAP',0):.4f} |")
        lines.append(f"| MRR | {ret.get('MRR',0):.4f} |")
        for k, v in ret.get("avg_precision_at_k", {}).items():
            lines.append(f"| Precision@{k} | {v:.4f} |")
        for k, v in ret.get("avg_recall_at_k", {}).items():
            lines.append(f"| Recall@{k} | {v:.4f} |")
        for k, v in ret.get("avg_ndcg_at_k", {}).items():
            lines.append(f"| nDCG@{k} | {v:.4f} |")
        gen = rag_res.get("generation", {})
        if gen.get("avg_rouge_l_f1") not in (None, "N/A"):
            lines.append(f"| ROUGE-L F1 | {gen['avg_rouge_l_f1']:.4f} |")
        lines.append("")
        lines.append("### 3.2 Graphiques")
        for img in ["rag_retrieval.png", "rag_latency.png"]:
            if os.path.exists(os.path.join(PLOTS_DIR, img)):
                lines.append(f"![{img}](plots/{img})")
        lines.append("")

    # ── Section Baseline ──────────────────────────────────────────────────
    if baseline_res:
        lines += [
            "---", "## 4. Comparaison Baseline", "",
        ]
        if "ocr" in baseline_res:
            bl = baseline_res["ocr"]["baseline"]
            cu = baseline_res["ocr"]["current"]
            lines.append("### 4.1 OCR — Tesseract seul vs Multi-moteur")
            lines.append("")
            lines.append("| Métrique | Baseline (Tesseract) | Système actuel | Gain |")
            lines.append("|----------|---------------------|----------------|------|")
            for key, label in [("CER_mean","CER"),("WER_mean","WER"),("Accuracy_mean","Accuracy")]:
                bv = bl.get(key, 0)
                cv = cu.get(key, 0)
                gain = cv - bv
                sign = "+" if gain > 0 else ""
                lines.append(f"| {label} | {bv:.4f} | {cv:.4f} | {sign}{gain:.4f} |")
            lines.append("")

        if "classification" in baseline_res:
            bl = baseline_res["classification"]["baseline"]
            cu = baseline_res["classification"]["current"]
            lines.append("### 4.2 Classification — Mots-clés vs LLM Groq")
            lines.append("")
            lines.append("| Tâche | Métrique | Baseline | Système actuel | Gain |")
            lines.append("|-------|----------|----------|----------------|------|")
            for task in ["subject", "doc_type"]:
                for key in ["accuracy", "macro_f1"]:
                    bv = bl.get(task, {}).get(key, 0)
                    cv = cu.get(task, {}).get(key, 0)
                    gain = cv - bv
                    sign = "+" if gain > 0 else ""
                    lines.append(f"| {task} | {key} | {bv:.4f} | {cv:.4f} | {sign}{gain:.4f} |")
            lines.append("")

    # ── Dashboard ─────────────────────────────────────────────────────────
    dash = os.path.join(PLOTS_DIR, "dashboard_global.png")
    if os.path.exists(dash):
        lines += ["---", "## 5. Dashboard Global", "", f"![Dashboard](plots/dashboard_global.png)", ""]

    lines += [
        "---",
        "*Rapport généré automatiquement par `evaluation/run_all.py`*",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Pipeline d'évaluation complet DocManager")
    parser.add_argument("--ocr-dataset", default=os.path.join(DATA_DIR, "ocr_dataset.json"))
    parser.add_argument("--clf-dataset", default=os.path.join(DATA_DIR, "classification_dataset.json"))
    parser.add_argument("--rag-dataset", default=os.path.join(DATA_DIR, "rag_dataset.json"))
    parser.add_argument("--user-id",     type=int, default=1)
    parser.add_argument("--skip-ocr",   action="store_true")
    parser.add_argument("--skip-clf",   action="store_true")
    parser.add_argument("--skip-rag",   action="store_true")
    parser.add_argument("--skip-plots", action="store_true")
    parser.add_argument("--generate-samples", action="store_true",
                        help="Génère des datasets exemples et quitte")
    args = parser.parse_args()

    if args.generate_samples:
        generate_samples()
        sys.exit(0)

    _ensure_dirs()
    print(f"\n{'█'*65}")
    print(f"  DocManager — PIPELINE D'ÉVALUATION COMPLET")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'█'*65}")

    ocr_res = clf_res = rag_res = baseline_res = None

    if not args.skip_ocr:
        print("\n[1/4] Benchmark OCR...")
        ocr_res = run_ocr_benchmark(args.ocr_dataset)

    if not args.skip_clf:
        print("\n[2/4] Benchmark Classification...")
        clf_res = run_clf_benchmark(args.clf_dataset)

    if not args.skip_rag:
        print("\n[3/4] Benchmark RAG...")
        rag_res = run_rag_benchmark(args.rag_dataset, args.user_id)

    print("\n[4/4] Comparaison Baseline...")
    baseline_res = run_baseline(args.ocr_dataset, args.clf_dataset)

    if not args.skip_plots:
        print("\n[5/5] Génération des graphiques...")
        run_visualize()

    # ── Rapport Markdown ─────────────────────────────────────────────────
    report_md = generate_markdown_report(ocr_res, clf_res, rag_res, baseline_res)
    report_path = os.path.join(RESULTS_DIR, "evaluation_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\n{'█'*65}")
    print(f"  ✅ ÉVALUATION TERMINÉE")
    print(f"  📄 Rapport Markdown : {report_path}")
    print(f"  📊 Graphiques       : {PLOTS_DIR}/")
    print(f"  📁 Résultats JSON   : {RESULTS_DIR}/")
    print(f"{'█'*65}\n")


if __name__ == "__main__":
    main()
