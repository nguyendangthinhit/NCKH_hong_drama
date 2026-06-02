import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { FacebookOutlined, SearchOutlined } from '@ant-design/icons';
import { getPaginatedPosts } from '../../services/api';
import PostCard from '../../components/PostCard/PostCard';
import Pagination from '../../components/Pagination/Pagination';
import styles from './FacebookPage.module.scss';

const PER_PAGE = 10;

export default function FacebookPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [allPosts, setAllPosts] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [query, setQuery]       = useState('');
  const [page, setPage]         = useState(1);

  // Lấy category từ URL ?cat=...
  const activeCategory = searchParams.get('cat') || '';

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await getPaginatedPosts('facebook', 1, 9999);
        setAllPosts(res.data || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Reset về trang 1 khi đổi category / query
  useEffect(() => { setPage(1); }, [activeCategory, query]);

  // Các category duy nhất có trong dữ liệu
  const categories = useMemo(() => {
    const set = new Set(allPosts.map((p) => p.category).filter(Boolean));
    return [...set];
  }, [allPosts]);

  const filtered = useMemo(() => {
    let result = allPosts;
    if (activeCategory) result = result.filter((p) => p.category === activeCategory);
    if (query.trim()) {
      const q = query.toLowerCase();
      result = result.filter(
        (p) =>
          p.title?.toLowerCase().includes(q) ||
          p.category?.toLowerCase().includes(q) ||
          p.links?.some((l) => l.toLowerCase().includes(q))
      );
    }
    return result;
  }, [allPosts, query, activeCategory]);

  const totalPages = Math.ceil(filtered.length / PER_PAGE);
  const paginated  = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const handleSearch   = (e) => { setQuery(e.target.value); setPage(1); };
  const handleCategory = (cat) => {
    setPage(1);
    if (cat) setSearchParams({ cat });
    else     setSearchParams({});
  };

  return (
    <div className={styles.page}>
      {/* Hero */}
      <div className={styles.hero}>
        <div className={styles['hero__container']}>
          <div className={styles['hero__inner']}>
            <div className={styles['hero__icon']}><FacebookOutlined /></div>
            <div className={styles['hero__text']}>
              <h1>Facebook{activeCategory ? ` — ${activeCategory}` : ''}</h1>
              <p>Tổng hợp sự kiện, drama nổi bật trên Facebook</p>
            </div>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles['search-wrap']}>
          <SearchOutlined className={styles['search-icon']} />
          <input
            id="fb-search"
            className={styles.search}
            type="text"
            placeholder="Tìm kiếm sự kiện, link..."
            value={query}
            onChange={handleSearch}
          />
        </div>

        {/* Category filter */}
        {categories.length > 0 && (
          <div className={styles['filter-group']}>
            <button
              className={`${styles['filter-btn']} ${!activeCategory ? styles['filter-btn--active'] : ''}`}
              onClick={() => handleCategory('')}
            >
              Tất cả
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                className={`${styles['filter-btn']} ${activeCategory === cat ? styles['filter-btn--active'] : ''}`}
                onClick={() => handleCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        )}

        {!loading && (
          <span className={styles['count-badge']}>{filtered.length} sự kiện</span>
        )}
      </div>

      {/* List */}
      <div className={styles.container}>
        {loading ? (
          <div className={styles.list}>
            {[...Array(6)].map((_, i) => <div key={i} className={styles.skeleton} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className={styles.empty}>
            <div className={styles['empty__icon']}><SearchOutlined /></div>
            <div className={styles['empty__text']}>Không tìm thấy kết quả</div>
            <div className={styles['empty__sub']}>Thử từ khoá hoặc danh mục khác</div>
          </div>
        ) : (
          <>
            <div className={styles.list}>
              {paginated.map((post, idx) => (
                <PostCard key={post.id ?? idx} post={post} variant="facebook" />
              ))}
            </div>
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
