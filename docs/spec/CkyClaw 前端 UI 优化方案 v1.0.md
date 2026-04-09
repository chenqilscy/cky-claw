# CkyClaw 前端 UI 优化方案

> 版本：v1.0
> 日期：2026-04-09
> 分析范围：frontend/src/ 全部 45 个页面组件，12,019 行代码

---

## 一、当前评分

| 维度 | 评分 | 说明 |
|------|:----:|------|
| 组件复用 | 2/5 | 仅 2 个共享组件（ErrorBoundary + MarkdownRenderer），大量重复 |
| 响应式设计 | 1/5 | 零 CSS 文件、零媒体查询、全部固定像素宽度 |
| 无障碍 | 1/5 | 零 ARIA、零键盘导航、零焦点管理 |
| 状态管理 | 2/5 | 三种策略并存，2 个 Zustand store 是死代码 |
| 错误处理 | 3/5 | API 层扎实，页面层不一致，有静默吞错的 bug |
| 加载体验 | 3/5 | 有 Spin 和 ProTable loading，无骨架屏 |
| 设计一致性 | 2/5 | Ant Design 提供基线，其余全部不一致 |
| **综合** | **2/5** | 功能完整，但 UI 工程质量需要大幅提升 |

---

## 二、Top 10 问题清单

### 问题 1：零响应式设计（致命）

**现状**：45 个页面，0 个 CSS 文件，0 个媒体查询。所有宽度固定像素。

| 页面 | 问题 |
|------|------|
| Dashboard | `Col span={4}` 无响应式断点（xs/sm/md/lg） |
| Chat | 侧边栏固定 `width={280}`，小屏幕溢出 |
| Traces 详情弹窗 | 固定 `width={1100}`，笔记本直接溢出 |
| 所有表单 | 固定 `maxWidth: 800` 或 `width: 600` |

**优化方案**：

```tsx
// Before: 固定布局
<Row gutter={16}>
  <Col span={4}>统计卡片</Col>
  <Col span={14}>图表</Col>
</Row>

// After: 响应式布局
<Row gutter={[16, 16]}>
  <Col xs={24} sm={12} md={6} lg={4}>统计卡片</Col>
  <Col xs={24} lg={14}>图表</Col>
</Row>
```

Chat 页面侧边栏改为可折叠 Drawer（移动端）：

```tsx
// Before
<div style={{ width: 280 }}>
  <ChatSidebar />
</div>

// After
const isMobile = useResponsive().md === false;
{isMobile
  ? <Drawer open={sidebarOpen} onClose={() => setSidebarOpen(false)}><ChatSidebar /></Drawer>
  : <Sider width={280}><ChatSidebar /></Sider>
}
```

---

### 问题 2：颜色常量重复 5 次且值不一致（Bug）

**现状**：`SPAN_TYPE_COLORS` 在 5 个文件中定义，且 `tool` 的颜色值不同：

| 文件 | `tool` 颜色值 |
|------|:------------:|
| `FlameChart.tsx:6` | `#faad14`（不一致！） |
| `TracesPage.tsx:48` | `#fa8c16` |
| `SpanWaterfall.tsx:8` | `#fa8c16` |
| `TraceReplayTimeline.tsx:13` | `#fa8c16` |
| `DashboardPage.tsx:37` | `#fa8c16` |

同样的 `NODE_COLORS` 在 3 个文件中重复，`protocolLabel/protocolColor` 在 2 个文件中重复。

**优化方案**：抽取共享常量文件

```tsx
// src/constants/colors.ts
export const SPAN_TYPE_COLORS: Record<string, string> = {
  agent: '#1677ff',
  llm: '#722ed1',
  tool: '#fa8c16',
  guardrail: '#eb2f96',
  handoff: '#52c41a',
};

// src/constants/nodes.ts
export const NODE_COLORS = { ... };
```

---

### 问题 3：2 个 Zustand Store 是死代码

**现状**：
- `agentStore.ts`（97 行）— AgentListPage 用 TanStack Query，不走 store
- `sessionStore.ts`（83 行）— ChatSidebar 直接调 chatService，不走 store

180 行精心编写的 stale-while-revalidate 缓存逻辑完全无人使用。

**优化方案**：删除死 store，统一用 TanStack Query。如果未来需要全局缓存，TanStack Query 的 `staleTime` + `gcTime` 已覆盖此需求。

---

### 问题 4：三种数据获取策略并存（架构问题）

**现状**：

| 策略 | 使用页面 | 问题 |
|------|---------|------|
| `useState + useEffect` | ~30 个页面 | 无缓存、无自动重试、重复代码 |
| TanStack Query | ~6 个页面 | 有缓存、有重试、但覆盖率太低 |
| Zustand Store | 2 个页面（实际 0） | 死代码 |

**优化方案**：全面切换到 TanStack Query

```tsx
// Before: 手动管理（30+ 页面的模式）
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);
const fetchData = useCallback(async () => {
  setLoading(true);
  try {
    const res = await xxxService.list();
    setData(res.items);
  } catch (e) {
    message.error('获取失败');
  } finally {
    setLoading(false);
  }
}, []);
useEffect(() => { fetchData(); }, [fetchData]);

// After: TanStack Query（一行搞定）
const { data = [], isLoading } = useQuery({
  queryKey: ['guardrails'],
  queryFn: () => guardrailService.list(),
});
```

为每个 Service 模块生成标准 Query hooks：

```tsx
// src/hooks/useGuardrailQueries.ts
export function useGuardrailList() {
  return useQuery({ queryKey: ['guardrails'], queryFn: guardrailService.list });
}
export function useGuardrailCreate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: guardrailService.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['guardrails'] }),
  });
}
```

---

### 问题 5：AntD v5 message API 混用（兼容性 Bug）

**现状**：6 个文件仍用已废弃的静态 API：

| 文件 | 导入方式 |
|------|---------|
| `AgentVersionPage.tsx:3` | `import { message } from 'antd'` |
| `GuardrailRulesPage.tsx:9` | 同上 |
| `TracesPage.tsx:3` | 同上 |
| `TeamPage.tsx:3` | 同上 |
| `WorkflowPage.tsx:3` | 同上 |
| `ProviderListPage.tsx:3` | 同上 |

**优化方案**：全部改为 `App.useApp()`，或抽取共享 hook：

```tsx
// src/hooks/useMessage.ts
export function useMessage() {
  const { message } = App.useApp();
  return message;
}

// 每个页面统一使用
const { message } = App.useApp();
// 或
const message = useMessage();
```

---

### 问题 6：Chat 页面硬编码颜色破坏暗色模式（Bug）

**现状**：`ChatWindow.tsx` 用内联样式硬编码颜色：

```tsx
// 硬编码，暗色模式下白底黑字
background: msg.role === 'user' ? '#1677ff' : '#fff',
color: msg.role === 'user' ? '#fff' : '#000',
```

**优化方案**：用 Ant Design token 替代硬编码颜色

```tsx
// After: 使用 theme token
const ChatBubble = styled('div', ({ theme }) => ({
  background: msg.role === 'user'
    ? theme.colorPrimary
    : theme.colorBgContainer,
  color: msg.role === 'user'
    ? theme.colorTextLightSolid
    : theme.colorText,
}));
```

或用 CSS 变量：

```css
/* 暗色模式自动适配 */
.chat-bubble--user {
  background: var(--ant-color-primary);
  color: var(--ant-color-text-light-solid);
}
.chat-bubble--assistant {
  background: var(--ant-color-bg-container);
  color: var(--ant-color-text);
}
```

---

### 问题 7：AgentEditPage 静默吞错

**现状**：4 个下拉数据加载全部 `catch(() => { /* ignore */ })`：

```tsx
// AgentEditPage.tsx:54, 65, 76, 85
guardrailService.list().then(...).catch(() => { /* ignore */ });
toolGroupService.list().then(...).catch(() => { /* ignore */ });
agentService.list().then(...).catch(() => { /* ignore */ });
providerService.list().then(...).catch(() => { /* ignore */ });
```

如果任何一个 API 失败，用户看到空下拉框，不知道为什么。

**优化方案**：

```tsx
// 用 TanStack Query 自动处理
const { data: guardrails = [] } = useQuery({
  queryKey: ['guardrails'],
  queryFn: guardrailService.list,
});
// 加载失败自动重试，UI 可展示 error 状态
```

---

### 问题 8：20+ 个 CRUD 页面重复同一模式

**现状**：每个列表页重复写 `useState` + `useEffect` + `fetchData` + 列定义 + ProTable + Modal，平均每个 250-350 行。估计重复代码 2000-3000 行。

**优化方案**：抽取通用 CRUD 基础设施

```tsx
// src/components/CrudTable.tsx
interface CrudTableProps<T> {
  queryKey: string;
  listFn: () => Promise<{ items: T[]; total: number }>;
  createFn: (data: T) => Promise<T>;
  updateFn: (id: string, data: T) => Promise<T>;
  deleteFn: (id: string) => Promise<void>;
  columns: ColumnsType<T>;
  form: React.ReactNode;
}

export function CrudTable<T extends { id: string }>(props: CrudTableProps<T>) {
  // 内部处理: 列表查询 / 创建弹窗 / 编辑弹窗 / 删除确认 / 错误提示
}
```

使用后每个 CRUD 页面从 300 行缩减到 ~80 行（只写列定义 + 表单字段）。

---

### 问题 9：零共享 UI 组件

**现状**：`components/` 目录只有 2 个文件。以下高频 UI 模式在每个页面中各自实现：

| 缺失组件 | 使用场景 |
|---------|---------|
| `StatusTag` | Agent 状态、Provider 状态、Session 状态 — 每个页面各自写 Tag color 映射 |
| `ConfirmDeleteButton` | 删除操作 — 每个页面各自写 Popconfirm |
| `PageHeader` | 页面标题 + 操作按钮 — 每个页面各自写 Flex justify |
| `DateTimeDisplay` | 时间展示 — 22 个文件各自 `new Date(x).toLocaleString()` |
| `EmptyState` | 空数据 — 各自写空判断 + 提示文案 |
| `SearchInput` | 搜索框 — 各自写 Input + onChange debounce |

**优化方案**：建立共享组件库

```
src/components/
├── CrudTable.tsx          # 通用 CRUD 表格
├── StatusTag.tsx          # 状态标签（统一颜色映射）
├── ConfirmDeleteButton.tsx # 删除确认按钮
├── PageHeader.tsx         # 页面标题栏
├── DateTimeDisplay.tsx    # 统一时间格式化
├── EmptyState.tsx         # 空数据占位
├── SearchInput.tsx        # 防抖搜索输入
├── ErrorBoundary.tsx      # 已有
└── MarkdownRenderer.tsx   # 已有
```

---

### 问题 10：零无障碍支持

**现状**：
- 0 个 `aria-*` 属性
- 0 个键盘导航（仅 Chat 有 Enter 发送）
- 0 个焦点管理
- 状态信息仅通过颜色传达（`<Tag color="red">`）
- Chat 侧边栏列表项有 `onClick` 无 `onKeyDown`

**优化方案**：针对核心页面（Chat、Agent 管理）做最小无障碍支持

```tsx
// 1. 状态标签添加文字说明（不仅是颜色）
<Tag color="green" role="status" aria-label="状态: 运行中">
  运行中
</Tag>

// 2. 列表项添加键盘支持
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyDown={(e) => e.key === 'Enter' && handleClick()}
>
  {item.name}
</div>

// 3. 弹窗自动聚焦到第一个输入
<Modal open={open} afterOpenChange={(v) => v && form.getFieldInstance('name')?.focus()}>
```

---

## 三、优化优先级与实施计划

### P0：立即修复（1-2 周）— Bug 级问题

| 任务 | 工作量 | 收益 |
|------|:------:|------|
| 抽取 `constants/colors.ts`，统一颜色映射 | 2h | 修复 FlameChart 颜色不一致 bug |
| Chat 页面颜色改为 theme token | 4h | 修复暗色模式 bug |
| 6 个文件 message API 改为 `App.useApp()` | 1h | 修复 AntD v5 兼容性 |
| AgentEditPage 4 个吞错改为正确错误处理 | 1h | 修复关键表单静默失败 |
| 删除 `agentStore` 和 `sessionStore` 死代码 | 0.5h | 代码清洁 |

### P1：架构统一（2-3 周）— 重复代码清理

| 任务 | 工作量 | 收益 |
|------|:------:|------|
| 全部页面切换到 TanStack Query | 3d | 统一数据获取 + 自动缓存 + 重试 |
| 抽取 `src/components/` 共享组件（StatusTag、PageHeader 等 6 个） | 3d | 减少重复代码 ~1000 行 |
| 抽取 `CrudTable` 通用组件 | 2d | 20+ 个页面各减 200 行 |
| 各 Service 模块生成标准 Query hooks | 2d | 标准化数据层 |

### P2：体验提升（2-3 周）— 面向用户的改进

| 任务 | 工作量 | 收益 |
|------|:------:|------|
| 核心页面响应式适配（Chat、Dashboard、Agent 管理） | 5d | 支持平板和手机访问 |
| 骨架屏替换 Spin（Dashboard、列表页） | 2d | 消除布局跳动，感知更流畅 |
| 暗色模式全面适配（消除所有硬编码颜色） | 3d | 暗色模式真正可用 |
| 路由规范统一（要么全用 URL 参数，要么全用 Query 参数） | 1d | URL 可分享、可收藏 |

### P3：精细打磨（2-3 周）— 高级体验

| 任务 | 工作量 | 收益 |
|------|:------:|------|
| 核心 CRUD 页面重构为 `CrudTable` 模式 | 5d | 代码量减少 50%+，维护性大幅提升 |
| 拆分大组件（TracesPage 634 行 → 3-4 个子模块） | 2d | 可读性和可维护性提升 |
| 核心页面无障碍支持 | 3d | 键盘可操作、屏幕阅读器可访问 |
| 统一错误边界（每个路由独立 ErrorBoundary） | 1d | 单页崩溃不影响全局 |

---

## 四、关键页面优化设计

### 4.1 Chat 页面（最重要的用户页面）

**当前问题**：
- 固定 280px 侧边栏
- 硬编码颜色破坏暗色模式
- 无键盘快捷键
- 消息气泡样式单调

**目标设计**：

```
┌──────────────────────────────────────────────────┐
│  ◀  CkyClaw Chat                🌙 暗色  ⚙ 设置  │
├────────────┬─────────────────────────────────────┤
│ 🔍 搜索    │  🤖 Code Reviewer                   │
│            │  ┌─────────────────────────────────┐│
│ ▸ 今天     │  │ 你好，我来帮你审查代码。        ││
│   Agent A  │  │ 请提交需要审查的代码片段。       ││
│   Agent B  │  └─────────────────────────────────┘│
│            │  ┌─────────────────────────────────┐│
│ ▸ 昨天     │  │ 发送代码：def hello(): pass     ││
│   Agent C  │  └─────────────────────────────────┘│
│            │                                      │
│            │  ┌─────────────────────────────────┐│
│            │  │ 审查结果：                       ││
│            │  │ 1. 缺少 docstring               ││
│            │  │ 2. 建议添加类型注解              ││
│            │  └─────────────────────────────────┘│
│            │                                      │
│            │  ┌──────────────────────────┐ 📎   │
│            │  │ 输入消息... (Enter 发送)  │  ⬆   │
│            │  └──────────────────────────┘       │
└────────────┴─────────────────────────────────────┘
```

**改进点**：
- 侧边栏可折叠（移动端变为 Drawer）
- 消息气泡使用 theme token（暗色模式适配）
- 支持文件附件（📎 按钮）
- 支持 Markdown 实时预览
- Enter 发送 / Shift+Enter 换行
- 会话分组（今天/昨天/更早）

### 4.2 Dashboard 页面

**当前问题**：
- 统计卡片无响应式
- 图表区域固定比例
- 数据加载无骨架屏

**目标设计**：

```
┌──────────────────────────────────────────────────────┐
│  Dashboard                              🔄 自动刷新  │
├──────────┬──────────┬──────────┬──────────────────────┤
│ Agent    │ 运行中   │ 今日     │ 待审批               │
│   24     │   3      │ Token    │    5                 │
│ ▲ +2     │ ● 绿     │ 12.5K    │ ⚠ 黄                │
├──────────┴──────────┴──────────┴──────────────────────┤
│                                                       │
│  ┌─── Token 使用趋势 ──────────────────────────────┐  │
│  │  📊 ECharts（自适应宽度）                        │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─── Agent 活跃排名 ──┐  ┌─── Guardrail 触发 ────┐  │
│  │ 1. code-reviewer    │  │ ⚡ 规则: 5            │  │
│  │ 2. data-analyst     │  │ ✅ 通过: 89%          │  │
│  │ 3. devops-agent     │  │ 🛑 拦截: 11%          │  │
│  └─────────────────────┘  └────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

**改进点**：
- 统计卡片 `xs={12} sm={12} md={6}` 响应式
- 骨架屏加载替代 Spin
- 图表自适应宽度（`useResizeDetector`）
- 自动刷新开关

### 4.3 Agent 管理页面

**当前问题**：
- 列表和编辑分离
- 表单下拉框静默失败
- Handoff 编排器独立页面

**目标设计**：

```
┌──────────────────────────────────────────────────────┐
│  Agent 管理        [+ 新建] [📋 从模板] [📤 导入]    │
├──────────────────────────────────────────────────────┤
│ 🔍 搜索  │ Provider: [全部 ▾] │ 状态: [全部 ▾]      │
├──────────────────────────────────────────────────────┤
│  ✅ code-reviewer    运行中  GPT-4o  │ [编辑] [⋮]   │
│  ✅ data-analyst     运行中  通义    │ [编辑] [⋮]   │
│  ⏸ devops-agent     已停用  DeepSeek │ [编辑] [⋮]   │
│  ✅ complaint-bot    运行中  文心    │ [编辑] [⋮]   │
└──────────────────────────────────────────────────────┘
```

**改进点**：
- 统一筛选栏（搜索 + Provider + 状态）
- 操作按钮聚合到「⋮」菜单
- 行内快速启用/停用 Toggle
- 编辑页改为抽屉（Drawer），减少页面跳转

---

## 五、设计系统规范建议

### 5.1 间距规范

```tsx
// 统一使用 Ant Design token 的间距
const { token } = theme.useToken();

// 页面内边距
padding: token.paddingLG,        // 24px

// 卡片间距
gap: token.padding,               // 16px

// 元素间距
marginBottom: token.marginSM,     // 8px
```

### 5.2 颜色规范

```tsx
// src/constants/colors.ts — 统一管理所有业务颜色

// Span 类型颜色
export const SPAN_TYPE_COLORS = { ... };

// 状态颜色（统一，不再每个页面各自定义）
export const STATUS_COLOR_MAP = {
  active: 'green',
  inactive: 'default',
  running: 'blue',
  error: 'red',
  pending: 'orange',
} as const;

// 使用 Ant Design token 做主题适配
// 禁止在代码中出现硬编码的 hex 颜色值
```

### 5.3 组件规范

| 规则 | 说明 |
|------|------|
| 禁止内联 `style={{}}` | 用 CSS Modules 或 styled-components |
| 禁止硬编码颜色 | 用 `theme.useToken()` 或 CSS 变量 |
| 统一数据获取 | 全部用 TanStack Query |
| 统一消息提示 | 全部用 `App.useApp()` 的 `message` |
| 列表页用 `CrudTable` | 只写列定义 + 表单字段 |
| 每个路由加 `ErrorBoundary` | 防止单页崩溃影响全局 |

---

## 六、总结

当前前端是"功能堆叠型"产品——38 个页面、161 个 API 端点全接通了，但 UI 层没有经过架构设计，属于逐功能迭代的结果。

**最大的三个问题**：
1. **重复代码太多** — 20+ 个 CRUD 页面各自手写数据获取 + 列定义 + 弹窗，可缩减 50% 代码量
2. **暗色模式不可用** — Chat 等核心页面硬编码颜色，theme token 形同虚设
3. **零响应式** — 所有布局固定像素，平板/手机完全不可用

**最高 ROI 的优化**：先做 P0（修 bug，1-2 天），再做 P1（统一架构 + 抽组件，2 周），这两步完成后代码量减少 ~3000 行，后续新增页面开发效率提升 3-5x。
