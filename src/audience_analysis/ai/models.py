"""Fabrici opționale: reutilizare encoder/mean/GRU legacy, fără descărcări."""
from .data import DIMENSIONS


def build_model(architecture="mean", *, hidden_size=128, dimensions=("engagement",)):
    dimensions = tuple(dimensions)
    if architecture not in {"mean", "gru"} or not dimensions or dimensions != tuple(d for d in DIMENSIONS if d in dimensions):
        raise ValueError("Arhitectură sau ordine a dimensiunilor invalidă.")
    if type(hidden_size) is not int or hidden_size < 1: raise ValueError("hidden_size invalid.")
    from ..models import EngagementModel
    if dimensions == ("engagement",):
        model = EngagementModel(architecture, hidden_size, pretrained=False)
        model.dimensions = dimensions
        return model
    from torch import nn
    class MultiHeadModel(EngagementModel):
        def __init__(self):
            super().__init__(architecture, hidden_size, pretrained=False)
            del self.classifier
            self.dimensions = dimensions
            self.heads = nn.ModuleDict({d: nn.Linear(hidden_size if self.temporal else 576, 4) for d in dimensions})

        def classify(self, features):
            if self.temporal is None: pooled = features.mean(dim=1)
            else: pooled = self.temporal(features)[1][-1]
            return {dimension: head(pooled) for dimension, head in self.heads.items()}
    return MultiHeadModel()


def build_baseline(**kwargs):
    return build_model("mean", **kwargs)


def build_temporal(**kwargs):
    return build_model("gru", **kwargs)
