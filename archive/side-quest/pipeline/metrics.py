"""Accuracy + reliability metrics (docs/PRODUCT.md). Input: list of {label, class, probabilities, latency_ms, cost_usd}."""
import random
import statistics

from sklearn.metrics import f1_score

from pipeline import config


def _top(p: dict) -> tuple[str, float]:
    c = max(p, key=p.get)
    return c, p[c]


def brier(rows, classes=None) -> float:
    """Multiclass Brier: mean over examples of sum_c (p_c - 1[c = label])^2. 0 = perfect, 2 = worst."""
    classes = classes or config.CLASSES
    return statistics.mean(sum((r["probabilities"].get(c, 0) - (c == r["label"])) ** 2 for c in classes)
                           for r in rows)


def ece(rows, bins: int = 5) -> float:
    """Expected calibration error on the top-class probability."""
    total, err = len(rows), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [r for r in rows if lo < _top(r["probabilities"])[1] <= hi or (b == 0 and _top(r["probabilities"])[1] == 0)]
        if bucket:
            conf = statistics.mean(_top(r["probabilities"])[1] for r in bucket)
            acc = statistics.mean(r["class"] == r["label"] for r in bucket)
            err += len(bucket) / total * abs(conf - acc)
    return err


def selective(rows, threshold: float, conf_key: str = "confidence") -> tuple[float, float]:
    """(accuracy on answered, coverage) when only answering if confidence >= threshold."""
    kept = [r for r in rows if r.get(conf_key, _top(r["probabilities"])[1]) >= threshold]
    if not kept:
        return float("nan"), 0.0
    return statistics.mean(r["class"] == r["label"] for r in kept), len(kept) / len(rows)


def bootstrap_ci(rows, fn, n: int = 1000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    vals = sorted(fn([rng.choice(rows) for _ in rows]) for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def accuracy(rows) -> float:
    return statistics.mean(r["class"] == r["label"] for r in rows)


def macro_f1(rows, classes=None) -> float:
    return f1_score([r["label"] for r in rows], [r["class"] for r in rows], labels=classes or config.CLASSES,
                    average="macro", zero_division=0)


def summary(name: str, rows: list[dict], threshold: float | None = None) -> dict:
    lat = sorted(r.get("latency_ms", 0) for r in rows)
    out = {"system": name, "n": len(rows), "accuracy": accuracy(rows), "macro_f1": macro_f1(rows),
           "macro_f1_ci95": bootstrap_ci(rows, macro_f1), "brier": brier(rows), "ece": ece(rows),
           "latency_p50_ms": lat[len(lat) // 2], "latency_p95_ms": lat[int(len(lat) * 0.95) - 1] if lat else 0,
           "cost_per_1k_usd": 1000 * statistics.mean(r.get("cost_usd", 0) for r in rows)}
    if threshold is not None:
        out["selective_acc"], out["coverage"] = selective(rows, threshold)
    return out


def table(summaries: list[dict]) -> str:
    cols = ["system", "n", "accuracy", "macro_f1", "macro_f1_ci95", "brier", "ece", "selective_acc", "coverage",
            "latency_p50_ms", "latency_p95_ms", "cost_per_1k_usd"]
    fmt = lambda v: (f"{v:.3f}" if isinstance(v, float) else  # noqa: E731
                     f"[{v[0]:.2f}, {v[1]:.2f}]" if isinstance(v, tuple) else str(v))
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(s.get(c, "")) for c in cols) + " |" for s in summaries]
    return "\n".join(lines)
