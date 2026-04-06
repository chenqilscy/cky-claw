import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/* ---------- mock costRouterService ---------- */
const mockClassify = vi.fn();
const mockRecommend = vi.fn();
vi.mock('../../services/costRouterService', () => ({
  costRouterService: {
    classify: (...args: unknown[]) => mockClassify(...args),
    recommend: (...args: unknown[]) => mockRecommend(...args),
  },
}));

import CostRouterPage from '../../pages/cost-router/CostRouterPage';

const MOCK_CLASSIFY = { tier: 'moderate', text_length: 42 };
const MOCK_RECOMMEND = { tier: 'moderate', provider_name: 'openai-gpt4', provider_tier: 'complex' };
const MOCK_RECOMMEND_EMPTY = { tier: 'simple', provider_name: null, provider_tier: null };

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CostRouterPage />
    </QueryClientProvider>,
  );
}

describe('CostRouterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockClassify.mockResolvedValue(MOCK_CLASSIFY);
    mockRecommend.mockResolvedValue(MOCK_RECOMMEND);
  });

  it('渲染页面标题', () => {
    const { container } = renderPage();
    const text = container.textContent ?? '';
    expect(text).toContain('成本路由测试器');
  });

  it('渲染层级说明卡片', () => {
    const { container } = renderPage();
    const text = container.textContent ?? '';
    expect(text).toContain('层级说明');
    expect(text).toContain('简单');
    expect(text).toContain('中等');
    expect(text).toContain('复杂');
    expect(text).toContain('推理');
    expect(text).toContain('多模态');
  });

  it('空输入时分析按钮禁用', () => {
    const { container } = renderPage();
    const btn = container.querySelector('button');
    expect(btn).toBeTruthy();
    expect(btn!.disabled).toBe(true);
  });

  it('输入文本后点击分析按钮调用 classify 和 recommend', async () => {
    const { container } = renderPage();
    const textarea = container.querySelector('textarea')!;

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '帮我写一段代码' } });
    });

    const btn = container.querySelector('button')!;
    expect(btn.disabled).toBe(false);

    await act(async () => {
      fireEvent.click(btn);
    });

    expect(mockClassify).toHaveBeenCalledWith({ text: '帮我写一段代码' });
    expect(mockRecommend).toHaveBeenCalledWith({ text: '帮我写一段代码' }, undefined);
  });

  it('显示分类结果', async () => {
    const { container } = renderPage();
    const textarea = container.querySelector('textarea')!;

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '测试文本' } });
    });
    await act(async () => {
      fireEvent.click(container.querySelector('button')!);
    });

    // 等待 mutation 完成
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const text = container.textContent ?? '';
    expect(text).toContain('分类结果');
    expect(text).toContain('中等');
    expect(text).toContain('42');
  });

  it('显示 Provider 推荐', async () => {
    const { container } = renderPage();
    const textarea = container.querySelector('textarea')!;

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '测试文本' } });
    });
    await act(async () => {
      fireEvent.click(container.querySelector('button')!);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const text = container.textContent ?? '';
    expect(text).toContain('Provider 推荐');
    expect(text).toContain('openai-gpt4');
  });

  it('无匹配 Provider 时显示警告', async () => {
    mockRecommend.mockResolvedValueOnce(MOCK_RECOMMEND_EMPTY);
    const { container } = renderPage();
    const textarea = container.querySelector('textarea')!;

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '你好' } });
    });
    await act(async () => {
      fireEvent.click(container.querySelector('button')!);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const text = container.textContent ?? '';
    expect(text).toContain('无匹配 Provider');
  });

  it('classify 失败时显示错误提示', async () => {
    mockClassify.mockRejectedValueOnce(new Error('network error'));
    const { container } = renderPage();
    const textarea = container.querySelector('textarea')!;

    await act(async () => {
      fireEvent.change(textarea, { target: { value: '出错测试' } });
    });
    await act(async () => {
      fireEvent.click(container.querySelector('button')!);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const text = container.textContent ?? '';
    expect(text).toContain('分类失败');
  });
});
