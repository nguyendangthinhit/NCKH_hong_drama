import { useCallback, useEffect, useState } from 'react';
import { getLatestEvents } from '../services/latest-events-api';

export default function useLatestEvents(limit) {
  const [result, setResult] = useState({ events: [], loading: true, failed: false });
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setResult({ events: [], loading: true, failed: false });
    getLatestEvents(limit, { signal: controller.signal })
      .then((events) => {
        if (!controller.signal.aborted) setResult({ events, loading: false, failed: false });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ events: [], loading: false, failed: true });
      });
    return () => controller.abort();
  }, [limit, attempt]);

  return { ...result, reload };
}
