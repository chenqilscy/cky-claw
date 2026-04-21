"""示例 3: Guardrails + Handoff — 展示护栏和多 Agent 编排。

运行方式：
    export OPENAI_API_KEY=sk-...
    python examples/03_guardrails_handoff.py
"""

from __future__ import annotations

from kasaya import Agent, Handoff, RegexGuardrail, Runner

# --- 护栏：拦截手机号码 ---

phone_guard = RegexGuardrail(
    name="no-phone-number",
    pattern=r"1[3-9]\d{9}",
    fail_message="检测到手机号码，已拦截输入。",
)

# --- 专业 Agent ---

translator = Agent(
    name="translator",
    instructions="你是专业翻译。将用户输入翻译为英文，只返回翻译结果。",
    model="gpt-4o-mini",
)

summarizer = Agent(
    name="summarizer",
    instructions="你是摘要专家。将用户输入压缩为一句话摘要。",
    model="gpt-4o-mini",
)

# --- 编排 Agent ---

orchestrator = Agent(
    name="orchestrator",
    instructions=(
        "你是任务分配器。根据用户需求：\n"
        "- 如果用户需要翻译，使用 transfer_to_translator\n"
        "- 如果用户需要摘要，使用 transfer_to_summarizer\n"
        "- 其他情况直接回答"
    ),
    model="gpt-4o-mini",
    input_guardrails=[phone_guard],
    handoffs=[
        Handoff(agent=translator),
        Handoff(agent=summarizer),
    ],
)


def main() -> None:
    """演示 Guardrails 和 Handoff。"""
    # 正常请求 — 触发 Handoff
    print("=== 翻译请求 ===")
    result = Runner.run_sync(orchestrator, "请帮我翻译：今天天气真好")
    print(f"结果: {result.final_output}\n")

    # 带手机号 — 触发 Guardrail 拦截
    print("=== 护栏拦截测试 ===")
    try:
        Runner.run_sync(orchestrator, "我的手机号是 13800138000")
    except Exception as e:
        print(f"已拦截: {e}")


if __name__ == "__main__":
    main()
