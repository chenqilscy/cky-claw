import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { FlameNode } from '../../services/traceService';

/** Span 类型 → 颜色映射 */
const TYPE_COLORS: Record<string, string> = {
  agent: '#1677ff',
  llm: '#52c41a',
  tool: '#faad14',
  handoff: '#722ed1',
  guardrail: '#eb2f96',
};

interface FlatSpan {
  name: string;
  type: string;
  status: string;
  start: number;
  duration: number;
  depth: number;
  model: string | null;
}

/** 递归展平嵌套火焰树为扁平列表 */
function flattenTree(node: FlameNode, depth: number, baseTime: number): FlatSpan[] {
  const start = node.start_time ? new Date(node.start_time).getTime() - baseTime : 0;
  const duration = node.duration_ms ?? 0;
  const result: FlatSpan[] = [{
    name: node.name || node.type,
    type: node.type,
    status: node.status,
    start,
    duration,
    depth,
    model: node.model,
  }];
  for (const child of node.children) {
    result.push(...flattenTree(child, depth + 1, baseTime));
  }
  return result;
}

interface FlameChartProps {
  nodes: FlameNode | FlameNode[] | null;
  totalSpans: number;
}

/** Span 火焰图 — 基于 ECharts custom series */
export default function FlameChart({ nodes, totalSpans }: FlameChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || !nodes) return;

    // 统一为数组处理
    const rootNodes = Array.isArray(nodes) ? nodes : [nodes];
    if (rootNodes.length === 0) return;

    // 计算 baseTime
    const allStartTimes = rootNodes
      .filter((n) => n.start_time)
      .map((n) => new Date(n.start_time!).getTime());
    const baseTime = allStartTimes.length > 0 ? Math.min(...allStartTimes) : 0;

    // 展平
    const flatSpans: FlatSpan[] = [];
    for (const root of rootNodes) {
      flatSpans.push(...flattenTree(root, 0, baseTime));
    }

    const maxDepth = Math.max(...flatSpans.map((s) => s.depth), 0);
    const barHeight = 24;
    const chartHeight = Math.max((maxDepth + 2) * barHeight + 80, 200);

    const chart = echarts.init(chartRef.current);
    chartRef.current.style.height = `${chartHeight}px`;
    chart.resize();

    const option = {
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const p = params as { data: FlatSpan };
          const d = p.data;
          return `<b>${d.name}</b><br/>类型: ${d.type}<br/>耗时: ${d.duration}ms<br/>状态: ${d.status}${d.model ? `<br/>模型: ${d.model}` : ''}`;
        },
      },
      grid: { left: 10, right: 10, top: 30, bottom: 10, containLabel: false },
      xAxis: {
        type: 'value' as const,
        axisLabel: { formatter: (v: number) => `${v}ms` },
        name: '耗时（ms）',
      },
      yAxis: {
        type: 'value' as const,
        min: -0.5,
        max: maxDepth + 0.5,
        inverse: true,
        axisLabel: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
      series: [{
        type: 'custom' as const,
        renderItem: (_params: unknown, api: Record<string, (...args: unknown[]) => unknown>) => {
          const val = api['value'] as (i: number) => number;
          const coord = api['coord'] as (v: [number, number]) => [number, number];
          const size = api['size'] as (v: [number, number]) => [number, number];

          const start = val(0);
          const duration = val(1);
          const depth = val(2);
          const typeIdx = val(3);

          const xy = coord([start, depth]);
          const wh = size([duration, 0]);

          const types = Object.keys(TYPE_COLORS);
          const color = TYPE_COLORS[types[typeIdx] ?? 'agent'] ?? '#999';

          return {
            type: 'rect',
            shape: {
              x: xy[0],
              y: xy[1] - barHeight / 2,
              width: Math.max(wh[0], 2),
              height: barHeight - 2,
              r: 3,
            },
            style: { fill: color, opacity: 0.85 },
          };
        },
        encode: { x: [0, 1], y: 2 },
        data: flatSpans.map((s) => ({
          value: [s.start, s.duration, s.depth, Object.keys(TYPE_COLORS).indexOf(s.type)],
          ...s,
        })),
      }],
    };

    chart.setOption(option as echarts.EChartsOption);

    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart.dispose();
    };
  }, [nodes, totalSpans]);

  if (!nodes) {
    return <div style={{ color: '#999', padding: 16 }}>无 Span 数据</div>;
  }

  return <div ref={chartRef} style={{ width: '100%', minHeight: 200 }} />;
}
