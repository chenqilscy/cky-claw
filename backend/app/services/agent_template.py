"""AgentTemplate 业务逻辑层。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.agent_template import AgentTemplate
from app.schemas.agent_template import AgentTemplateCreate, AgentTemplateUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内置模板定义
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATES: list[dict] = [
    {
        "name": "triage",
        "display_name": "分诊路由 Agent",
        "description": "智能分诊助手，理解用户意图并路由到最合适的专家 Agent。支持多轮追问澄清意图。",
        "category": "routing",
        "icon": "BranchesOutlined",
        "config": {
            "instructions": (
                "你是一个智能分诊助手。你的职责是：\n"
                "1. 理解用户意图并归类到预定义类别\n"
                "2. 如果意图明确，立即使用 handoff 转交给最合适的专家 Agent\n"
                "3. 如果意图不明确，通过最多 2 轮追问澄清\n"
                "4. 不要自己回答专业问题，你的唯一职责是路由"
            ),
            "handoffs": ["data-analyst", "code-assistant", "researcher", "customer-service", "faq-bot"],
            "tools": [],
            "guardrails": {"input": ["prompt_injection_detector", "content_safety_filter"], "output": []},
        },
    },
    {
        "name": "faq-bot",
        "display_name": "FAQ 问答 Agent",
        "description": "基于知识库回答常见问题，找不到答案时礼貌告知并建议联系人工客服。",
        "category": "customer-support",
        "icon": "QuestionCircleOutlined",
        "config": {
            "instructions": (
                "你是一个 FAQ 问答助手。你的职责是：\n"
                "1. 基于加载的知识库和 Skill 文档回答用户常见问题\n"
                "2. 如果知识库中找不到答案，礼貌告知并建议联系人工客服\n"
                "3. 回答简洁、准确，引用来源\n"
                "4. 不编造信息"
            ),
            "tools": [],
            "skills": ["customer-service-handbook"],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["content_safety_filter", "pii_redactor"]},
        },
    },
    {
        "name": "researcher",
        "display_name": "网络调研 Agent",
        "description": "专业网络调研助手，搜索多来源信息并输出结构化调研报告。",
        "category": "research",
        "icon": "SearchOutlined",
        "config": {
            "instructions": (
                "你是一个专业的网络调研助手。你的工作流程：\n"
                "1. 分析调研主题，拆解为 3-5 个搜索关键词\n"
                "2. 使用 web_search 工具搜索每个关键词\n"
                "3. 综合多个来源，输出结构化调研报告\n"
                "4. 注明信息时效性"
            ),
            "tools": [{"group": "web-search"}],
            "skills": ["research-methodology"],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["content_safety_filter"]},
        },
    },
    {
        "name": "data-analyst",
        "display_name": "数据分析 Agent",
        "description": "数据分析专家，支持 SQL 查询、Python 分析、可视化图表生成。",
        "category": "analytics",
        "icon": "BarChartOutlined",
        "config": {
            "instructions": (
                "你是一个数据分析专家。你的工作流程：\n"
                "1. 理解用户的分析需求\n"
                "2. 如需查询数据库，先用 SQL 查询获取数据\n"
                "3. 使用 Python 进行数据处理和统计分析\n"
                "4. 生成可视化图表\n"
                "5. 输出分析报告"
            ),
            "tools": [{"group": "code-executor"}, {"group": "database"}],
            "skills": ["data-analysis"],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["pii_redactor"]},
        },
    },
    {
        "name": "report-writer",
        "display_name": "报告撰写 Agent",
        "description": "专业报告撰写助手，将分析数据整理为结构化 Markdown 报告。",
        "category": "content",
        "icon": "FileTextOutlined",
        "config": {
            "instructions": (
                "你是一个专业的报告撰写助手。你的职责是：\n"
                "1. 接收分析数据/调研结果，整理为结构化报告\n"
                "2. 报告格式：Markdown，包含标题、摘要、正文、结论、附录\n"
                "3. 使用 file-ops 工具将报告保存为文件\n"
                "4. 图表和数据引用必须标注来源"
            ),
            "tools": [{"group": "file-ops"}],
            "skills": ["writing-style-guide", "data-analysis"],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["content_safety_filter"]},
        },
    },
    {
        "name": "code-assistant",
        "display_name": "代码辅助 Agent",
        "description": "多语言代码辅助助手，支持编写、审阅、解释、调试代码。",
        "category": "development",
        "icon": "CodeOutlined",
        "config": {
            "instructions": (
                "你是一个代码辅助助手，支持多种编程语言。你可以：\n"
                "1. 根据需求编写代码\n"
                "2. 审阅已有代码，指出问题和改进建议\n"
                "3. 解释代码逻辑\n"
                "4. 调试和修复 Bug\n"
                "5. 使用 code-executor 执行代码验证结果"
            ),
            "tools": [{"group": "code-executor"}],
            "skills": ["code-review"],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["content_safety_filter"]},
        },
    },
    {
        "name": "translator",
        "display_name": "多语言翻译 Agent",
        "description": "专业翻译助手，支持中/英/日/韩/法/德/西等主要语言互译。",
        "category": "content",
        "icon": "TranslationOutlined",
        "config": {
            "instructions": (
                "你是一个专业翻译助手。翻译规则：\n"
                "1. 自动检测源语言，翻译为用户指定的目标语言\n"
                "2. 保持原文语义、语气和风格\n"
                "3. 专业术语保留原文并在括号中注释翻译\n"
                "4. 支持中/英/日/韩/法/德/西等主要语言"
            ),
            "tools": [],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["content_safety_filter"]},
        },
    },
    {
        "name": "customer-service",
        "display_name": "客服助手 Agent",
        "description": "客服助手，处理产品咨询、订单查询、退款申请等客户问题。",
        "category": "customer-support",
        "icon": "CustomerServiceOutlined",
        "config": {
            "instructions": (
                "你是一个客服助手。工作流程：\n"
                "1. 理解客户问题（产品咨询/订单查询/退款申请/投诉等）\n"
                "2. 参考 customer-service-handbook 中的标准话术和政策\n"
                "3. 通过 http 工具调用业务 API 查询订单/账户信息\n"
                "4. 始终保持礼貌、耐心、专业\n"
                "5. 绝不泄露内部系统信息或其他客户数据"
            ),
            "tools": [{"group": "http"}],
            "skills": ["customer-service-handbook"],
            "guardrails": {
                "input": ["prompt_injection_detector", "content_safety_filter"],
                "output": ["pii_redactor", "content_safety_filter"],
            },
        },
    },
    {
        "name": "summarizer",
        "display_name": "文本摘要 Agent",
        "description": "文本摘要专家，提取核心信息，输出结构化摘要。",
        "category": "content",
        "icon": "FileSearchOutlined",
        "config": {
            "instructions": (
                "你是一个文本摘要专家。摘要规则：\n"
                "1. 提取输入文本的核心信息\n"
                "2. 输出结构：一句话摘要 → 关键要点 → 详细摘要\n"
                "3. 摘要长度约为原文的 20-30%\n"
                "4. 保留关键数据、人名、日期等事实信息\n"
                "5. 不添加原文中没有的推断"
            ),
            "tools": [],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["content_safety_filter"]},
        },
    },
    {
        "name": "coordinator",
        "display_name": "总协调员 Agent",
        "description": "分解复杂任务并调度多 Agent 协作执行，是 Agent Team 的核心调度器。",
        "category": "routing",
        "icon": "ClusterOutlined",
        "config": {
            "instructions": (
                "你是系统的总协调员。你的职责是分解复杂任务并调度执行：\n"
                "1. 分析用户任务，判断是否需要多步骤/多 Agent 协作\n"
                "2. 如果任务简单，直接使用合适的单个 Agent 处理\n"
                "3. 如果任务复杂，选择最合适的 Agent Team 执行\n"
                "4. 汇总执行结果，生成最终回复\n"
                "5. 处理执行失败的情况，进行重试或降级"
            ),
            "tools": [],
            "guardrails": {"input": ["prompt_injection_detector"], "output": ["content_safety_filter"]},
        },
    },
]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_template(db: AsyncSession, data: AgentTemplateCreate) -> AgentTemplate:
    """创建 Agent 模板。"""
    record = AgentTemplate(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        category=data.category,
        icon=data.icon,
        config=data.config,
        is_builtin=False,
        metadata_=data.metadata,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_template(db: AsyncSession, template_id: uuid.UUID) -> AgentTemplate:
    """获取单个模板。"""
    stmt = select(AgentTemplate).where(AgentTemplate.id == template_id)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"模板 '{template_id}' 不存在")
    return record


async def get_template_by_name(db: AsyncSession, name: str) -> AgentTemplate:
    """按名称获取模板。"""
    stmt = select(AgentTemplate).where(AgentTemplate.name == name)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"模板 '{name}' 不存在")
    return record


async def list_templates(
    db: AsyncSession,
    *,
    category: str | None = None,
    is_builtin: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AgentTemplate], int]:
    """获取模板列表（分页 + 过滤）。"""
    base = select(AgentTemplate)
    if category:
        base = base.where(AgentTemplate.category == category)
    if is_builtin is not None:
        base = base.where(AgentTemplate.is_builtin == is_builtin)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        base.order_by(AgentTemplate.is_builtin.desc(), AgentTemplate.name)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def update_template(
    db: AsyncSession, template_id: uuid.UUID, data: AgentTemplateUpdate
) -> AgentTemplate:
    """更新模板（内置模板不可更新）。"""
    record = await get_template(db, template_id)
    if record.is_builtin:
        raise ValueError("内置模板不可编辑")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "metadata":
            setattr(record, "metadata_", value)
        else:
            setattr(record, key, value)
    from datetime import datetime, timezone
    record.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_template(db: AsyncSession, template_id: uuid.UUID) -> None:
    """删除模板（内置模板不可删除）。"""
    record = await get_template(db, template_id)
    if record.is_builtin:
        raise ValueError("内置模板不可删除")
    await db.delete(record)
    await db.commit()


async def seed_builtin_templates(db: AsyncSession) -> int:
    """初始化内置模板（幂等）。"""
    created = 0
    for tpl_data in BUILTIN_TEMPLATES:
        stmt = select(AgentTemplate).where(AgentTemplate.name == tpl_data["name"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is None:
            record = AgentTemplate(
                name=tpl_data["name"],
                display_name=tpl_data["display_name"],
                description=tpl_data["description"],
                category=tpl_data["category"],
                icon=tpl_data["icon"],
                config=tpl_data["config"],
                is_builtin=True,
                metadata_={},
            )
            db.add(record)
            created += 1
    if created > 0:
        await db.commit()
    logger.info("内置模板初始化完成：新增 %d 个", created)
    return created
