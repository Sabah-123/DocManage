"""
evaluation/metrics.py
---------------------
Toutes les métriques d'évaluation pour les 3 agents :
  - OCR   : CER (Character Error Rate), WER (Word Error Rate)
  - Classification : Accuracy, Precision, Recall, F1-score
  - RAG   : Precision@k, Recall@k, MRR, NDCG, Answer Quality
"""

import time
import unicodedata
import re
from typing import List, Dict, Tuple, Optional


# ─────────────────────────────────────────────────────────────────────────────
# 1.  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """Normalisation minimale : minuscules, accents supprimés, espaces collapsés."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _edit_distance(a: str, b: str) -> int:
    """Distance de Levenshtein caractère par caractère."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


# ─────────────────────────────────────────────────────────────────────────────
# 2.  MÉTRIQUES OCR
# ─────────────────────────────────────────────────────────────────────────────

def cer(ground_truth: str, hypothesis: str, normalize: bool = True) -> float:
    """
    Character Error Rate (CER).
    CER = edit_distance(ref, hyp) / len(ref)
    Valeur entre 0 (parfait) et >1 (très mauvais).
    """
    ref = _normalize_text(ground_truth) if normalize else ground_truth
    hyp = _normalize_text(hypothesis) if normalize else hypothesis
    if len(ref) == 0:
        return 0.0 if len(hyp) == 0 else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def wer(ground_truth: str, hypothesis: str, normalize: bool = True) -> float:
    """
    Word Error Rate (WER).
    WER = edit_distance(ref_words, hyp_words) / len(ref_words)
    """
    ref_words = (_normalize_text(ground_truth) if normalize else ground_truth).split()
    hyp_words = (_normalize_text(hypothesis) if normalize else hypothesis).split()
    if len(ref_words) == 0:
        return 0.0 if len(hyp_words) == 0 else 1.0
    return _edit_distance(ref_words, hyp_words) / len(ref_words)


def ocr_accuracy(ground_truth: str, hypothesis: str) -> float:
    """Accuracy caractère = 1 - CER (clampé à 0)."""
    return max(0.0, 1.0 - cer(ground_truth, hypothesis))


def ocr_report(samples: List[Dict]) -> Dict:
    """
    Calcule CER et WER sur un ensemble de couples (ground_truth, hypothesis).
    samples = [{"gt": "...", "hyp": "...", "engine": "tesseract"}, ...]
    Retourne stats globales + par moteur.
    """
    from collections import defaultdict
    stats_global = {"cer": [], "wer": [], "accuracy": []}
    stats_engine: Dict[str, Dict[str, List]] = defaultdict(lambda: {"cer": [], "wer": [], "accuracy": []})

    for s in samples:
        gt, hyp = s["gt"], s["hyp"]
        c = cer(gt, hyp)
        w = wer(gt, hyp)
        a = max(0.0, 1.0 - c)
        engine = s.get("engine", "unknown")

        stats_global["cer"].append(c)
        stats_global["wer"].append(w)
        stats_global["accuracy"].append(a)
        stats_engine[engine]["cer"].append(c)
        stats_engine[engine]["wer"].append(w)
        stats_engine[engine]["accuracy"].append(a)

    def _avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "global": {
            "n": len(samples),
            "CER_mean": _avg(stats_global["cer"]),
            "WER_mean": _avg(stats_global["wer"]),
            "Accuracy_mean": _avg(stats_global["accuracy"]),
        },
        "by_engine": {
            engine: {
                "n": len(v["cer"]),
                "CER_mean": _avg(v["cer"]),
                "WER_mean": _avg(v["wer"]),
                "Accuracy_mean": _avg(v["accuracy"]),
            }
            for engine, v in stats_engine.items()
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3.  MÉTRIQUES CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classification_report(y_true: List[str], y_pred: List[str]) -> Dict:
    """
    Accuracy, Precision, Recall, F1 macro/weighted pour la classification.
    Compatible avec les sorties du classification_agent.
    """
    from collections import Counter
    assert len(y_true) == len(y_pred), "y_true et y_pred doivent avoir la même longueur"

    labels = sorted(set(y_true) | set(y_pred))
    n = len(y_true)

    tp: Dict[str, int] = Counter()
    fp: Dict[str, int] = Counter()
    fn: Dict[str, int] = Counter()

    correct = 0
    for t, p in zip(y_true, y_pred):
        if t == p:
            correct += 1
            tp[t] += 1
        else:
            fp[p] += 1
            fn[t] += 1

    accuracy = correct / n if n > 0 else 0.0

    per_class = {}
    for lbl in labels:
        prec = tp[lbl] / (tp[lbl] + fp[lbl]) if (tp[lbl] + fp[lbl]) > 0 else 0.0
        rec  = tp[lbl] / (tp[lbl] + fn[lbl]) if (tp[lbl] + fn[lbl]) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        support = sum(1 for t in y_true if t == lbl)
        per_class[lbl] = {"precision": round(prec, 4), "recall": round(rec, 4),
                          "f1": round(f1, 4), "support": support}

    macro_p = sum(v["precision"] for v in per_class.values()) / len(labels)
    macro_r = sum(v["recall"]    for v in per_class.values()) / len(labels)
    macro_f1 = sum(v["f1"]       for v in per_class.values()) / len(labels)

    total = n
    weighted_p  = sum(v["precision"] * v["support"] for v in per_class.values()) / total if total else 0
    weighted_r  = sum(v["recall"]    * v["support"] for v in per_class.values()) / total if total else 0
    weighted_f1 = sum(v["f1"]        * v["support"] for v in per_class.values()) / total if total else 0

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_precision": round(weighted_p, 4),
        "weighted_recall": round(weighted_r, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "n_samples": n,
    }


def confusion_matrix(y_true: List[str], y_pred: List[str]) -> Dict:
    """Matrice de confusion sous forme de dict {true_label: {pred_label: count}}."""
    labels = sorted(set(y_true) | set(y_pred))
    matrix: Dict[str, Dict[str, int]] = {l: {l2: 0 for l2 in labels} for l in labels}
    for t, p in zip(y_true, y_pred):
        matrix[t][p] += 1
    return {"labels": labels, "matrix": matrix}


# ─────────────────────────────────────────────────────────────────────────────
# 4.  MÉTRIQUES RAG
# ─────────────────────────────────────────────────────────────────────────────

def precision_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    """P@k : proportion de documents pertinents dans le top-k."""
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / k if k > 0 else 0.0


def recall_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    """R@k : proportion de documents pertinents retrouvés dans le top-k."""
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / len(relevant) if relevant else 0.0


def average_precision(relevant: List[int], retrieved: List[int]) -> float:
    """AP : Average Precision pour une requête."""
    hits, score = 0, 0.0
    for i, doc_id in enumerate(retrieved, 1):
        if doc_id in relevant:
            hits += 1
            score += hits / i
    return score / len(relevant) if relevant else 0.0


def mean_average_precision(queries_results: List[Tuple[List[int], List[int]]]) -> float:
    """MAP : Mean Average Precision sur un ensemble de requêtes."""
    aps = [average_precision(rel, ret) for rel, ret in queries_results]
    return sum(aps) / len(aps) if aps else 0.0


def mrr(queries_results: List[Tuple[List[int], List[int]]]) -> float:
    """Mean Reciprocal Rank."""
    rrs = []
    for relevant, retrieved in queries_results:
        rr = 0.0
        for rank, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant:
                rr = 1.0 / rank
                break
        rrs.append(rr)
    return sum(rrs) / len(rrs) if rrs else 0.0


def ndcg_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    """nDCG@k (relevance binaire)."""
    import math
    dcg = 0.0
    for i, doc_id in enumerate(retrieved[:k], 1):
        if doc_id in relevant:
            dcg += 1.0 / math.log2(i + 1)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / idcg if idcg > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 5.  MÉTRIQUES LATENCE
# ─────────────────────────────────────────────────────────────────────────────

class Timer:
    """Context manager pour mesurer le temps d'exécution."""
    def __init__(self, label: str = ""):
        self.label = label
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000


def latency_stats(times_ms: List[float]) -> Dict:
    """Calcule min, max, mean, median, p95 sur une liste de latences (ms)."""
    import statistics
    if not times_ms:
        return {}
    sorted_t = sorted(times_ms)
    p95_idx = int(0.95 * len(sorted_t))
    return {
        "n": len(times_ms),
        "min_ms": round(min(times_ms), 2),
        "max_ms": round(max(times_ms), 2),
        "mean_ms": round(statistics.mean(times_ms), 2),
        "median_ms": round(statistics.median(times_ms), 2),
        "p95_ms": round(sorted_t[p95_idx], 2),
        "stdev_ms": round(statistics.stdev(times_ms), 2) if len(times_ms) > 1 else 0.0,
    }
