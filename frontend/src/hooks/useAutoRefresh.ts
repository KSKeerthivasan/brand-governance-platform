import { useEffect, useRef } from 'react';

interface AutoRefreshOptions {
  intervalMs?: number;
  enabled?: boolean;
}

/**
 * Focus-aware auto-refresh hook.
 * Polls at `intervalMs` only when the document is visible and tab is active.
 * Immediately refetches whenever the window/tab regains focus.
 * Cleans up listeners and timers cleanly on unmount.
 */
export function useAutoRefresh(
  refreshFn: () => void | Promise<void>,
  options: AutoRefreshOptions = {}
) {
  const { intervalMs = 6000, enabled = true } = options;
  const refreshFnRef = useRef(refreshFn);

  useEffect(() => {
    refreshFnRef.current = refreshFn;
  }, [refreshFn]);

  useEffect(() => {
    if (!enabled) return;

    let isMounted = true;
    let isRefreshing = false;

    const executeRefresh = async () => {
      if (!isMounted || isRefreshing) return;
      if (document.hidden) return;

      isRefreshing = true;
      try {
        await refreshFnRef.current();
      } catch (err) {
        // Silently suppress background polling errors to avoid interrupting user workflows
        console.warn('[useAutoRefresh] Background polling error:', err);
      } finally {
        isRefreshing = false;
      }
    };

    // 1. Periodic background timer (6s default)
    const timerId = setInterval(executeRefresh, intervalMs);

    // 2. Refetch on tab visibility change (e.g. user returns to this tab)
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        executeRefresh();
      }
    };

    // 3. Refetch when browser window regains focus
    const handleWindowFocus = () => {
      executeRefresh();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleWindowFocus);

    return () => {
      isMounted = false;
      clearInterval(timerId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [intervalMs, enabled]);
}
