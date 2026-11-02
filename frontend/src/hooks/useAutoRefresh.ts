import { useEffect, useRef } from 'react';

interface AutoRefreshOptions {
  intervalMs?: number;
  enabled?: boolean;
}

/**
 * Focus-aware auto-refresh hook with exponential backoff on failure.
 *
 * - Default polling interval: 30 seconds.
 * - Backoff schedule:
 *     1st consecutive failure: 30 seconds
 *     2nd consecutive failure: 60 seconds
 *     3rd+ consecutive failure: 120 seconds maximum
 * - Halts polling on HTTP 401/403 authentication/authorization errors.
 * - Honors HTTP 429 Retry-After values if available.
 * - Suspends polling while tab is hidden; resumes when tab regains visibility/focus.
 * - Prevents overlapping executions.
 * - Cleans up timers and event listeners on unmount.
 */
export function useAutoRefresh(
  refreshFn: () => void | Promise<void>,
  options: AutoRefreshOptions = {}
) {
  const { intervalMs = 30000, enabled = true } = options;
  const refreshFnRef = useRef(refreshFn);
  const isRefreshingRef = useRef(false);
  const consecutiveFailuresRef = useRef(0);
  const stoppedDueToAuthRef = useRef(false);
  const timerRef = useRef<any>(null);

  useEffect(() => {
    refreshFnRef.current = refreshFn;
  }, [refreshFn]);

  useEffect(() => {
    if (!enabled) return;

    let isMounted = true;

    const clearScheduledTimer = () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    const scheduleNext = (delayMs: number) => {
      clearScheduledTimer();
      if (!isMounted || stoppedDueToAuthRef.current || document.hidden) return;
      timerRef.current = setTimeout(runRefresh, delayMs);
    };

    const computeDelay = (failures: number, retryAfterSec?: number): number => {
      if (retryAfterSec && retryAfterSec > 0) {
        return Math.min(retryAfterSec * 1000, 120000);
      }
      if (failures === 0) {
        return intervalMs;
      }
      if (failures === 1) {
        return 30000;
      }
      if (failures === 2) {
        return 60000;
      }
      return 120000;
    };

    const runRefresh = async () => {
      if (!isMounted || isRefreshingRef.current) return;
      if (document.hidden) return;
      if (stoppedDueToAuthRef.current) return;

      isRefreshingRef.current = true;
      try {
        await refreshFnRef.current();
        if (!isMounted) return;
        consecutiveFailuresRef.current = 0;
        scheduleNext(intervalMs);
      } catch (err: any) {
        if (!isMounted) return;

        // Check for HTTP 401 or 403 to halt polling
        const status = err?.status ?? err?.response?.status ?? (typeof err?.message === 'string' && (err.message.includes('401') ? 401 : err.message.includes('403') ? 403 : undefined));
        if (status === 401 || status === 403) {
          console.warn('[useAutoRefresh] Polling halted due to authentication/authorization status:', status);
          stoppedDueToAuthRef.current = true;
          return;
        }

        // Check for HTTP 429 Retry-After
        let retryAfterSec: number | undefined;
        if (status === 429 || (err?.message && err.message.includes('429'))) {
          const rawHeader = err?.headers?.get?.('retry-after') ?? err?.response?.headers?.get?.('retry-after') ?? err?.retryAfter;
          if (rawHeader) {
            const parsed = parseInt(String(rawHeader), 10);
            if (!isNaN(parsed) && parsed > 0) {
              retryAfterSec = parsed;
            }
          }
        }

        consecutiveFailuresRef.current += 1;
        const delay = computeDelay(consecutiveFailuresRef.current, retryAfterSec);
        console.warn(
          `[useAutoRefresh] Background poll failed (consecutive failure #${consecutiveFailuresRef.current}). Backing off for ${delay / 1000}s.`,
          err
        );
        scheduleNext(delay);
      } finally {
        isRefreshingRef.current = false;
      }
    };

    // Initial timer
    scheduleNext(intervalMs);

    // Tab visibility change listener
    const handleVisibilityChange = () => {
      if (document.hidden) {
        clearScheduledTimer();
      } else {
        if (!stoppedDueToAuthRef.current && !isRefreshingRef.current) {
          runRefresh();
        }
      }
    };

    // Window focus listener
    const handleWindowFocus = () => {
      if (!document.hidden && !stoppedDueToAuthRef.current && !isRefreshingRef.current) {
        runRefresh();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleWindowFocus);

    return () => {
      isMounted = false;
      clearScheduledTimer();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [intervalMs, enabled]);
}
