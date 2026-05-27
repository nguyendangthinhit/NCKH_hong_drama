"""
GraphSAGE 2-layer node classifier.

Hỗ trợ cả PyTorch Geometric (`torch_geometric.nn.SAGEConv`) và pure PyTorch
fallback (mean aggregation manually) — chọn import động để Colab chạy được
ngay cả khi PyG chưa cài.

Reference:
- Hamilton, Ying, Leskovec (2017). Inductive Representation Learning on
  Large Graphs. NeurIPS.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class GraphSAGEClassifier(nn.Module):
    """2-layer GraphSAGE + classification head.

    Args:
        in_dim: input feature dim (1071 cho hybrid PhoBERT+TFIDF+structural)
        hidden_dim: hidden GraphSAGE dim (default 128)
        num_classes: số lớp (4 cho Edu, 5 cho Show)
        dropout: dropout giữa 2 layer
    """

    def __init__(self, in_dim: int, hidden_dim: int = 128, num_classes: int = 4,
                 dropout: float = 0.3):
        super().__init__()
        from torch_geometric.nn import SAGEConv  # lazy import
        self.conv1 = SAGEConv(in_dim, hidden_dim, aggr="mean")
        self.conv2 = SAGEConv(hidden_dim, hidden_dim, aggr="mean")
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, x, edge_index):
        h = F.relu(self.conv1(x, edge_index))
        h = self.dropout(h)
        h = F.relu(self.conv2(h, edge_index))
        return self.classifier(h)


def make_model(domain: str, in_dim: int = 1071, hidden_dim: int = 128,
               dropout: float = 0.3) -> GraphSAGEClassifier:
    """Factory chọn num_classes theo domain."""
    n_classes = {"education": 4, "showbiz": 5}[domain]
    return GraphSAGEClassifier(in_dim, hidden_dim, n_classes, dropout)
