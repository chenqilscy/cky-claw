import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { App } from 'antd';
import { PageContainer } from '../../components/PageContainer';

/** 包装 PageContainer 所需的 Router + AntD App 上下文 */
function renderPageContainer(
  props: React.ComponentProps<typeof PageContainer>,
  route = '/agents',
) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App>
        <PageContainer {...props} />
      </App>
    </MemoryRouter>,
  );
}

describe('PageContainer', () => {
  it('渲染标题', () => {
    renderPageContainer({ title: 'Agent 管理', children: <div /> }, '/dashboard');
    expect(screen.getByText('Agent 管理')).toBeTruthy();
  });

  it('渲染描述', () => {
    renderPageContainer({
      title: '测试',
      description: '这是一段描述文字',
      children: <div />,
    });
    expect(screen.getByText('这是一段描述文字')).toBeTruthy();
  });

  it('渲染图标', () => {
    renderPageContainer({
      title: '测试',
      icon: <span data-testid="custom-icon">🔧</span>,
      children: <div />,
    });
    expect(screen.getByTestId('custom-icon')).toBeTruthy();
  });

  it('渲染 extra 操作区', () => {
    renderPageContainer({
      title: '测试',
      extra: <button>新建</button>,
      children: <div />,
    });
    expect(screen.getByText('新建')).toBeTruthy();
  });

  it('渲染子内容', () => {
    renderPageContainer({
      title: '测试',
      children: <div data-testid="page-body">内容</div>,
    });
    expect(screen.getByTestId('page-body')).toBeTruthy();
  });

  it('自动生成面包屑', () => {
    renderPageContainer(
      { title: '测试', children: <div /> },
      '/agents',
    );
    expect(screen.getByText('首页')).toBeTruthy();
    expect(screen.getByText('Agent 管理')).toBeTruthy();
  });

  it('多层路径生成多级面包屑', () => {
    renderPageContainer(
      { title: '编辑 Agent', children: <div /> },
      '/agents/123/edit',
    );
    expect(screen.getByText('首页')).toBeTruthy();
    expect(screen.getAllByText('Agent 管理').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('编辑')).toBeTruthy();
  });

  it('hideBreadcrumb 隐藏面包屑', () => {
    renderPageContainer(
      { title: '测试', hideBreadcrumb: true, children: <div /> },
      '/agents',
    );
    expect(screen.queryByText('首页')).toBeNull();
  });

  it('未知路径段原样显示', () => {
    renderPageContainer(
      { title: '测试', children: <div /> },
      '/unknown-path',
    );
    expect(screen.getByText('unknown-path')).toBeTruthy();
  });
});
