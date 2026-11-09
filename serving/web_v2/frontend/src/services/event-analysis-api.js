import { normalizeEventAnalysis } from '../utils/normalize-event-analysis';

const ANALYSIS_BASE = (import.meta.env.VITE_ANALYSIS_BASE
  || 'https://raw.githubusercontent.com/nguyendangthinhit/NCKH_hong_drama/main/data').replace(/\/+$/, '');
const FOLDERS = {
  education: 'process_education/analyzed_dataa',
  showbiz: 'process_showbiz/analyzed_data',
};

export function getEventAnalysisSource(eventId) {
  if (typeof eventId !== 'string' || !/^(education|showbiz)_[a-zA-Z0-9_-]+$/.test(eventId)) return null;
  const domain = eventId.startsWith('education_') ? 'education' : 'showbiz';
  return {
    domain,
    url: `${ANALYSIS_BASE}/processed/${FOLDERS[domain]}/summary/${encodeURIComponent(eventId)}.json`,
  };
}

export async function getEventAnalysis(eventId, { signal } = {}) {
  const source = getEventAnalysisSource(eventId);
  if (!source) return null;
  const controller = new AbortController();
  const abort = () => controller.abort();
  let timedOut = false;
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 15000);

  try {
    const response = await fetch(source.url, { signal: controller.signal, cache: 'no-cache' });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Không tải được dữ liệu phân tích (HTTP ${response.status}).`);
    const raw = await response.json();
    return { ...normalizeEventAnalysis(raw, eventId, source.domain), sourceUrl: source.url };
  } catch (error) {
    if (timedOut) throw new Error('Quá thời gian chờ tải dữ liệu phân tích.');
    throw error;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}
