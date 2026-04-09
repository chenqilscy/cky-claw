# CkyClaw CLI

终端 Agent 交互工具。依赖 [ckyclaw-framework](../ckyclaw-framework/README.md)，提供命令行聊天能力。

## 安装

```bash
pip install ckyclaw-cli
```

## 使用

### 交互式聊天

```bash
# 默认模型 gpt-4o-mini
ckyclaw chat

# 指定模型
ckyclaw chat --model claude-sonnet-4-20250514

# 自定义指令
ckyclaw chat --instructions "你是一个代码审查专家"

# 指定 API Key
ckyclaw chat --api-key sk-xxx
```

### 命令列表

```bash
ckyclaw --help       # 查看所有命令
ckyclaw version      # 显示版本
ckyclaw chat --help  # 查看 chat 参数
```

### 聊天内置命令

| 命令 | 说明 |
|------|------|
| `exit` / `quit` | 退出 |
| `clear` | 清空对话历史 |
| Ctrl+C | 优雅退出 |
