/**
 * PageContainer — 标准化页面容器。
 *
 * 提供统一的页面标题 / 描述 / 操作区 / 面包屑布局，
 * 消除各页面间的排版不一致问题。
 * 内置淡入 + 微位移过渡动画。
 */
import type { ReactNode } from 'react';
import { Breadcrumb, Flex, Space, Typography, theme } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

/* ---------- 页面进入动画 ---------- */

const fadeInStyle: React.CSSProperties = {
  animation: 'pageContainerFadeIn 0.25s ease-out',
};

/* 通过全局 style 标签注入 keyframes（仅注入一次） */
if (typeof document !== 'undefined' && !document.getElementById('__page-container-anim')) {
  const style = document.createElement('style');
  style.id = '__page-container-anim';
  style.textContent = `
    @keyframes pageContainerFadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
  `;
  document.head.appendChild(style);
}

/* ---------- 面包屑映射 ---------- */

const BREADCRUMB_MAP: Record<string, string> = {
  dashboard: '概览',
  chat: '对话',
  agents: 'Agent 管理',
  'visual-builder': '可视化搭建',
  'handoff-editor': 'Handoff 编排',
  evaluations: 'Agent 评估',
  evolution: '自动进化',
  debug: 'Agent 调试器',
  providers: '模型厂商',
  'mcp-servers': 'MCP Server',
  'tool-groups': '工具组',
  'cost-router': '成本路由',
  'knowledge-bases': '知识库',
  memories: '记忆管理',
  skills: '技能管理',
  runs: '执行记录',
  traces: 'Trace 追踪',
  supervision: '监督面板',
  apm: 'APM 仪表盘',
  checkpoints: '检查点',
  guardrails: 'Guardrail 护栏',
  approvals: '审批队列',
  intent: '意图检测',
  compliance: '合规管理',
  templates: '模板市场',
  marketplace: 'Agent 市场',
  benchmark: 'Agent 评测',
  'ab-test': 'A/B 测试',
  'im-channels': 'IM 渠道',
  a2a: 'A2A 协议',
  workflows: '工作流',
  'scheduled-tasks': '定时任务',
  teams: '团队管理',
  organizations: '组织管理',
  roles: '角色权限',
  'audit-logs': '审计日志',
  environments: '环境管理',
  i18n: '国际化设置',
  new: '新建',
  edit: '编辑',
  versions: '版本历史',
};

/* ---------- Props ---------- */

interface PageContainerProps {
  /** 页面标题 */
  title: string;
  /** 标题左侧图标 */
  icon?: ReactNode;
  /** 页面副标题 / 简要说明 */
  description?: string;
  /** 标题栏右侧操作区 */
  extra?: ReactNode;
  /** 是否隐藏面包屑（默认不隐藏） */
  hideBreadcrumb?: boolean;
  /** 覆盖面包屑中特定 URL 段的显示文本，key 为 URL 段原始值 */
  breadcrumbOverrides?: Record<string, string>;
  children: ReactNode;
}

/**
 * 统一页面容器：面包屑 + 标题 + 描述 + 操作区 + 内容。
 */
export const PageContainer: React.FC<PageContainerProps> = ({
  title,
  icon,
  description,
  extra,
  hideBreadcrumb,
  breadcrumbOverrides,
  children,
}) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { token } = theme.useToken();

  /* 自动生成面包屑 */
  const pathSegments = location.pathname.split('/').filter(Boolean);
  const breadcrumbItems = [
    { title: <a onClick={() => navigate('/dashboard')}>首页</a>, key: 'home' },
    ...pathSegments.map((seg, idx) => {
      const path = '/' + pathSegments.slice(0, idx + 1).join('/');
      const label = breadcrumbOverrides?.[seg] ?? BREADCRUMB_MAP[seg] ?? seg;
      const isLast = idx === pathSegments.length - 1;
      return {
        title: isLast ? label : <a onClick={() => navigate(path)}>{label}</a>,
        key: path,
      };
    }),
  ];

  return (
    <Flex vertical gap={0} style={fadeInStyle}>
      {/* 面包屑 */}
      {!hideBreadcrumb && (
        <div style={{ marginBottom: 12 }}>
          <Breadcrumb items={breadcrumbItems} />
        </div>
      )}

      {/* 标题区 — 白色背景卡片 */}
      <div
        style={{
          background: token.colorBgContainer,
          borderRadius: token.borderRadiusLG,
          padding: '20px 24px',
          marginBottom: 20,
          boxShadow: token.boxShadow,
        }}
      >
        <Flex justify="space-between" align="flex-start" wrap="wrap" gap={12}>
          <Flex vertical gap={4}>
            <Space size={8} align="center">
              {icon && (
                <span style={{
                  fontSize: 22,
                  color: token.colorPrimary,
                  display: 'flex',
                  background: token.colorPrimaryBg,
                  borderRadius: 8,
                  padding: 6,
                }}>
                  {icon}
                </span>
              )}
              <Title level={4} style={{ margin: 0 }}>
                {title}
              </Title>
            </Space>
            {description && (
              <Text type="secondary" style={{ fontSize: 13, marginLeft: icon ? 42 : 0 }}>
                {description}
              </Text>
            )}
          </Flex>
          {extra && <Space wrap>{extra}</Space>}
        </Flex>
      </div>

      {/* 页面内容 */}
      {children}
    </Flex>
  );
};
