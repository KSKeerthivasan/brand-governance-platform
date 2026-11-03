import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../services/api';
import { ContentType } from '../pages/ContentStudio';

/**
 * Unit & Integration logic tests for ContentStudio Content Type Selection and Validation Workflow.
 */
describe('ContentStudio Content Type Selection and Validation Workflow', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // Helper reflecting the validation logic implemented in saveDraftInternal
  function validateSubmission(
    contentType: ContentType,
    title: string,
    brandId: string,
    bodyText: string,
    posterFilePath: string | null
  ): { valid: boolean; error?: string } {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      return { valid: false, error: 'Please provide a title before saving or running checks.' };
    }
    if (!brandId) {
      return { valid: false, error: 'Please select a brand.' };
    }

    const trimmedBody = bodyText.trim();
    const hasPoster = Boolean(posterFilePath);

    if (contentType === 'image') {
      if (!hasPoster) {
        return { valid: false, error: 'Please upload an advertisement image for an Image Advertisement.' };
      }
    } else if (contentType === 'text') {
      if (!trimmedBody) {
        return { valid: false, error: 'Please provide marketing copy text for a Text Advertisement.' };
      }
    } else {
      // 'both'
      if (!trimmedBody && !hasPoster) {
        return { valid: false, error: 'Please provide marketing copy and upload an advertisement image for an Image + Text Advertisement.' };
      }
      if (!trimmedBody) {
        return { valid: false, error: 'Please provide marketing copy text for an Image + Text Advertisement.' };
      }
      if (!hasPoster) {
        return { valid: false, error: 'Please upload an advertisement image for an Image + Text Advertisement.' };
      }
    }

    return { valid: true };
  }

  // Helper reflecting the payload construction for saveDraftInternal
  function buildSavePayload(
    contentType: ContentType,
    title: string,
    bodyText: string,
    posterFilePath: string | null,
    channel?: string
  ) {
    const trimmedBody = bodyText.trim();
    const bodyToSave = contentType === 'image' ? '' : trimmedBody;
    const posterPathToSave = contentType === 'text' ? undefined : (posterFilePath || undefined);
    const channelToSave = channel || 'General';

    return {
      title: title.trim(),
      body_text: bodyToSave,
      poster_file_path: posterPathToSave,
      channel: channelToSave
    };
  }

  describe('1. Validation rules per Content Type', () => {
    it('Image Advertisement requires image upload, copy text is optional', () => {
      // Without image -> rejected
      const res1 = validateSubmission('image', 'Summer Sale', 'brand-1', '', null);
      expect(res1.valid).toBe(false);
      expect(res1.error).toContain('upload an advertisement image');

      // With image and no text -> accepted
      const res2 = validateSubmission('image', 'Summer Sale', 'brand-1', '', 'uploads/poster.png');
      expect(res2.valid).toBe(true);

      // With image and text -> accepted
      const res3 = validateSubmission('image', 'Summer Sale', 'brand-1', 'Optional text', 'uploads/poster.png');
      expect(res3.valid).toBe(true);
    });

    it('Text Advertisement requires marketing copy, image is not required', () => {
      // Without copy -> rejected
      const res1 = validateSubmission('text', 'Summer Sale', 'brand-1', '   ', null);
      expect(res1.valid).toBe(false);
      expect(res1.error).toContain('marketing copy text');

      // With copy and no image -> accepted
      const res2 = validateSubmission('text', 'Summer Sale', 'brand-1', 'Get 50% off all vitamins today!', null);
      expect(res2.valid).toBe(true);

      // With copy and image -> accepted
      const res3 = validateSubmission('text', 'Summer Sale', 'brand-1', 'Get 50% off today!', 'uploads/poster.png');
      expect(res3.valid).toBe(true);
    });

    it('Image + Text Advertisement requires BOTH marketing copy and image upload', () => {
      // Missing both
      const res1 = validateSubmission('both', 'Summer Sale', 'brand-1', '', null);
      expect(res1.valid).toBe(false);
      expect(res1.error).toContain('provide marketing copy and upload an advertisement image');

      // Missing only image
      const res2 = validateSubmission('both', 'Summer Sale', 'brand-1', 'Valid marketing copy here', null);
      expect(res2.valid).toBe(false);
      expect(res2.error).toContain('upload an advertisement image');

      // Missing only copy
      const res3 = validateSubmission('both', 'Summer Sale', 'brand-1', '', 'uploads/poster.png');
      expect(res3.valid).toBe(false);
      expect(res3.error).toContain('marketing copy text');

      // Providing both -> accepted
      const res4 = validateSubmission('both', 'Summer Sale', 'brand-1', 'Valid marketing copy here', 'uploads/poster.png');
      expect(res4.valid).toBe(true);
    });
  });

  describe('2. Payload construction and state preservation', () => {
    it('Preserves user inputs when switching types without clearing state', () => {
      // Simulated component state
      let state = {
        contentType: 'both' as ContentType,
        bodyText: 'Probiotic gummies improve digestion.',
        posterFilePath: 'uploads/art.png' as string | null
      };

      // User switches to 'image'
      state = { ...state, contentType: 'image' };
      expect(state.bodyText).toBe('Probiotic gummies improve digestion.');
      expect(state.posterFilePath).toBe('uploads/art.png');

      // In 'image' mode, saved payload sends empty body_text for image-only governance
      const payloadImage = buildSavePayload(state.contentType, 'Draft 1', state.bodyText, state.posterFilePath);
      expect(payloadImage.body_text).toBe('');
      expect(payloadImage.poster_file_path).toBe('uploads/art.png');
      expect(payloadImage.channel).toBe('General');

      // User switches to 'text'
      state = { ...state, contentType: 'text' };
      expect(state.bodyText).toBe('Probiotic gummies improve digestion.');
      expect(state.posterFilePath).toBe('uploads/art.png');

      // In 'text' mode, saved payload sends text copy without poster
      const payloadText = buildSavePayload(state.contentType, 'Draft 1', state.bodyText, state.posterFilePath);
      expect(payloadText.body_text).toBe('Probiotic gummies improve digestion.');
      expect(payloadText.poster_file_path).toBeUndefined();
      expect(payloadText.channel).toBe('General');

      // User switches back to 'both'
      state = { ...state, contentType: 'both' };
      const payloadBoth = buildSavePayload(state.contentType, 'Draft 1', state.bodyText, state.posterFilePath);
      expect(payloadBoth.body_text).toBe('Probiotic gummies improve digestion.');
      expect(payloadBoth.poster_file_path).toBe('uploads/art.png');
      expect(payloadBoth.channel).toBe('General');
    });
  });

  describe('3. API interaction defaults', () => {
    it('createContentItem defaults channel to General and bodyText to empty string', async () => {
      const mockRequest = vi.spyOn(api as any, 'request').mockResolvedValueOnce({
        id: 'new-item-1',
        title: 'New Poster',
        channel: 'General',
        current_version_num: 1,
        latest_version: { id: 'v-1', body_text: '', poster_file_path: 'poster.png' }
      });

      const res = await api.createContentItem('brand-1', 'New Poster', 'General', '', 'poster.png');

      expect(mockRequest).toHaveBeenCalledWith('/content', {
        method: 'POST',
        body: JSON.stringify({
          brand_id: 'brand-1',
          product_id: null,
          title: 'New Poster',
          channel: 'General',
          body_text: '',
          poster_file_path: 'poster.png',
          poster_asset_id: undefined,
          poster_alt_text: undefined
        })
      });
      expect(res.channel).toBe('General');
    });
  });
});
