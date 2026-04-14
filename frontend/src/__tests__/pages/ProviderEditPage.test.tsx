import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { App as AntApp } from 'antd';

// Mock 服务
const mockGet = vi.fn();
const mockListModels = vi.fn();
vi.mock('../../services/providerService', () => ({
  providerService: {
    get: (...args: unknown[]) => mockGet(...args),
    create: vi.fn(),
    update: vi.fn(),
    listModels: (...args: unknown[]) => mockListModels(...args),
    createModel: vi.fn(),
    updateModel: vi.fn(),
    deleteModel: vi.fn(),
    testConnection: vi.fn(),
  },
  PROVIDER_TYPES: ['openai', 'azure', 'anthropic', 'openai_compatible', 'custom'],
  PROVIDER_BASE_URLS: {
    openai: 'https://api.openai.com/v1',
    azure: '',
    anthropic: 'https://api.anthropic.com/v1',
    openai_compatible: '',
    custom: '',
  },
  PROVIDER_TYPE_LABELS: {
    openai: 'OpenAI',
    azure: 'Azure OpenAI',
    anthropic: 'Anthropic',
    openai_compatible: 'OpenAI Compatible',
    custom: '自定义',
  },
  AUTH_TYPES: ['api_key', 'oauth'],
}));

import ProviderEditPage from '../../pages/providers/ProviderEditPage';

function renderWithRouter(id?: string) {
  const path = id ? `/providers/${id}/edit` : '/providers/new';
  return render(
    <AntApp>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/providers/new" element={<ProviderEditPage />} />
          <Route path="/providers/:id/edit" element={<ProviderEditPage />} />
        </Routes>
      </MemoryRouter>
    </AntApp>
  );
}

describe('ProviderEditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({
      id: 'p1',
      name: 'OpenAI',
      provider_type: 'openai',
      base_url: 'https://api.openai.com/v1',
      auth_type: 'api_key',
      rate_limit_rpm: null,
      rate_limit_tpm: null,
    });
    mockListModels.mockResolvedValue({ data: [], total: 0 });
  });

  it('新建模式渲染注册标题', () => {
    const { container } = renderWithRouter();
    expect(container.textContent).toContain('注册新 Provider');
  });

  it('新建模式包含返回按钮', () => {
    const { container } = renderWithRouter();
    expect(container.textContent).toContain('返回列表');
  });

  it('新建模式包含表单字段', () => {
    const { container } = renderWithRouter();
    expect(container.textContent).toContain('名称');
    expect(container.textContent).toContain('厂商类型');
    expect(container.textContent).toContain('Base URL');
  });

  it('编辑模式渲染编辑标题', async () => {
    renderWithRouter('p1');
    await waitFor(() => {
      expect(document.body.textContent).toContain('编辑 Provider');
    });
  });

  it('编辑模式调用 get 接口', async () => {
    renderWithRouter('p1');
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('p1');
    });
  });

  it('编辑模式显示关联模型 Tab', async () => {
    renderWithRouter('p1');
    await waitFor(() => {
      expect(document.body.textContent).toContain('关联模型');
    });
  });

  it('编辑模式加载关联模型列表', async () => {
    renderWithRouter('p1');
    await waitFor(() => {
      expect(mockListModels).toHaveBeenCalledWith('p1');
    });
  });

  it('新建模式不显示关联模型 Tab', () => {
    const { container } = renderWithRouter();
    expect(container.textContent).not.toContain('关联模型');
  });

  it('编辑模式显示基本配置和关联模型两个 Tab', async () => {
    renderWithRouter('p1');
    await waitFor(() => {
      expect(document.body.textContent).toContain('基本配置');
      expect(document.body.textContent).toContain('关联模型');
    });
  });
});
