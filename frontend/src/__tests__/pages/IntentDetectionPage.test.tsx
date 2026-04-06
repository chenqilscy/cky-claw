import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IntentDetectionPage from '../../pages/intent/IntentDetectionPage';

vi.mock('../../services/intentService', () => ({
  intentService: {
    detect: vi.fn(),
  },
}));

import { intentService } from '../../services/intentService';

const MOCK_RESULT = {
  original_keywords: ['python', 'sort', 'algo'],
  current_keywords: ['weather', 'beijing'],
  drift_score: 0.85,
  is_drifted: true,
  threshold: 0.6,
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <IntentDetectionPage />
    </MemoryRouter>,
  );

describe('IntentDetectionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders page title', () => {
    const { container } = renderPage();
    expect(container.textContent).toContain('意图飘移检测');
  });

  it('renders form labels', () => {
    const { container } = renderPage();
    expect(container.textContent).toContain('原始意图');
    expect(container.textContent).toContain('当前消息');
  });

  it('renders detect button', () => {
    renderPage();
    const btn = screen.getByRole('button', { name: /检测飘移/ });
    expect(btn).toBeTruthy();
  });

  it('calls detect API and shows drifted result', async () => {
    vi.mocked(intentService.detect).mockResolvedValue(MOCK_RESULT);
    const { container } = renderPage();

    const textareas = container.querySelectorAll('textarea');
    fireEvent.change(textareas[0]!, { target: { value: 'test original' } });
    fireEvent.change(textareas[1]!, { target: { value: 'test current' } });

    fireEvent.click(screen.getByRole('button', { name: /检测飘移/ }));

    await waitFor(() => {
      expect(intentService.detect).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(container.textContent).toContain('已飘移');
    });
  });

  it('shows not-drifted result', async () => {
    vi.mocked(intentService.detect).mockResolvedValue({
      ...MOCK_RESULT,
      drift_score: 0.2,
      is_drifted: false,
    });
    const { container } = renderPage();

    const textareas = container.querySelectorAll('textarea');
    fireEvent.change(textareas[0]!, { target: { value: 'a' } });
    fireEvent.change(textareas[1]!, { target: { value: 'b' } });

    fireEvent.click(screen.getByRole('button', { name: /检测飘移/ }));

    await waitFor(() => {
      expect(container.textContent).toContain('未飘移');
    });
  });

  it('displays keyword tags', async () => {
    vi.mocked(intentService.detect).mockResolvedValue(MOCK_RESULT);
    const { container } = renderPage();

    const textareas = container.querySelectorAll('textarea');
    fireEvent.change(textareas[0]!, { target: { value: 'x' } });
    fireEvent.change(textareas[1]!, { target: { value: 'y' } });

    fireEvent.click(screen.getByRole('button', { name: /检测飘移/ }));

    await waitFor(() => {
      expect(container.textContent).toContain('python');
      expect(container.textContent).toContain('weather');
    });
  });
});
