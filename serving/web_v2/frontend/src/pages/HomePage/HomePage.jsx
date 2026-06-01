import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  FacebookOutlined,
  GlobalOutlined,
  FireOutlined,
  ThunderboltOutlined,
  LinkOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { getLatestPostsByPlatform } from '../../services/api';
import PostCard from '../../components/PostCard/PostCard';
import TrendingSection from '../../components/TrendingSection/TrendingSection';
import styles from './HomePage.module.scss';

export default function HomePage() {
  const [apiPosts, setApiPosts] = useState({ fb: [], news: [] });
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const [fb, news] = await Promise.all([
          getLatestPostsByPlatform('facebook', 5),
          getLatestPostsByPlatform('news', 6),
        ]);
        setApiPosts({ fb, news });
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  return (
    <main className={styles.homepage}>

      {/* ── Hero ── */}
      <div className={styles.hero}>
        <div className={styles['hero__container']}>
          <div className={styles['hero__inner']}>
            <div className={styles['hero__text']}>
              <span className={styles['hero__eyebrow']}><FireOutlined /> Cập nhật liên tục</span>
              <h1 className={styles['hero__title']}>
                Drama &amp; Tin tức{' '}
                <span className={styles['hero__title-accent']}>nóng hổi</span>
                <br />mỗi ngày
              </h1>
              <p className={styles['hero__desc']}>
                Tổng hợp sự kiện, drama giải trí từ Facebook và các báo chính thống.
                Cập nhật nhanh, đầy đủ nguồn tham khảo.
              </p>
              <div className={styles['hero__cta']}>
                <Link to="/facebook" className={`${styles['hero__btn']} ${styles['hero__btn--primary']}`}>
                  <FacebookOutlined /> Xem Facebook
                </Link>
                <Link to="/news" className={`${styles['hero__btn']} ${styles['hero__btn--outline']}`}>
                  <GlobalOutlined /> Tin tức
                </Link>
              </div>
            </div>

            {/* Stats */}
            <div className={styles['hero__stats']}>
              <div className={styles['hero__stat']}>
                <span className={styles['hero__stat-num']}><FacebookOutlined /></span>
                <span className={styles['hero__stat-label']}>Facebook</span>
              </div>
              <div className={styles['hero__stat']}>
                <span className={styles['hero__stat-num']}><GlobalOutlined /></span>
                <span className={styles['hero__stat-label']}>Tin tức</span>
              </div>
              <div className={styles['hero__stat']}>
                <span className={styles['hero__stat-num']}><ThunderboltOutlined /></span>
                <span className={styles['hero__stat-label']}>Live</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Wave */}
      <div className={styles['hero-wave']}>
        <svg viewBox="0 0 1440 48" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M0,32 C360,0 1080,64 1440,32 L1440,48 L0,48 Z" fill="#fcf8f8"/>
        </svg>
      </div>

      {/* ── Ticker ── */}
      {!loading && apiPosts.fb.length > 0 && (
        <div className={styles.ticker}>
          <div className={styles['ticker__inner']}>
            <span className={styles['ticker__label']}><FireOutlined /> Mới nhất</span>
            <div className={styles['ticker__track']}>
              <span className={styles['ticker__text']}>
                {[...apiPosts.fb, ...apiPosts.news]
                  .map((p) => p.title)
                  .filter(Boolean)
                  .join('   ·   ')}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Trending ── */}
      <TrendingSection />

      {/* ── Facebook section ── */}
      <section className={styles.section}>
        <div className={styles['section__container']}>
          <div className={styles['section__header']}>
            <h2 className={styles['section__title']}>
              <span className={styles['section__title-bar']} />
              <FacebookOutlined className={styles['section__title-icon']} />
              Tin hot Facebook
            </h2>
            <Link to="/facebook" className={styles['section__viewall']}>
              Xem tất cả <RightOutlined />
            </Link>
          </div>

          <div className={styles['fb-list']}>
            {loading
              ? [0, 1, 2].map((i) => <div key={i} className={styles['fb-card-skeleton']} />)
              : apiPosts.fb.map((post) => (
                  <PostCard
                    key={post.id}
                    post={post}
                    variant="facebook"
                    maxLinks={3}
                    compact
                  />
                ))}
          </div>
        </div>
      </section>

      {/* ── News section ── */}
      <section className={styles.section}>
        <div className={styles['section__container']}>
          <div className={styles['section__header']}>
            <h2 className={styles['section__title']}>
              <span className={styles['section__title-bar']} />
              <GlobalOutlined className={styles['section__title-icon']} />
              Tin tức nổi bật
            </h2>
            <Link to="/news" className={styles['section__viewall']}>
              Xem tất cả <RightOutlined />
            </Link>
          </div>

          <div className={styles['news-list']}>
            {loading
              ? [0, 1, 2, 3].map((i) => <div key={i} className={styles['news-card-skeleton']} />)
              : apiPosts.news.map((post) => (
                  <PostCard
                    key={post.id}
                    post={post}
                    variant="news"
                    maxLinks={3}
                    compact
                  />
                ))}
          </div>
        </div>
      </section>

    </main>
  );
}