import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import EventReplayTimeline from '../../pages/traces/EventReplayTimeline';
import type { EventItem } from '../../services/eventService';

function makeEvent(overrides: Partial<EventItem> = {}): EventItem {
  return {
    event_id: 'e1',
    sequence: 1,
    event_type: 'run_start',
    run_id: 'run-001',
    session_id: null,
    agent_name: 'bot',
    span_id: null,
    timestamp: '2026-01-01T00:00:00Z',
    payload: null,
    ...overrides,
  };
}

describe('EventReplayTimeline', () => {
  it('空事件显示空状态', () => {
    render(<EventReplayTimeline events={[]} />);
    expect(screen.getByText('暂无事件数据')).toBeTruthy();
  });

  it('渲染事件列表', () => {
    const events: EventItem[] = [
      makeEvent({ event_id: 'e1', sequence: 1, event_type: 'run_start' }),
      makeEvent({ event_id: 'e2', sequence: 2, event_type: 'agent_start', timestamp: '2026-01-01T00:00:01Z' }),
      makeEvent({ event_id: 'e3', sequence: 3, event_type: 'run_end', timestamp: '2026-01-01T00:00:02Z' }),
    ];
    render(<EventReplayTimeline events={events} />);
    expect(screen.getByText('0 / 3 步')).toBeTruthy();
    expect(screen.getByText('播放')).toBeTruthy();
  });

  it('点击播放按钮', () => {
    vi.useFakeTimers();
    const events: EventItem[] = [
      makeEvent({ event_id: 'e1', sequence: 1 }),
      makeEvent({ event_id: 'e2', sequence: 2, timestamp: '2026-01-01T00:00:01Z' }),
    ];
    render(<EventReplayTimeline events={events} />);

    const playBtn = screen.getByText('播放');
    fireEvent.click(playBtn);
    // 播放后按钮文本切换
    expect(screen.getByText('暂停')).toBeTruthy();

    vi.useRealTimers();
  });

  it('点击单步前进', () => {
    const events: EventItem[] = [
      makeEvent({ event_id: 'e1', sequence: 1 }),
      makeEvent({ event_id: 'e2', sequence: 2, timestamp: '2026-01-01T00:00:01Z' }),
    ];
    render(<EventReplayTimeline events={events} />);

    // 后退按钮初始禁用
    const backBtn = screen.getAllByRole('button')[0];
    expect(backBtn).toHaveProperty('disabled', true);

    // 前进
    const fwdBtn = screen.getAllByRole('button')[2]!;
    fireEvent.click(fwdBtn);
    expect(screen.getByText('1 / 2 步')).toBeTruthy();
  });

  it('显示事件类型 Tag', () => {
    const events: EventItem[] = [
      makeEvent({ event_id: 'e1', sequence: 1, event_type: 'llm_call_start' }),
    ];
    render(<EventReplayTimeline events={events} />);
    expect(screen.getByText('llm_call_start')).toBeTruthy();
  });

  it('按序列号排序', () => {
    const events: EventItem[] = [
      makeEvent({ event_id: 'e3', sequence: 3, event_type: 'run_end', timestamp: '2026-01-01T00:00:03Z' }),
      makeEvent({ event_id: 'e1', sequence: 1, event_type: 'run_start', timestamp: '2026-01-01T00:00:01Z' }),
      makeEvent({ event_id: 'e2', sequence: 2, event_type: 'agent_start', timestamp: '2026-01-01T00:00:02Z' }),
    ];
    render(<EventReplayTimeline events={events} />);
    // 即使乱序传入，组件也会按 sequence 排序
    const tags = screen.getAllByText(/run_start|agent_start|run_end/);
    expect(tags[0]!.textContent).toBe('run_start');
    expect(tags[1]!.textContent).toBe('agent_start');
    expect(tags[2]!.textContent).toBe('run_end');
  });
});
