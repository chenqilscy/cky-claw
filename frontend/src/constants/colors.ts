/**
 * 共享颜色常量 — 统一全平台颜色映射，消除跨文件重复。
 */

/** Span 类型颜色（HEX 值，用于图表/瀑布图/火焰图等需要精确色值的场景） */
export const SPAN_TYPE_COLORS: Record<string, string> = {
  agent: '#1677ff',
  llm: '#52c41a',
  tool: '#fa8c16',
  handoff: '#722ed1',
  guardrail: '#f5222d',
};

/** Span 类型颜色（Ant Design 颜色名，用于 Tag 组件等场景） */
export const SPAN_TYPE_TAG_COLORS: Record<string, string> = {
  agent: 'blue',
  llm: 'green',
  tool: 'orange',
  handoff: 'purple',
  guardrail: 'red',
};

/** Workflow 节点类型颜色 */
export const NODE_COLORS: Record<string, string> = {
  agent: '#1890ff',
  parallel: '#52c41a',
  conditional: '#fa8c16',
  loop: '#722ed1',
};

/** Workflow 步骤类型 Tag 颜色 */
export const STEP_TYPE_TAG_COLORS: Record<string, string> = {
  agent: 'blue',
  parallel: 'green',
  conditional: 'orange',
  loop: 'purple',
};

/** 团队协议标签 */
export const PROTOCOL_LABELS: Record<string, string> = {
  SEQUENTIAL: '顺序执行',
  PARALLEL: '并行执行',
  COORDINATOR: '协调者模式',
};

/** 团队协议颜色（HEX） */
export const PROTOCOL_COLORS: Record<string, string> = {
  SEQUENTIAL: '#1890ff',
  PARALLEL: '#52c41a',
  COORDINATOR: '#722ed1',
};

/** 团队协议 Tag 颜色 */
export const PROTOCOL_TAG_COLORS: Record<string, string> = {
  SEQUENTIAL: 'blue',
  PARALLEL: 'green',
  COORDINATOR: 'purple',
};
