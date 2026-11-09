import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';

export default function useEventFilters() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const urlQuery = params.get('q') || '';
  const [query, setDraft] = useState(urlQuery);
  const [composing, setComposing] = useState(false);
  const queryRef = useRef(query);
  const urlQueryRef = useRef(urlQuery);
  const compositionRef = useRef(false);
  const compositionQuery = useRef(query);
  const authoredSearch = useRef(null);
  const timer = useRef();
  urlQueryRef.current = urlQuery;

  // Browser Back/header navigation updates the draft. Our own URL writes must
  // not replace text/caret that the user is still editing with a Vietnamese IME.
  useEffect(() => {
    const ownWrite = authoredSearch.current === location.search;
    authoredSearch.current = null;
    if (ownWrite) return;
    clearTimeout(timer.current);
    queryRef.current = urlQuery;
    setDraft(urlQuery);
    compositionRef.current = false;
    setComposing(false);
  }, [location.key, location.search, urlQuery]);

  const updateParams = useCallback((change, options) => {
    clearTimeout(timer.current);
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (queryRef.current) next.set('q', queryRef.current);
      else next.delete('q');
      change(next);
      const value = next.toString();
      authoredSearch.current = value ? `?${value}` : '';
      return next;
    }, options);
  }, [setParams]);

  const commitQuery = useCallback(() => {
    if (compositionRef.current || queryRef.current === urlQueryRef.current) return;
    updateParams((next) => next.delete('page'), { replace: true });
  }, [updateParams]);

  useEffect(() => {
    if (composing || query === urlQuery) return;
    timer.current = setTimeout(commitQuery, 250);
    return () => clearTimeout(timer.current);
  }, [query, urlQuery, composing, commitQuery]);

  const updateQuery = useCallback((value) => {
    queryRef.current = value;
    setDraft(value);
  }, []);
  const startComposition = () => {
    compositionQuery.current = queryRef.current;
    compositionRef.current = true;
    setComposing(true);
  };
  const endComposition = (event) => {
    compositionRef.current = false;
    updateQuery(event.currentTarget.value);
    setComposing(false);
  };
  const changeSource = (value) => updateParams((next) => {
    if (value) next.set('source', value);
    else next.delete('source');
    next.delete('page');
  });
  const changePage = useCallback((page, options) => updateParams((next) => {
    if (page > 1) next.set('page', String(page));
    else next.delete('page');
  }, options), [updateParams]);
  const clearFilters = () => {
    compositionRef.current = false;
    setComposing(false);
    updateQuery('');
    updateParams((next) => ['q', 'source', 'page'].forEach((key) => next.delete(key)));
  };

  return {
    query, filterQuery: composing ? compositionQuery.current : query,
    pendingQuery: composing || query !== urlQuery,
    source: params.get('source') || '', pageParam: params.get('page'),
    updateQuery, startComposition, endComposition, commitQuery, changeSource, changePage, clearFilters,
  };
}
