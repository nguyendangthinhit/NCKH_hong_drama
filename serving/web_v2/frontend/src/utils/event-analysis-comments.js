import { getAnalysisLabel } from './event-analysis-labels';

const textValue = (value) => typeof value === 'string' ? value.trim() : '';
const metric = (value) => Number.isFinite(value) && value >= 0 ? value : null;

export function getAnalysisComments(raw, domain) {
  const candidates = [];
  if (domain === 'education') {
    Object.entries(raw.analysis || {}).forEach(([label, info]) => {
      if (Array.isArray(info?.examples)) {
        info.examples.forEach((example) => candidates.push({ value: example, label }));
      }
    });
  } else {
    // One example per emotion keeps smaller groups visible beside popular comments.
    Object.entries(raw.top_comments?.by_emotion || {}).forEach(([label, value]) => {
      candidates.push({ value, label });
    });
    if (Array.isArray(raw.top_comments?.most_popular)) {
      raw.top_comments.most_popular.forEach((value) => candidates.push({ value, label: value?.emotion }));
    }
  }

  const seenIds = new Set();
  const seenText = new Set();
  const comments = [];
  for (const { value, label } of candidates) {
    const text = typeof value === 'string' ? value.trim() : textValue(value?.text);
    const id = textValue(value?.comment_id);
    if (!text || (id && seenIds.has(id)) || seenText.has(text)) continue;
    if (id) seenIds.add(id);
    seenText.add(text);
    comments.push({
      id: id || `example-${comments.length}`,
      text,
      ...getAnalysisLabel(label || 'Chưa xác định'),
      likes: metric(value?.likes),
      replyCount: metric(value?.reply_count),
      score: metric(value?.score),
    });
    if (comments.length === 12) break;
  }
  return comments;
}
