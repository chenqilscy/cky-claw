# CkyClaw 成本路由测试器分析

> 版本：v1.0
> 日期：2026-04-15
> 状态：问题分析 + 修复方案

## 1. 功能概述

成本路由（Cost Router）是 CkyClaw 的智能模型选择系统，根据输入文本的复杂度自动推荐最合适的模型厂商（Provider）。

### 1.1 核心流程

```
用户输入文本 → 复杂度分类 → 层级匹配 → 推荐 Provider
```

### 1.2 模型层级（ModelTier）

| 层级 | 说明 | 分类依据 |
|------|------|----------|
| `simple` | 简单 | 短文本（≤50 字符）或简单问答 |
| `moderate` | 中等 | 一般对话、翻译等 |
| `complex` | 复杂 | 代码编写、系统设计、调试等 |
| `reasoning` | 推理 | 数学计算、逻辑推理、算法设计 |
| `multimodal` | 多模态 | 图片、视觉、音频相关 |

分类优先级：`multimodal` > `reasoning` > `complex` > `moderate` > `simple`

### 1.3 推荐策略

1. **精确匹配**：找与目标层级相同的 Provider
2. **向上升级**：无精确匹配时，选层级更高的 Provider
3. **降级兜底**：所有候选均低于目标时，选最高层级的

---

## 2. Provider 与成本路由的关联方式

### 2.1 数据模型

Provider 通过以下两个字段参与成本路由：

```python
class ProviderConfig(Base):
    model_tier: str    # 层级: simple / moderate / complex / reasoning / multimodal
                       # 默认值: 'moderate'
    capabilities: list  # 能力标签: text / code / vision / reasoning / function_calling
                       # 默认值: []
    is_enabled: bool   # 启用状态（只有启用的 Provider 参与路由）
```

### 2.2 候选筛选流程

```
1. SELECT * FROM provider_configs WHERE is_enabled=True AND is_deleted=False
2. 过滤 model_tier 无效值（非枚举成员的跳过）
3. 如果指定了 required_capabilities → 按能力子集过滤
4. 按层级匹配策略选择最优 Provider
```

---

## 3. 问题分析："无匹配 Provider"

### 3.1 问题现象

在成本路由测试器页面，用户输入文本点击分析后，即使系统中已有多个启用的 Provider，仍提示：

> ⚠️ 无匹配 Provider。当前没有启用的 Provider 满足此层级需求。请到「模型厂商」页面添加并启用 Provider。

### 3.2 根本原因

**ProviderEditPage 前端表单缺少 `model_tier` 和 `capabilities` 两个关键字段。**

| 字段 | 后端 Schema 支持 | ORM 模型支持 | 前端表单 | 结果 |
|------|:----------------:|:------------:|:--------:|------|
| `model_tier` | ✅ ProviderCreate 有 | ✅ 有默认值 `moderate` | ❌ **缺失** | 所有 Provider 都是 `moderate` |
| `capabilities` | ✅ ProviderCreate 有 | ✅ 有默认值 `[]` | ❌ **缺失** | 所有 Provider 能力为空 |

**具体场景**：

当用户在成本路由页面选择了能力筛选（如"视觉"）：

```python
required_capabilities = ["vision"]
provider.capabilities = []  # 前端没有配置入口，永远是空列表

# 匹配逻辑
{"vision"}.issubset(set([]))  # → False → 被过滤掉

# 所有 Provider 都被过滤 → 返回 None → "无匹配 Provider"
```

### 3.3 缺失环节总结

```
方案设计缺失链：

ProviderConfig ORM 有 model_tier/capabilities 字段
    ↓ ✅
ProviderCreate Schema 有这两个字段
    ↓ ✅
Backend API 支持存取这两个字段
    ↓ ✅
前端 ProviderEditPage 表单          ← ❌ 缺失！没有 UI 让用户配置
    ↓
用户无法设置 Provider 的层级和能力
    ↓
成本路由无法找到匹配的 Provider
```

---

## 4. 修复方案

### 4.1 前端 ProviderEditPage 补充表单字段

在基本配置 Tab 中添加：

**模型层级选择器**：
```typescript
<Form.Item name="model_tier" label="模型层级" rules={[{ required: true }]}>
  <Select options={[
    { label: '简单（Simple）', value: 'simple' },
    { label: '中等（Moderate）', value: 'moderate' },
    { label: '复杂（Complex）', value: 'complex' },
    { label: '推理（Reasoning）', value: 'reasoning' },
    { label: '多模态（Multimodal）', value: 'multimodal' },
  ]} />
</Form.Item>
```

**能力标签多选器**：
```typescript
<Form.Item name="capabilities" label="模型能力">
  <Select mode="multiple" options={[
    { label: '文本生成', value: 'text' },
    { label: '代码生成', value: 'code' },
    { label: '视觉理解', value: 'vision' },
    { label: '逻辑推理', value: 'reasoning' },
    { label: '函数调用', value: 'function_calling' },
  ]} placeholder="选择一个或多个能力标签" />
</Form.Item>
```

### 4.2 表单加载时回填数据

```typescript
// useEffect 加载 Provider 数据时
form.setFieldsValue({
  // ...existing fields...
  model_tier: provider.model_tier || 'moderate',
  capabilities: provider.capabilities || [],
});
```

### 4.3 提交时包含字段

```typescript
// onFinish 提交时
const payload = {
  // ...existing fields...
  model_tier: values.model_tier,
  capabilities: values.capabilities || [],
};
```

### 4.4 成本路由页面增强（可选）

- 当无匹配时，在警告信息中列出当前所有启用 Provider 的层级分布
- 提示用户去编辑 Provider 的层级和能力配置

---

## 5. 各层级推荐的 Provider 配置示例

| Provider 示例 | model_tier | capabilities |
|---------------|------------|--------------|
| OpenAI GPT-4o | `complex` | `["text", "code", "vision", "function_calling"]` |
| OpenAI GPT-4o-mini | `moderate` | `["text", "code", "function_calling"]` |
| OpenAI o1 | `reasoning` | `["text", "code", "reasoning"]` |
| Claude 3.5 Sonnet | `complex` | `["text", "code", "vision", "function_calling"]` |
| 通义千问-VL | `multimodal` | `["text", "vision"]` |
| DeepSeek V3 | `complex` | `["text", "code", "reasoning", "function_calling"]` |
| GLM-4 | `moderate` | `["text", "code", "function_calling"]` |
