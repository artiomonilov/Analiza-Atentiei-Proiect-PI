"""Evaluare P1 pe predicții furnizate explicit, fără antrenare sau surse video."""
import numpy as np

from ..metrics import classification_metrics


def majority_class(training_labels):
    values = list(training_labels)
    if not values or any(type(v) is not int or v not in range(4) for v in values):
        raise ValueError("R0 necesită etichete train valide.")
    return int(np.bincount(values, minlength=4).argmax())


def compare_models(training_labels, targets, predictions, *, split="validation", data_kind="unverified"):
    if split not in {"validation", "test"} or data_kind not in {"synthetic", "authorized", "unverified"}:
        raise ValueError("Split/proveniență invalidă.")
    if not predictions or any(len(p) != len(targets) for p in predictions.values()): raise ValueError("Predicții nealiniate.")
    if any(type(v) is not int or v not in range(4) for v in targets): raise ValueError("Ținte invalide.")
    if any(v is not None and (type(v) is not int or v not in range(4)) for p in predictions.values() for v in p):
        raise ValueError("Predicții invalide.")
    common = [i for i in range(len(targets)) if all(p[i] is not None for p in predictions.values())]
    majority = majority_class(training_labels)
    truth = [targets[i] for i in common]
    def metric(values): return classification_metrics(truth, values) if truth else None
    return {"split": split, "data_kind": data_kind, "selection_allowed": split == "validation", "total": len(targets),
        "common_samples": len(common), "common_indices": common, "majority_class_from_train": majority,
        "coverage": {name: sum(v is not None for v in p) / len(targets) if targets else None for name, p in predictions.items()},
        "R0": metric([majority] * len(common)),
        "models": {name: metric([p[i] for i in common]) for name, p in predictions.items()},
        "limitation": "Fixture-urile sintetice nu sunt rezultate DAiSEE; comparațiile folosesc același subset observabil."}


def choose_on_validation(report):
    if report["split"] != "validation": raise ValueError("Selecția modelului pe test este interzisă.")
    available = {name: metrics for name, metrics in report["models"].items() if metrics is not None}
    if not available: raise ValueError("Nicio metrică disponibilă pentru selecție.")
    return max(sorted(available), key=lambda name: available[name]["macro_f1"])
