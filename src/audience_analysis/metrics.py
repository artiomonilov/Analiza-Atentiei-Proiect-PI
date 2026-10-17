import numpy as np


def classification_metrics(targets, predictions):
    matrix = np.zeros((4, 4), dtype=np.int64)
    if len(targets) != len(predictions) or len(targets) == 0:
        raise ValueError("Metricile necesită exemple și predicții pereche")
    for target, prediction in zip(targets, predictions):
        if target not in range(4) or prediction not in range(4):
            raise ValueError("Clasă invalidă")
        matrix[target, prediction] += 1
    tp = np.diag(matrix)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    recall = np.divide(tp, support, out=np.zeros(4), where=support != 0)
    precision = np.divide(tp, predicted, out=np.zeros(4), where=predicted != 0)
    f1 = np.divide(2*precision*recall, precision+recall, out=np.zeros(4), where=(precision+recall) != 0)
    return {"n": int(matrix.sum()), "accuracy": float(tp.sum()/matrix.sum()),
            "macro_f1": float(f1.mean()), "balanced_accuracy": float(recall[support > 0].mean()),
            "confusion_matrix": matrix.tolist(), "support": support.tolist(),
            "precision": precision.tolist(), "recall": recall.tolist(), "f1": f1.tolist(),
            "convention": "macro-F1 over 4 classes, zero_division=0; balanced accuracy over present target classes"}

