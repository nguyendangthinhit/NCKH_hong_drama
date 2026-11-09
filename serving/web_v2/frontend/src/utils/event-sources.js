const labels = {
  facebook: 'Facebook',
  news: 'Tin tức',
  youtube: 'YouTube',
  tiktok: 'TikTok',
  threads: 'Threads',
  instagram: 'Instagram',
  unknown: 'Chưa rõ nguồn',
};

export function getEventSource(platform) {
  const value = typeof platform === 'string' ? platform.trim() : '';
  const key = value.toLowerCase() || 'unknown';
  return { key, label: Object.hasOwn(labels, key) ? labels[key] : value || 'Chưa rõ nguồn' };
}
