"""
GraphSAGE 2-layer node classifier.

Dùng `torch_geometric.nn.SAGEConv` nếu PyG đã cài; nếu không dùng bản thuần
PyTorch (`MeanSAGEConv`, mean aggregation) có cùng tên tham số
(`lin_l`, `lin_r`) nên checkpoint hai bản nạp chéo được.

Reference:
- Hamilton, Ying, Leskovec (2017). Inductive Representation Learning on
  Large Graphs. NeurIPS.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_CLASSES = {"education": 4, "showbiz": 5}


class MeanSAGEConv(nn.Module):
    """SAGEConv(aggr='mean') thuần PyTorch: out = W_l * mean(x_j) + W_r * x_i.

    edge_index[0] = nguồn (j), edge_index[1] = đích (i), như PyG.
    """

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.lin_l = nn.Linear(in_dim, out_dim, bias=True)
        self.lin_r = nn.Linear(in_dim, out_dim, bias=False)

    def forward(self, x, edge_index):
        src, dst = edge_index
        agg = torch.zeros_like(x)
        agg.index_add_(0, dst, x[src])
        deg = torch.zeros(x.size(0), device=x.device, dtype=x.dtype)
        deg.index_add_(0, dst, torch.ones_like(dst, dtype=x.dtype))
        agg = agg / deg.clamp(min=1).unsqueeze(1)
        return self.lin_l(agg) + self.lin_r(x)


def _sage_conv_cls():
    try:
        from torch_geometric.nn import SAGEConv

        return lambda i, o: SAGEConv(i, o, aggr="mean")
    except ImportError:
        return MeanSAGEConv


class GraphSAGEClassifier(nn.Module):
    """2-layer GraphSAGE + classification head.

    Args:
        in_dim: số chiều đặc trưng nút (text embedding + TF-IDF + cấu trúc)
        hidden_dim: hidden GraphSAGE dim (default 128)
        num_classes: số lớp (4 cho Edu, 5 cho Show)
        dropout: dropout giữa 2 layer
    """

    def __init__(self, in_dim: int, hidden_dim: int = 128, num_classes: int = 4,
                 dropout: float = 0.3):
        super().__init__()
        conv = _sage_conv_cls()
        self.conv1 = conv(in_dim, hidden_dim)
        self.conv2 = conv(hidden_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, x, edge_index):
        h = F.relu(self.conv1(x, edge_index))
        h = self.dropout(h)
        h = F.relu(self.conv2(h, edge_index))
        return self.classifier(h)


class MLPClassifier(nn.Module):
    """Baseline không dùng đồ thị: Linear-ReLU-Dropout-Linear-ReLU-Linear.

    Cùng `in_dim/hidden_dim/num_classes` với GraphSAGE; `edge_index` được nhận
    nhưng bỏ qua để dùng chung vòng train. So GNN với MLP cho biết cạnh reply
    có đóng góp gì ngoài đặc trưng nút.
    """

    def __init__(self, in_dim: int, hidden_dim: int = 128, num_classes: int = 4,
                 dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x, edge_index=None):
        return self.net(x)


def make_model(domain: str, in_dim: int, hidden_dim: int = 128,
               dropout: float = 0.3, kind: str = "sage"):
    """Factory chọn num_classes theo domain. kind: 'sage' (GNN) hoặc 'mlp' (baseline)."""
    cls = {"sage": GraphSAGEClassifier, "mlp": MLPClassifier}[kind]
    return cls(in_dim, hidden_dim, NUM_CLASSES[domain], dropout)
