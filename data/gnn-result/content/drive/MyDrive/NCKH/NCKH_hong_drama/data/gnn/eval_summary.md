# Đánh giá GNN vs LLM — Tóm tắt

| Domain | F1 macro GNN | F1 weighted GNN | GNN inference (s) | LLM inference (s) | Speedup |
|---|---|---|---|---|---|
| education | 0.5239 | 0.6267 | 0.0868 | 2685.0 | 30951.0x |
| showbiz | 0.217 | 0.9161 | 0.5245 | 10200.0 | 19447.0x |

**Cost LLM giả định:** Gemini Flash 2.5, ~20.250 USD / 1M comment.
**Latency LLM giả định:** 0.5s/call (sequential, không batch).

Diễn giải:
- F1 cao → GNN match LLM tốt → có thể replace LLM ở scale.
- Speedup cao → ROI khi xử lý batch lớn (1M+ comments).