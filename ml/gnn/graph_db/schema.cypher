// Schema Neo4j cho đồ thị thảo luận (chạy bằng load_graph_to_neo4j.py --init-schema, idempotent).
//
// (:Event {id, domain})                     1 sự kiện (education_011, showbiz_033, ...)
// (:Comment {uid, comment_id, event_id, text, depth, in_degree, sibling_count,
//            label, pred_label, pred_conf, split})
// (:Label {key, name, domain})              nhãn (stance/emotion)
// (c)-[:IN_EVENT]->(e)   (c)-[:REPLY_TO]->(parent)   (c)-[:HAS_LABEL]->(l)
//
// uid = "<event_id>::<comment_id>" (comment_id có thể trùng giữa các sự kiện).

CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT comment_uid IF NOT EXISTS FOR (c:Comment) REQUIRE c.uid IS UNIQUE;
CREATE CONSTRAINT label_key IF NOT EXISTS FOR (l:Label) REQUIRE l.key IS UNIQUE;
CREATE INDEX comment_event IF NOT EXISTS FOR (c:Comment) ON (c.event_id);
CREATE INDEX comment_label IF NOT EXISTS FOR (c:Comment) ON (c.label);
CREATE INDEX comment_pred IF NOT EXISTS FOR (c:Comment) ON (c.pred_label);
