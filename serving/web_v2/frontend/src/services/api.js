const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const mapEvent = (e) => ({
  id: e.id_content,
  title: e.title,
  category: e.category,
  platform: e.platform,
  description: e.description,
  links: e.links || [],
  status: e.status,
  totalComments: e.total_comments,
  isHot: e.is_hot,
  hotRank: e.hot_rank,
  imageUrl: e.image_url,
});

async function apiFetch(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export const getAllPosts = async () => {
  const json = await apiFetch('/api/events?per_page=9999');
  return json.data.map(mapEvent);
};

export const getPostsByPlatform = async (platform) => {
  const posts = await getAllPosts();
  return posts.filter(
    (p) => p.platform?.toLowerCase() === platform?.toLowerCase()
  );
};

export const getPostById = async (id) => {
  const json = await apiFetch(`/api/event/${id}`);
  return mapEvent(json);
};

export const getRelatedPosts = async (id, platform) => {
  const posts = await getPostsByPlatform(platform);
  return posts.filter((p) => String(p.id) !== String(id)).slice(0, 4);
};

export const searchPosts = async (query, platform = null) => {
  const params = new URLSearchParams({ per_page: '9999' });
  if (query) params.set('q', query);
  const json = await apiFetch(`/api/events?${params}`);
  let results = json.data.map(mapEvent);
  if (platform) {
    results = results.filter(
      (p) => p.platform?.toLowerCase() === platform.toLowerCase()
    );
  }
  return results;
};

export const getLatestPostsByPlatform = async (platform, limit = 5) => {
  const params = new URLSearchParams({ per_page: String(limit) });
  const json = await apiFetch(`/api/events?${params}`);
  return json.data.map(mapEvent);
};

export const getPaginatedPosts = async (platform, page = 1, perPage = 12) => {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
  });
  const json = await apiFetch(`/api/events?${params}`);
  return {
    data: json.data.map(mapEvent),
    total: json.total,
    totalPages: json.total_pages,
    currentPage: json.page,
  };
};

export const getHotEvents = async (category, limit = 10) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (category) params.set('category', category);
  const json = await apiFetch(`/api/hot?${params}`);
  return json.data.map(mapEvent);
};

export const getCategories = async () => {
  const json = await apiFetch('/api/categories');
  return json.data;
};
