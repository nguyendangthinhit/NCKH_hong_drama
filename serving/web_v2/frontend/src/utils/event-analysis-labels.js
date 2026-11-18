const COLORS = {
  'tích cực': '#059669',
  'tiêu cực': '#dc2626',
  'trung lập': '#64748b',
  'ý kiến riêng': '#d97706',
  'phẫn nộ': '#dc2626',
  'cà khịa': '#d97706',
  'đồng cảm': '#2563eb',
  'ủng hộ': '#059669',
};

export function normalizeAnalysisLabel(value) {
  return String(value).normalize('NFC').trim().replace(/_/g, ' ').replace(/\s+/g, ' ').toLowerCase();
}

export function getAnalysisLabel(value) {
  const key = normalizeAnalysisLabel(value);
  return {
    key,
    label: key.charAt(0).toUpperCase() + key.slice(1),
    color: COLORS[key] || '#6b7280',
  };
}
