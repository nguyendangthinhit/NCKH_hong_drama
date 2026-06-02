/**
 * Các hàm helper dùng chung cho cards & pages
 */

/** Lấy link chính của post */
export function getMainLink(post) {
  return post.link || post.links?.[0] || '#';
}

/** Rút gọn URL để hiển thị */
export function shortenUrl(url, maxPath = 38) {
  try {
    const u = new URL(url);
    const path = u.pathname.slice(0, maxPath);
    return u.hostname.replace('www.', '') + path + (u.pathname.length > maxPath ? '…' : '');
  } catch {
    return url.slice(0, 55) + (url.length > 55 ? '…' : '');
  }
}

/** Kiểm tra chuỗi có phải URL không */
export function isUrl(str) {
  return typeof str === 'string' && /^https?:\/\//i.test(str.trim());
}
