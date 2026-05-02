
// BẠN SẼ ĐIỀN LINK API TỪ GOOGLE APPS SCRIPT HOẶC (SHEETDB, MOCKAPI...) VÀO ĐÂY:
const DRIVE_API_URL = 'https://script.google.com/macros/s/AKfycbynT1r0tDzNhf8er-zNsDIJuQB5yfpy6VrxhDk_k83EB9FPOkYbKq1NF16nFMZ2403C/exec'; 

const SIMULATED_DELAY = 600;

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Apps Script đã trả về đúng cấu trúc, KHÔNG cần map lại.
 * Shape mỗi post: { id, title, description, platform, links[], status, category, type }
 * platform = "facebook" | "news"  (do Apps Script tự set theo sheet name)
 * links    = string[]             (đã split sẵn theo , hoặc ;)
 */

// Hàm dùng để lấy dữ liệu. Nếu có DRIVE_API_URL thì gọi API, nếu không thì dùng mockData.
const fetchFromDrive = async () => {
  if (!DRIVE_API_URL) {
    await delay(SIMULATED_DELAY);
    return mockData.posts;
  }
  try {
    const response = await fetch(DRIVE_API_URL);
    const raw = await response.json();
    // Apps Script trả về { posts: [...] }
    const posts = raw.posts || raw;
    return Array.isArray(posts) ? posts : [];
  } catch (err) {
    console.error('Lỗi lấy dữ liệu từ Drive, dùng tạm dữ liệu mẫu:', err);
    await delay(SIMULATED_DELAY);
    return mockData.posts; // Fallback
  }
};

// Get all posts
export const getAllPosts = async () => {
  const posts = await fetchFromDrive();
  return posts;
};

// Get posts by platform (khớp không phân biệt hoa-thường)
export const getPostsByPlatform = async (platform) => {
  const posts = await fetchFromDrive();
  return posts.filter(
    (post) => post.platform?.toLowerCase() === platform?.toLowerCase()
  );
};

// Get a single post by ID (id từ GG Sheet là chuỗi như 'showbiz_001')
export const getPostById = async (id) => {
  const posts = await fetchFromDrive();
  const post = posts.find((p) => String(p.id) === String(id));
  if (!post) throw new Error('Post not found');
  return post;
};

// Get related posts (same platform, excluding current)
export const getRelatedPosts = async (id, platform) => {
  const posts = await fetchFromDrive();
  return posts
    .filter(
      (p) =>
        p.platform?.toLowerCase() === platform?.toLowerCase() &&
        String(p.id) !== String(id)
    )
    .slice(0, 4);
};

// Search posts
export const searchPosts = async (query, platform = null) => {
  let results = await fetchFromDrive();

  if (platform) {
    results = results.filter(
      (p) => p.platform?.toLowerCase() === platform?.toLowerCase()
    );
  }

  if (query) {
    const lowerQuery = query.toLowerCase();
    results = results.filter(
      (p) =>
        p.title?.toLowerCase().includes(lowerQuery) ||
        // Tìm trong danh sách link
        p.links?.some((link) => link.toLowerCase().includes(lowerQuery))
    );
  }

  return results;
};

// Get latest posts (for homepage preview)
// GG Sheet không có cột date → giữ nguyên thứ tự từ sheet, chỉ lấy limit đầu
export const getLatestPostsByPlatform = async (platform, limit = 5) => {
  const posts = await fetchFromDrive();
  return posts
    .filter((p) => p.platform?.toLowerCase() === platform?.toLowerCase())
    .slice(0, limit);
};

// Paginate posts
export const getPaginatedPosts = async (platform, page = 1, perPage = 6) => {
  const posts = await fetchFromDrive();
  const allPlatformPosts = posts.filter(
    (p) => p.platform?.toLowerCase() === platform?.toLowerCase()
  );

  const total = allPlatformPosts.length;
  const totalPages = Math.ceil(total / perPage);
  const start = (page - 1) * perPage;
  const data = allPlatformPosts.slice(start, start + perPage);

  return { data, total, totalPages, currentPage: page };
};
