import { useEffect, useState } from 'react';
import { getEventAnalysis } from '../../services/event-analysis-api';
import EventAnalysisContent from './event-analysis-content';
import styles from './event-analysis.module.scss';

function AnalysisRequest({ eventId, onRetry }) {
  const [result, setResult] = useState({ status: 'loading', data: null });

  useEffect(() => {
    const controller = new AbortController();
    getEventAnalysis(eventId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ status: data ? 'success' : 'missing', data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ status: 'error', data: null });
      });
    return () => controller.abort();
  }, [eventId]);

  if (result.status === 'loading') {
    return <p className={styles.notice} role="status">Đang tải phân tích bình luận…</p>;
  }
  if (result.status === 'missing') {
    return (
      <div className={styles.notice} role="status">
        <p>Chưa có dữ liệu phân tích cho sự kiện này trên nguồn hiện tại.</p>
        <p>Bạn vẫn có thể đọc thông tin sự kiện và các nguồn tham khảo.</p>
        <button className={styles.retry} onClick={onRetry}>Kiểm tra lại</button>
      </div>
    );
  }
  if (result.status === 'error') {
    return (
      <div className={styles.notice} role="alert">
        <p>Chưa tải được phân tích. Nguồn dữ liệu có thể đang gián đoạn hoặc chưa có dữ liệu hợp lệ.</p>
        <button className={styles.retry} onClick={onRetry}>Thử lại</button>
      </div>
    );
  }
  return <EventAnalysisContent data={result.data} />;
}

export default function EventAnalysis({ eventId }) {
  const [attempt, setAttempt] = useState(0);
  return (
    <AnalysisRequest
      key={`${eventId}:${attempt}`}
      eventId={eventId}
      onRetry={() => setAttempt((value) => value + 1)}
    />
  );
}
