import { useState, useEffect } from 'react';
import { FireOutlined } from '@ant-design/icons';
import { getLatestPostsByPlatform } from '../../services/api';
import useLatestEvents from '../../hooks/use-latest-events';
import TrendingSection from '../../components/TrendingSection/TrendingSection';
import FeaturedEvents from '../../components/home/featured-events';
import HomeSidebar from '../../components/home/home-sidebar';
import LatestEventsRail from '../../components/home/latest-events-rail';
import styles from './HomePage.module.scss';

export default function HomePage() {
  const [apiPosts, setApiPosts] = useState({ fb: [], news: [] });
  const { events: latestEvents, loading: latestLoading, failed: latestFailed } = useLatestEvents(6);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const fetchAll = async () => {
      try {
        const [fb, news] = await Promise.all([
          getLatestPostsByPlatform('facebook', 5),
          getLatestPostsByPlatform('news', 6),
        ]);
        if (active) setApiPosts({ fb, news });
      } catch (error) {
        console.error(error);
        if (active) setFailed(true);
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchAll();
    return () => { active = false; };
  }, []);

  const allPosts = [...apiPosts.fb, ...apiPosts.news];
  const featured = [...new Map(allPosts.map((post) => [post.id, post])).values()].slice(0, 4);

  return (
    <main className={styles.homepage}>
      <div className={styles.container}>
        <h1 className={styles.pageTitle}>Sự kiện Showbiz và Giáo dục nổi bật</h1>
        {failed && <p className={styles.error} role="alert">Chưa tải được danh sách sự kiện. Vui lòng kiểm tra kết nối và tải lại trang.</p>}
        <FeaturedEvents posts={featured} loading={loading} />
        {!loading && apiPosts.fb.length > 0 && (
          <div className={styles.ticker}>
            <span className={styles.tickerLabel}><FireOutlined /> Điểm tin</span>
            <div className={styles.tickerWindow}>
              <p className={styles.tickerText}>{allPosts.map((post) => post.title).filter(Boolean).join('   ·   ')}</p>
            </div>
          </div>
        )}
        <div className={styles.contentGrid}>
          <TrendingSection />
          <HomeSidebar posts={apiPosts.fb} news={apiPosts.news} loading={loading} />
        </div>
        <LatestEventsRail posts={latestEvents} loading={latestLoading} failed={latestFailed} />
      </div>
    </main>
  );
}
