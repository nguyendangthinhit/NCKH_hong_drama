import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { getPostById } from '../../services/api';
import EventDetailContent from './event-detail-content';
import styles from './event-detail-page.module.scss';

function EventDetail({ id, onRetry }) {
  const [result, setResult] = useState({ status: 'loading', post: null });

  useEffect(() => {
    const controller = new AbortController();
    window.scrollTo(0, 0);

    getPostById(id, { signal: controller.signal })
      .then((post) => {
        if (!controller.signal.aborted) setResult({ status: 'success', post });
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setResult({ status: error.status === 404 ? 'not-found' : 'error', post: null });
        }
      });

    return () => controller.abort();
  }, [id]);

  if (result.status === 'loading') {
    return <p className={styles.notice} role="status">Đang tải thông tin sự kiện…</p>;
  }

  if (result.status !== 'success') {
    const notFound = result.status === 'not-found';
    return (
      <section className={styles.notice} role="alert">
        <h1>{notFound ? 'Không tìm thấy sự kiện' : 'Chưa tải được sự kiện'}</h1>
        <p>
          {notFound
            ? 'Sự kiện không tồn tại hoặc đã được gỡ. Bạn có thể quay lại danh sách để chọn sự kiện khác.'
            : 'Không thể kết nối để lấy thông tin. Vui lòng thử lại sau.'}
        </p>
        {!notFound && <button className={styles.button} onClick={onRetry}>Thử lại</button>}
      </section>
    );
  }

  return <EventDetailContent post={result.post} />;
}

export default function EventDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const [attempt, setAttempt] = useState(0);
  const from = location.state?.from;
  const backPath = typeof from === 'string' && /^\/(?!\/)/.test(from) ? from : '/';

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <Link to={backPath} className={styles.back}>
          <ArrowLeftOutlined /> Quay lại danh sách
        </Link>
        {/* Remount for a new ID/retry so an earlier event never flashes while loading. */}
        <EventDetail key={`${id}:${attempt}`} id={id} onRetry={() => setAttempt((value) => value + 1)} />
      </div>
    </main>
  );
}
