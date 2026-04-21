# Kasaya 用户手册

> 本手册介绍 Kasaya 平台的日常使用操作。

## 登录

1. 访问 `http://localhost:3000`，自动跳转到登录页。
2. 输入用户名和密码，点击「登录」。
3. 首次使用需通过注册接口创建账号（见 [注册账号](#注册账号)）。

### GitHub OAuth 登录

如果管理员已配置 GitHub OAuth：
1. 在登录页点击「使用 GitHub 登录」按钮。
2. 跳转到 GitHub 授权页面，确认授权。
3. 授权成功后自动回调并完成登录。
4. 首次通过 GitHub 登录时，系统会自动创建账号。

### 企微 / 钉钉 / 飞书 SSO 登录

管理员配置相应 OAuth 应用凭证后：
1. 在登录页点击对应平台的登录按钮（「企微登录」/「钉钉登录」/「飞书登录」）。
2. 跳转到对应平台授权页面（企微：扫码登录、钉钉：扫码/账号授权、飞书：扫码授权）。
3. 授权成功后自动回调并完成登录。
4. 首次通过 SSO 登录时，系统会自动创建账号并关联企业身份。

> **配置环境变量**：企微需设置 `KASAYA_OAUTH_WECOM_CORP_ID` / `KASAYA_OAUTH_WECOM_AGENT_ID` / `KASAYA_OAUTH_WECOM_SECRET`；
> 钉钉需设置 `KASAYA_OAUTH_DINGTALK_CLIENT_ID` / `KASAYA_OAUTH_DINGTALK_CLIENT_SECRET`；
> 飞书需设置 `KASAYA_OAUTH_FEISHU_APP_ID` / `KASAYA_OAUTH_FEISHU_APP_SECRET`。

### OAuth 账号绑定

已登录用户可在个人设置中绑定/解绑 OAuth 账号：
- 绑定后可使用第三方账号直接登录。
- 解绑后需使用用户名密码登录。

### 注册账号

通过 API 创建第一个管理员账号：

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@example.com", "password": "your_password", "role": "admin"}'
```

注册成功后即可在 Web 界面登录。

---

## Agent 管理

### 查看 Agent 列表

1. 登录后，点击左侧导航栏「Agent 管理」。
2. 列表展示所有已创建的 Agent，支持按名称搜索和分页。

### 创建 Agent

1. 在 Agent 列表页点击「新建 Agent」按钮。
2. 填写表单：
   - **名称**：Agent 唯一标识，仅允许小写字母、数字和连字符（如 `my-agent`）。
   - **指令**：Agent 的系统提示词（Instructions），定义 Agent 的行为和能力。
   - **模型**：选择 LLM 模型（如 `gpt-4o`、`glm-4-flash`）。
   - **审批模式**：
     - `full-auto`：全自动执行（默认）。
     - `suggest`：工具调用前需人工审批。
     - `auto-edit`：MVP 阶段等同 full-auto。
3. 点击「保存」完成创建。

### 编辑 Agent

1. 在 Agent 列表中点击目标 Agent 的「编辑」按钮。
2. 修改配置后点击「保存」。

### 删除 Agent

1. 在 Agent 列表中点击目标 Agent 的「删除」按钮。
2. 确认删除（软删除，标记为 `is_active=false`）。

---

## 对话

### 开始对话

1. 点击左侧导航栏「对话」进入对话页面。
2. 从顶部下拉框选择一个 Agent。
3. 点击「新建会话」创建对话。
4. 在底部输入框输入消息，按回车或点击发送。

### 流式响应

发送消息后，Agent 的回复以流式方式实时显示：
- **agent_start**：Agent 开始处理。
- **text_delta**：逐字显示回复内容。
- **tool_call / tool_output**：工具调用及结果（如果 Agent 配置了工具）。
- **run_end**：处理完成。

### 对话历史

左侧边栏展示当前 Agent 的历史会话列表，点击可切换到之前的对话。

---

## 执行记录

### 查看 Token 消耗

1. 点击左侧导航栏「执行记录」。
2. 上方统计卡片展示总调用次数、总 Token 消耗等汇总信息。
3. 下方表格展示每次 LLM 调用的详细记录：
   - Agent 名称、模型、输入/输出/总 Token 数。
   - 调用时间。

### 筛选与汇总

- **按 Agent 筛选**：在搜索框输入 Agent 名称。
- **按时间筛选**：选择时间范围。
- **按模型筛选**：下拉选择模型名称。
- **维度切换**：使用 Segmented 控件在「按 Agent+模型」「按用户」「按模型」三个维度间切换汇总视图。

---

## 监督面板

### 查看活跃会话

1. 点击左侧导航栏「监督面板」。
2. 统计卡片展示活跃会话数、总 Token 消耗等实时指标。
3. 表格列出所有活跃会话及其状态。

### 暂停/恢复会话

1. 在会话列表中，点击「暂停」按钮可暂停运行中的会话。
2. 暂停后，按钮变为「恢复」，点击可继续会话。

### 查看会话详情

点击会话行可查看详情弹窗，展示会话元数据和 Token 使用统计。

---

## Model Provider 管理

> 需要管理员权限。

### 查看 Provider 列表

1. 点击左侧导航栏「Provider 管理」。
2. 列表展示所有已配置的 AI 模型提供商。

### 添加 Provider

1. 点击「新建 Provider」。
2. 填写：
   - **名称**：Provider 唯一标识。
   - **Provider 类型**：如 `openai`、`zhipu`、`anthropic` 等。
   - **认证类型**：如 `api_key`。
   - **API Key**：模型服务的密钥（加密存储）。
   - **Base URL**：自定义 API 端点（可选）。
   - **默认模型**：该 Provider 的默认模型名称。
3. 点击「保存」。

### 启用/禁用 Provider

在列表中使用开关控件切换 Provider 的启用状态。禁用后，使用该 Provider 的 Agent 将无法调用 LLM。

### 删除 Provider

点击「删除」按钮并确认。

---

## API 文档

Kasaya 后端基于 FastAPI，自动生成交互式 API 文档：

- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`

所有 API 端点、请求参数、响应结构均可在线查看和测试。

---

## IM 渠道接入

### 添加渠道

1. 点击左侧导航栏「渠道管理」。
2. 点击「新建渠道」，填写：
   - **名称**：渠道标识。
   - **渠道类型**：`wecom`（企业微信）或 `dingtalk`（钉钉）。
   - **配置信息**：根据渠道类型填写 Token、AES Key、CorpID 等。
3. 保存后获取 Webhook URL。

### 企业微信接入

1. 在企业微信管理后台创建自建应用。
2. 配置应用的「接收消息」URL 为 Kasaya 提供的 Webhook URL。
3. 将 Token、EncodingAESKey、CorpID 填入渠道配置。
4. 企业微信用户发送的消息会自动路由到绑定的 Agent 处理。

### 钉钉接入

1. 在钉钉开放平台创建机器人。
2. 配置消息接收地址为 Kasaya 的 Webhook URL。
3. 将签名密钥（App Secret）和 Webhook URL 填入渠道配置。
4. 钉钉用户 @机器人 的消息会自动路由到绑定的 Agent。
