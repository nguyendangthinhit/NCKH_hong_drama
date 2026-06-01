import { useState, useEffect } from 'react';
import { FireOutlined } from '@ant-design/icons';
import { getHotEvents } from '../../services/api';
import PostCard from '../PostCard/PostCard';
import styles from './TrendingSection.module.scss';

const TABS = ['Giải trí', 'Giáo dục'];

export default function TrendingSection() {
  const [activeTab, setActiveTab] = useState(TABS[0]);
  const [cache, setCache] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (cache[activeTab]) return;

    const load = async () => {
      setLoading(true);
      try {
        const data = await getHotEvents(activeTab, 10);
        setCache((prev) => ({ ...prev, [activeTab]: data }));
      } catch (err) {
        console.error(err);
        setCache((prev) => ({ ...prev, [activeTab]: [] }));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [activeTab, cache]);

  const events = cache[activeTab] || [];

  return (
    <section className={styles.trending}>
      <div className={styles['trending__container']}>
        <div className={styles['trending__header']}>
          <h2 className={styles['trending__title']}>
            <FireOutlined className={styles['trending__title-icon']} />
            Sự kiện Trending
          </h2>

          <div className={styles['trending__tabs']}>
            {TABS.map((tab) => (
              <button
                key={tab}
                className={`${styles['trending__tab']} ${activeTab === tab ? styles['trending__tab--active'] : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        <div className={styles['trending__list']}>
          {loading ? (
            [...Array(5)].map((_, i) => (
              <div key={i} className={styles['trending__skeleton']} />
            ))
          ) : events.length === 0 ? (
            <div className={styles['trending__empty']}>Không có sự kiện trending</div>
          ) : (
            events.map((post, idx) => (
              <PostCard
                key={post.id}
                post={post}
                variant={activeTab === 'Giải trí' ? 'facebook' : 'news'}
                rank={idx + 1}
                showImage
                compact
                maxLinks={2}
              />
            ))
          )}
        </div>
      </div>
    </section>
  );
}
