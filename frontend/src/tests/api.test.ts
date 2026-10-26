import { describe, it, expect, beforeEach } from 'vitest';
import { api } from '../services/api';

describe('ApiService', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores and clears authentication tokens in local storage', () => {
    api.setAuth('test-jwt-token-123', 'org-456');
    expect(localStorage.getItem('inkloom_token')).toBe('test-jwt-token-123');
    expect(localStorage.getItem('inkloom_org_id')).toBe('org-456');

    api.setAuth(null, null);
    expect(localStorage.getItem('inkloom_token')).toBeNull();
    expect(localStorage.getItem('inkloom_org_id')).toBeNull();
  });
});
