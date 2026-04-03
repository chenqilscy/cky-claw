"""ContentSafetyGuardrail — 检测有害/不当内容（暴力、歧视、违法）。"""

from __future__ import annotations

from dataclasses import dataclass

from ckyclaw_framework.guardrails.llm_guardrail import LLMGuardrail

_CONTENT_SAFETY_TEMPLATE = """\
你是一个内容安全审核专家。请判断以下内容是否包含有害或不当信息。

有害内容包括但不限于：
1. 暴力内容（煽动暴力、描述暴力行为）
2. 歧视内容（种族、性别、宗教、地域歧视）
3. 违法内容（教唆犯罪、传播非法信息）
4. 色情内容（露骨的性描述）
5. 仇恨言论（针对特定群体的攻击性言论）
6. 自伤内容（自杀、自残相关引导）
7. 虚假信息（明显的谣言或误导性内容）

内容:
{content}

请用以下 JSON 格式回复（只输出 JSON，不要其他内容）:
{{"safe": true/false, "confidence": 0.0~1.0, "reason": "判断理由"}}
"""


@dataclass
class ContentSafetyGuardrail(LLMGuardrail):
    """内容安全检测护栏（LLM-Based）。

    使用 LLM 判定内容是否包含暴力、歧视、违法等有害信息。
    同时支持 Input 和 Output 检测。

    用法::

        guard = ContentSafetyGuardrail()
        agent = Agent(
            input_guardrails=[InputGuardrail(guardrail_function=guard.as_input_fn())],
            output_guardrails=[OutputGuardrail(guardrail_function=guard.as_output_fn())],
        )
    """

    prompt_template: str = _CONTENT_SAFETY_TEMPLATE
    name: str = "content_safety"
    threshold: float = 0.75
