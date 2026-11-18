"""PhoBERT + đầu phân loại tuyến tính trên hidden state token đầu ([CLS]/<s>)."""

import torch.nn as nn
from transformers import AutoConfig, AutoModel


def build_encoder(model_name: str, smoke: bool = False):
    """smoke=True: encoder BERT nhỏ khởi tạo ngẫu nhiên (chỉ kiểm pipeline, không tải 540MB)."""
    if not smoke:
        return AutoModel.from_pretrained(model_name)
    from transformers import BertConfig, BertModel

    base = AutoConfig.from_pretrained(model_name)
    return BertModel(BertConfig(vocab_size=base.vocab_size, hidden_size=32, num_hidden_layers=2,
                                num_attention_heads=2, intermediate_size=64,
                                max_position_embeddings=base.max_position_embeddings))


class PhoBERTClassifier(nn.Module):
    def __init__(self, num_labels: int, model_name: str = "vinai/phobert-base-v2",
                 dropout: float = 0.1, smoke: bool = False):
        super().__init__()
        self.bert = build_encoder(model_name, smoke)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.bert.config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        h = self.bert(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0, :]
        return self.classifier(self.dropout(h))
