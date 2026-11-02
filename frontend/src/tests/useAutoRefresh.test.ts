import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

describe('useAutoRefresh hook', () => {
  let container: HTMLDivElement;
  let root: any;

  beforeEach(() => {
    vi.useFakeTimers();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    Object.defineProperty(document, 'hidden', { value: false, configurable: true, writable: true });
  });

  afterEach(async () => {
    if (root) {
      await act(async () => {
        root.unmount();
      });
    }
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
    vi.restoreAllMocks();
  });

  function renderAutoRefresh(refreshFn: any, options = {}) {
    function TestComponent() {
      useAutoRefresh(refreshFn, options);
      return null;
    }
    act(() => {
      root.render(React.createElement(TestComponent));
    });
  }

  it('polls at the specified normal interval (30s) when healthy', async () => {
    const refreshFn = vi.fn().mockResolvedValue(undefined);
    renderAutoRefresh(refreshFn, { intervalMs: 30000 });

    expect(refreshFn).not.toHaveBeenCalled();

    // Advance 30 seconds
    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);

    // Advance another 30 seconds
    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(2);
  });

  it('backs off exponentially on consecutive errors: 30s -> 60s -> 120s max', async () => {
    const refreshFn = vi.fn().mockRejectedValue(new Error('500 Internal Server Error'));
    renderAutoRefresh(refreshFn, { intervalMs: 30000 });

    // 1st tick at 30s: fails
    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);

    // 1st consecutive failure delay is 30s
    await act(async () => {
      vi.advanceTimersByTime(29000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(2);

    // 2nd consecutive failure delay is 60s
    await act(async () => {
      vi.advanceTimersByTime(59000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(2);
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(3);

    // 3rd consecutive failure delay is 120s max
    await act(async () => {
      vi.advanceTimersByTime(119000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(3);
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(4);
  });

  it('resets backoff interval upon successful recovery', async () => {
    let callCount = 0;
    const refreshFn = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) throw new Error('Temporary failure');
      return;
    });

    renderAutoRefresh(refreshFn, { intervalMs: 30000 });

    // 1st call fails at 30s
    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);

    // Backoff 30s, 2nd call succeeds
    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(2);

    // Next scheduled call should be back to standard interval (30s)
    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(3);
  });

  it('halts polling on HTTP 401 and 403 errors', async () => {
    const authError = { status: 401, message: 'Unauthorized' };
    const refreshFn = vi.fn().mockRejectedValue(authError);

    renderAutoRefresh(refreshFn, { intervalMs: 30000 });

    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);

    // Advance 5 minutes - should NOT retry because auth error halted polling
    await act(async () => {
      vi.advanceTimersByTime(300000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);
  });

  it('honors HTTP 429 Retry-After header', async () => {
    const rateLimitError = {
      status: 429,
      headers: {
        get: (h: string) => (h === 'retry-after' ? '45' : null)
      }
    };
    const refreshFn = vi.fn().mockRejectedValue(rateLimitError);

    renderAutoRefresh(refreshFn, { intervalMs: 30000 });

    // Initial 30s call
    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);

    // Should wait 45s (Retry-After)
    await act(async () => {
      vi.advanceTimersByTime(44000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(refreshFn).toHaveBeenCalledTimes(2);
  });

  it('suspends polling when document is hidden and resumes on visibility change', async () => {
    Object.defineProperty(document, 'hidden', { value: true, configurable: true, writable: true });
    const refreshFn = vi.fn().mockResolvedValue(undefined);

    renderAutoRefresh(refreshFn, { intervalMs: 30000 });

    await act(async () => {
      vi.advanceTimersByTime(60000);
    });
    expect(refreshFn).not.toHaveBeenCalled();

    // Document becomes visible
    Object.defineProperty(document, 'hidden', { value: false, configurable: true, writable: true });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(refreshFn).toHaveBeenCalledTimes(1);
  });
});
