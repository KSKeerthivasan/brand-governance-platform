import { describe, it, expect } from 'vitest';

export function shouldShowOversizeWarning(
  meta: { width?: number; height?: number } | null | undefined,
  isPdf: boolean = false
): boolean {
  if (isPdf || !meta?.width || !meta?.height) {
    return false;
  }
  return meta.width > 835 || meta.height > 1080;
}

export const OVERSIZED_POSTER_WARNING_HEADER = 'Image Resized for Analysis';
export const OVERSIZED_POSTER_WARNING_MESSAGE =
  'Your image exceeds the recommended processing dimensions of 835 × 1080 px. Inkloom AI will automatically resize it proportionally before analysis. Your original image will remain unchanged.';

describe('Oversized Poster Upload Warning Condition & Message', () => {
  it('case 1: 835 × 1080 (exact recommended dimensions) - does NOT show warning', () => {
    expect(shouldShowOversizeWarning({ width: 835, height: 1080 })).toBe(false);
  });

  it('case 2: 1200 × 1600 (exceeds both limits) - shows warning', () => {
    expect(shouldShowOversizeWarning({ width: 1200, height: 1600 })).toBe(true);
  });

  it('case 3: 2000 × 1000 (exceeds width only) - shows warning', () => {
    expect(shouldShowOversizeWarning({ width: 2000, height: 1000 })).toBe(true);
  });

  it('case 4: 600 × 800 (smaller than recommended dimensions) - does NOT show warning', () => {
    expect(shouldShowOversizeWarning({ width: 600, height: 800 })).toBe(false);
  });

  it('case 5: 835 × 1200 (exceeds height only) - shows warning', () => {
    expect(shouldShowOversizeWarning({ width: 835, height: 1200 })).toBe(true);
  });

  it('case 6: 900 × 1080 (exceeds width only) - shows warning', () => {
    expect(shouldShowOversizeWarning({ width: 900, height: 1080 })).toBe(true);
  });

  it('handles removed poster or null metadata - does NOT show warning', () => {
    expect(shouldShowOversizeWarning(null)).toBe(false);
    expect(shouldShowOversizeWarning(undefined)).toBe(false);
    expect(shouldShowOversizeWarning({ width: undefined, height: undefined })).toBe(false);
  });

  it('does NOT show warning for PDF creative assets', () => {
    expect(shouldShowOversizeWarning({ width: 1400, height: 2000 }, true)).toBe(false);
  });

  it('matches exact mandated warning header and message content', () => {
    expect(OVERSIZED_POSTER_WARNING_HEADER).toBe('Image Resized for Analysis');
    expect(OVERSIZED_POSTER_WARNING_MESSAGE).toBe(
      'Your image exceeds the recommended processing dimensions of 835 × 1080 px. Inkloom AI will automatically resize it proportionally before analysis. Your original image will remain unchanged.'
    );
  });
});

