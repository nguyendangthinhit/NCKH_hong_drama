// Truy vấn mẫu. Thay $event bằng id sự kiện.

// 1. Phân bố nhãn theo sự kiện
MATCH (c:Comment)-[:IN_EVENT]->(e:Event {id: $event})
RETURN c.label AS label, count(*) AS n ORDER BY n DESC;

// 2. Chuỗi trả lời dài nhất (độ sâu thread)
MATCH p = (c:Comment)-[:REPLY_TO*1..]->(root:Comment)
WHERE c.event_id = $event AND NOT (root)-[:REPLY_TO]->()
RETURN c.uid, length(p) AS depth ORDER BY depth DESC LIMIT 10;

// 3. Bình luận được trả lời nhiều nhất
MATCH (r:Comment)-[:REPLY_TO]->(c:Comment)
WHERE c.event_id = $event
RETURN c.uid, c.text, count(r) AS replies ORDER BY replies DESC LIMIT 10;

// 4. Thread tranh cãi: parent và reply khác nhãn
MATCH (r:Comment)-[:REPLY_TO]->(p:Comment)
WHERE r.event_id = $event AND r.label <> p.label
RETURN p.uid, p.label, r.uid, r.label LIMIT 25;

// 5. GNN dự đoán sai (trên tập test)
MATCH (c:Comment)
WHERE c.split = 'test' AND c.pred_label IS NOT NULL AND c.pred_label <> c.label
RETURN c.event_id, c.label, c.pred_label, c.pred_conf, c.text LIMIT 25;
