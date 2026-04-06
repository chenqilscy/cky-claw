import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import NotFoundPage from '../../pages/NotFoundPage';

describe('NotFoundPage', () => {
  it('renders 404 text', () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('404')).toBeDefined();
    expect(screen.getByText('页面不存在')).toBeDefined();
  });

  it('renders back button', () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /返回首页/ })).toBeDefined();
  });
});
