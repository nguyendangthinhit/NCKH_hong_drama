"""Cấu hình dùng chung cho fine-tune PhoBERT: nhãn theo lĩnh vực, tên cột dữ liệu, siêu tham số.

Khi cấu trúc dữ liệu gán lại thay đổi, chỉ sửa `ColumnMap` / `LABEL_ALIASES` ở đây
(hoặc truyền --text-col, --label-col... trên dòng lệnh); phần còn lại không đổi.
"""

from dataclasses import dataclass, field

TRASH_LABEL = "is_trash"

DOMAIN_LABELS = {
    "showbiz": ["Phẫn nộ", "Cà khịa", "Đồng cảm", "Ủng hộ", "Trung lập", TRASH_LABEL],
    "education": ["tích cực", "tiêu cực", "trung lập", "ý kiến riêng", TRASH_LABEL],
}

# Cột nhãn LLM mặc định theo lĩnh vực (file verify_*_5k.xlsx)
LLM_LABEL_COL = {"showbiz": "llm_emotion", "education": "llm_stance"}

# Tên viết khác/gõ sai thường gặp trong nhãn người gán -> nhãn chuẩn (so khớp sau khi lower+strip)
LABEL_ALIASES = {
    "ứng hộ": "Ủng hộ", "ung ho": "Ủng hộ",
    "phan no": "Phẫn nộ", "ca khia": "Cà khịa", "dong cam": "Đồng cảm", "trung lap": "Trung lập",
    "tich cuc": "tích cực", "tieu cuc": "tiêu cực", "y kien rieng": "ý kiến riêng",
    "rác": TRASH_LABEL, "rac": TRASH_LABEL, "trash": TRASH_LABEL, "spam": TRASH_LABEL,
}


@dataclass
class ColumnMap:
    text: str = "text"
    label: str = "label"  # nhãn cuối đã gộp sẵn trong file (ưu tiên nhất nếu có)
    is_synthetic: str = "is_synthetic"  # True = câu sinh tăng cường: chỉ cho vào train
    event_id: str = "event_id"
    comment_id: str = "comment_id"
    verified_label: str = "verified_label"
    is_trash: str = "is_trash"
    llm_label: str = ""  # để trống = tự chọn theo lĩnh vực (LLM_LABEL_COL)


@dataclass
class TrainConfig:
    domain: str = "showbiz"
    model_name: str = "vinai/phobert-base-v2"
    max_length: int = 256
    epochs: int = 10
    batch_size: int = 16
    lr: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    patience: int = 3
    seed: int = 42
    dropout: float = 0.1
    # verified_or_llm = nhãn cuối: cột label nếu có, else verified_label, else is_trash/nhãn LLM.
    # verified = chỉ dòng có verified_label: các dòng này là chỗ người SỬA nhãn LLM nên lệch phân bố,
    # chỉ dùng để đánh giá, không dùng làm tập train duy nhất.
    label_source: str = "verified_or_llm"
    use_synthetic: bool = True  # False = bỏ dòng sinh (để so sánh có/không tăng cường)
    # event = chia nguyên sự kiện vào từng tập (không rò rỉ); row = stratified theo dòng
    split_mode: str = "event"
    segmenter: str = "underthesea"  # underthesea | none
    columns: ColumnMap = field(default_factory=ColumnMap)
