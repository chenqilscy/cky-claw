import { describe, it, expect } from 'vitest';
import {
  PROVIDER_TYPES,
  PROVIDER_BASE_URLS,
  PROVIDER_TYPE_LABELS,
} from '../services/providerService';

describe('providerService constants', () => {
  it('所有 PROVIDER_TYPES 都有对应的 PROVIDER_TYPE_LABELS', () => {
    for (const t of PROVIDER_TYPES) {
      expect(PROVIDER_TYPE_LABELS[t]).toBeTruthy();
    }
  });

  it('所有 PROVIDER_TYPES 都有对应的 PROVIDER_BASE_URLS 条目', () => {
    for (const t of PROVIDER_TYPES) {
      expect(t in PROVIDER_BASE_URLS).toBe(true);
    }
  });

  it('包含 openai_compatible 类型', () => {
    expect(PROVIDER_TYPES).toContain('openai_compatible');
    expect(PROVIDER_TYPE_LABELS.openai_compatible).toBe('OpenAI Compatible');
    expect(PROVIDER_BASE_URLS.openai_compatible).toBe('');
  });

  it('PROVIDER_TYPES 数组不重复', () => {
    const set = new Set(PROVIDER_TYPES);
    expect(set.size).toBe(PROVIDER_TYPES.length);
  });
});
