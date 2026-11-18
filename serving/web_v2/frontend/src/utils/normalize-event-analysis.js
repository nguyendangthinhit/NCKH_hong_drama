import { getAnalysisLabel, normalizeAnalysisLabel } from './event-analysis-labels';
import { getAnalysisComments } from './event-analysis-comments';

const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const textValue = (value) => typeof value === 'string' ? value.trim() : '';

function countValue(value, fallback = 0) {
  if (value === undefined || value === null) return fallback;
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Số lượng bình luận không hợp lệ.');
  return value;
}

export function normalizeEventAnalysis(raw, eventId, domain) {
  if (!isRecord(raw) || raw.id_content !== eventId) {
    throw new Error('Dữ liệu phân tích không khớp sự kiện đang xem.');
  }
  if (!['education', 'showbiz'].includes(domain)) throw new Error('Lĩnh vực phân tích không hợp lệ.');

  const education = domain === 'education';
  const stats = education ? raw.comment_counts : raw.emotion_stats;
  if (!isRecord(stats)) throw new Error('Chưa có thống kê hợp lệ cho sự kiện.');
  const explanations = new Map(Object.entries(isRecord(raw.analysis) ? raw.analysis : {})
    .map(([label, info]) => [normalizeAnalysisLabel(label), info]));
  const groupsByKey = new Map();
  let declaredTotal;
  let excludedCount = 0;

  for (const [label, value] of Object.entries(stats)) {
    const info = getAnalysisLabel(label);
    const count = countValue(isRecord(value) ? value.count : value);
    if (info.key === 'total') {
      if (declaredTotal !== undefined && declaredTotal !== count) throw new Error('Các trường tổng số không nhất quán.');
      declaredTotal = count;
      continue;
    }
    if (info.key === 'rác') {
      excludedCount += count;
      continue;
    }
    const existing = groupsByKey.get(info.key);
    if (existing) {
      existing.count += count;
    } else {
      groupsByKey.set(info.key, {
        ...info,
        count,
        summary: textValue(explanations.get(info.key)?.summary),
      });
    }
  }

  const groups = [...groupsByKey.values()];
  const classifiedCount = groups.reduce((sum, group) => sum + group.count, 0);
  const trashCount = education ? excludedCount : null;
  const collectedCount = education ? declaredTotal ?? classifiedCount + trashCount : null;
  const validCount = education
    ? collectedCount - trashCount
    : countValue(raw.total_comments, classifiedCount);
  if (validCount < classifiedCount) throw new Error('Tổng số bình luận và phân bố nhãn không nhất quán.');

  // Some summaries contain valid comments without an emotion label; do not call them trash.
  const unclassifiedCount = validCount - classifiedCount;
  if (unclassifiedCount > 0) {
    groups.push({ ...getAnalysisLabel('Chưa phân loại'), count: unclassifiedCount, summary: '' });
  }

  return {
    eventId,
    domain,
    kind: education ? 'lập trường' : 'cảm xúc',
    validCount,
    classifiedCount,
    unclassifiedCount,
    trashCount,
    collectedCount,
    groups: groups.map((group) => ({
      ...group,
      percent: validCount > 0 ? group.count / validCount * 100 : 0,
    })),
    comments: getAnalysisComments(raw, domain),
    conclusion: {
      focus: textValue(raw.conclusion?.focus),
      trend: textValue(raw.conclusion?.trend),
    },
  };
}
