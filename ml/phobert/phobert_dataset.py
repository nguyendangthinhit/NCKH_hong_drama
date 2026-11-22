"""Dataset PyTorch cho PhoBERT: tokenize trước (một câu hoặc cặp câu ngữ cảnh + bình luận), pad động theo batch."""

import torch
from torch.utils.data import Dataset


class CommentDataset(Dataset):
    """Tokenize trước (đã word-segment), pad động theo batch qua collate_fn.
    contexts (tuỳ chọn): ngữ cảnh sự kiện từng dòng -> cặp câu `<s> ngữ cảnh </s></s> bình luận </s>`;
    quá max_length thì `longest_first` cắt dần phần đang dài hơn (bình luận rất dài cũng bị cắt)."""

    def __init__(self, texts, labels, tokenizer, max_length, contexts=None):
        if contexts is None:
            self.enc = tokenizer(list(texts), max_length=max_length, truncation=True)
        else:
            self.enc = tokenizer(list(contexts), list(texts), max_length=max_length,
                                 truncation="longest_first")
        self.labels = list(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        return {"input_ids": self.enc["input_ids"][i], "label": self.labels[i]}


def make_collate(pad_id: int):
    def collate(batch):
        width = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), width), pad_id, dtype=torch.long)
        mask = torch.zeros((len(batch), width), dtype=torch.long)
        for i, b in enumerate(batch):
            n = len(b["input_ids"])
            ids[i, :n] = torch.tensor(b["input_ids"])
            mask[i, :n] = 1
        return {"input_ids": ids, "attention_mask": mask,
                "label": torch.tensor([b["label"] for b in batch], dtype=torch.long)}
    return collate
