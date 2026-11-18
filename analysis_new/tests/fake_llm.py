"""Client thay thế dùng trong test (không gọi mạng): đọc mã Kx.y trong prompt và trả JSON
đúng định dạng prompt yêu cầu. Chỉ để kiểm luồng code, không phải kết quả phân tích."""

import json
import re


class FakeLLM:
    def __init__(self, label="Cà khịa"):
        self.label, self.requests_sent = label, 0

    def complete(self, prompt):
        self.requests_sent += 1
        if '"summaries"' in prompt:  # request tổng hợp sự kiện (Giáo dục)
            return json.dumps({"summaries": {}, "focus": "f", "trend": "t"}), "fake"
        field = "emotion" if '"emotion"' in prompt else "stance"
        groups = {}
        for lid, trash in re.findall(r"\[(K\d+\.\d+)\] \([^)]*\)( \[rác)?", prompt):
            if not trash:
                groups.setdefault(lid.split(".")[0], []).append(
                    {"id": lid, "is_trash": False, field: self.label, "toxic": False})
        out = {"clusters": [{"cluster": k, "summary": f"tóm tắt {k}", "comments": v}
                            for k, v in groups.items()]}
        return "```json\n" + json.dumps(out, ensure_ascii=False) + "\n```", "fake"


def fake_factory():
    return FakeLLM()
