# Agent 输出风格控制

Kasaya 支持为每个 Agent 配置输出风格，控制 LLM 响应的冗余程度和结构。

## 内置风格

| 风格标识 | 说明 | 效果 |
|----------|------|------|
| `concise` | 简洁模式（基于 [talk-normal](https://github.com/hexiecs/talk-normal)） | 减少约 70% 冗余输出，保留信息密度 |
| `formal` | 正式模式 | 专业学术语调，精确用词，避免口语化 |
| `creative` | 创意模式 | 生动表达，使用比喻和类比，增强可读性 |
| `null` | 默认 | 不启用风格修饰，LLM 按自身习惯输出 |

## concise 模式核心规则

- 直接给答案，再补充上下文
- 禁止否定式对比短语（"不是X，而是Y"）
- 清除所有废话填充词
- 不重述用户问题
- 是非题：先回答，一句话推理
- 代码题：直接给代码 + 用法示例
- 概念解释：3-5 句话，覆盖本质
- 不以总结词收尾（"总之"、"综上"）
- 不主动提供假设性后续建议

## 使用方式

### 方式一：API 创建/更新 Agent

```bash
# 创建时指定
curl -X POST /api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "my-agent", "response_style": "concise"}'

# 更新已有 Agent
curl -X PUT /api/v1/agents/my-agent \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"response_style": "concise"}'

# 取消风格；传 null 恢复默认
curl -X PUT /api/v1/agents/my-agent \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"response_style": null}'
```

### 方式二：Web 管理界面

在 Agent 编辑页面找到「输出风格」下拉框，选择「简洁模式 (talk-normal)」。

### 方式三：Framework 直接使用

```python
from kasaya.agent import Agent

agent = Agent(
    name="concise-assistant",
    instructions="你是一个技术助手。",
    response_style="concise",
)
```

## 技术原理

`response_style` 字段存储在 Agent 配置中。Runner 构建 system prompt 时，
在 Agent instructions **之前** 注入对应风格的规则文本。

```
[风格规则 prompt]        ← response_style 自动注入
[Agent instructions]     ← 用户自定义指令
[output_type hint]       ← 结构化输出 JSON Schema（如果有）
```

## 扩展自定义风格

在 `kasaya/agent/response_style.py` 的 `RESPONSE_STYLES` 字典中注册：

```python
RESPONSE_STYLES["formal"] = "Use formal academic tone. Avoid contractions..."
```

同时更新 Backend schema validator 的 `allowed` 集合以允许新风格通过 API 校验。
