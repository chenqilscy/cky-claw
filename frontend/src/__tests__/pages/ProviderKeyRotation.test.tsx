import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, fireEvent } from '@testing-library/react';

/* ---------- mock providerService ---------- */
const mockList = vi.fn();
const mockDelete = vi.fn();
const mockToggle = vi.fn();
const mockTestConn = vi.fn();
const mockRotateKey = vi.fn();
vi.mock('../../services/providerService', () => ({
  providerService: {
    list: (...args: unknown[]) => mockList(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    toggle: (...args: unknown[]) => mockToggle(...args),
    testConnection: (...args: unknown[]) => mockTestConn(...args),
    rotateKey: (...args: unknown[]) => mockRotateKey(...args),
  },
  PROVIDER_TYPES: ['openai', 'custom'] as const,
  AUTH_TYPES: ['api_key'] as const,
}));

/* ---------- mock react-router ---------- */
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

import ProviderListPage from '../../pages/providers/ProviderListPage';

const MOCK_PROVIDER = {
  id: 'p1',
  name: 'Test Provider',
  provider_type: 'openai',
  base_url: 'https://api.openai.com',
  api_key_set: true,
  auth_type: 'api_key',
  auth_config: {},
  rate_limit_rpm: null,
  rate_limit_tpm: null,
  is_enabled: true,
  org_id: null,
  last_health_check: null,
  health_status: 'healthy',
  key_expires_at: '2025-01-01T00:00:00Z',
  key_last_rotated_at: '2024-06-01T00:00:00Z',
  key_expired: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-06-01T00:00:00Z',
};

const MOCK_PROVIDER_VALID = {
  ...MOCK_PROVIDER,
  id: 'p2',
  name: 'Valid Provider',
  key_expired: false,
  key_expires_at: '2099-12-31T00:00:00Z',
};

const MOCK_PROVIDER_NO_EXPIRY = {
  ...MOCK_PROVIDER,
  id: 'p3',
  name: 'No Expiry',
  key_expired: false,
  key_expires_at: null,
};

describe('ProviderListPage — 密钥轮换与到期', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ data: [MOCK_PROVIDER, MOCK_PROVIDER_VALID, MOCK_PROVIDER_NO_EXPIRY], total: 3, limit: 20, offset: 0 });
    mockRotateKey.mockResolvedValue(MOCK_PROVIDER);
    mockTestConn.mockResolvedValue({ success: true, latency_ms: 100, error: null, model_used: 'gpt-4' });
  });

  it('渲染密钥状态列', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ProviderListPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('密钥状态');
  });

  it('显示已过期标签', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ProviderListPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('已过期');
  });

  it('显示有效标签', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ProviderListPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('有效');
  });

  it('显示永久标签（无过期时间）', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ProviderListPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('永久');
  });

  it('渲染轮换按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ProviderListPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('轮换');
  });

  it('点击轮换按钮显示弹窗', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ProviderListPage />));
    });

    // 找到第一个轮换链接并点击
    const links = Array.from(container.querySelectorAll('a'));
    const rotateLink = links.find((a) => a.textContent?.includes('轮换'));
    expect(rotateLink).toBeTruthy();

    await act(async () => {
      fireEvent.click((rotateLink as HTMLElement));
    });

    // 等待弹窗渲染
    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });

    const bodyText = document.body.textContent ?? '';
    expect(bodyText).toContain('轮换密钥');
    expect(bodyText).toContain('新 API Key');
  });
});
