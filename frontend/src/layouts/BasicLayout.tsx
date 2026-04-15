import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { ProLayout } from '@ant-design/pro-components';
import { Button, Select, Tag, Tooltip, theme } from 'antd';
import useEnvironmentStore from '../stores/environmentStore';
import { environmentService } from '../services/environmentService';
import type { Environment } from '../services/environmentService';
import {
  DashboardOutlined,
  MessageOutlined,
  RobotOutlined,
  UnorderedListOutlined,
  EyeOutlined,
  CloudServerOutlined,
  ApartmentOutlined,
  SafetyCertificateOutlined,
  AuditOutlined,
  ApiOutlined,
  ToolOutlined,
  BulbOutlined,
  BulbFilled,
  BookOutlined,
  AppstoreOutlined,
  DatabaseOutlined,
  BranchesOutlined,
  TeamOutlined,
  FileSearchOutlined,
  CrownOutlined,
  LinkOutlined,
  StarOutlined,
  BankOutlined,
  ClockCircleOutlined,
  LineChartOutlined,
  GlobalOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  HistoryOutlined,
  AimOutlined,
  BugOutlined,
  DeploymentUnitOutlined,
  SwapOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import useThemeStore from '../stores/themeStore';
import { useResponsive } from '../hooks/useResponsive';

const menuRoutes = {
  routes: [
    {
      path: '/dashboard',
      name: '概览',
      icon: <DashboardOutlined />,
    },
    {
      path: '/chat',
      name: '对话',
      icon: <MessageOutlined />,
    },
    {
      name: 'Agent',
      icon: <RobotOutlined />,
      children: [
        { path: '/agents', name: 'Agent 管理' },
        { path: '/agents/visual-builder', name: '可视化搭建', icon: <BranchesOutlined /> },
        { path: '/evaluations', name: 'Agent 评估', icon: <StarOutlined /> },
        { path: '/evolution', name: '自动进化', icon: <ExperimentOutlined /> },
        { path: '/debug', name: 'Agent 调试器', icon: <BugOutlined /> },
      ],
    },
    {
      name: '模型与工具',
      icon: <CloudServerOutlined />,
      children: [
        { path: '/providers', name: '模型厂商' },
        { path: '/mcp-servers', name: 'MCP Server', icon: <ApiOutlined /> },
        { path: '/tool-groups', name: '工具组', icon: <ToolOutlined /> },
        { path: '/cost-router', name: '成本路由', icon: <ThunderboltOutlined /> },
      ],
    },
    {
      name: '知识与记忆',
      icon: <BulbOutlined />,
      children: [
        { path: '/knowledge-bases', name: '知识库', icon: <DatabaseOutlined /> },
        { path: '/memories', name: '记忆管理' },
        { path: '/skills', name: '技能管理', icon: <BookOutlined /> },
      ],
    },
    {
      name: '监控与追踪',
      icon: <EyeOutlined />,
      children: [
        { path: '/runs', name: '执行记录', icon: <UnorderedListOutlined /> },
        { path: '/traces', name: 'Trace 追踪', icon: <ApartmentOutlined /> },
        { path: '/supervision', name: '监督面板' },
        { path: '/apm', name: 'APM 仪表盘', icon: <LineChartOutlined /> },
        { path: '/checkpoints', name: '检查点', icon: <HistoryOutlined /> },
      ],
    },
    {
      name: '安全与治理',
      icon: <SafetyCertificateOutlined />,
      children: [
        { path: '/guardrails', name: 'Guardrail 护栏' },
        { path: '/approvals', name: '审批队列', icon: <AuditOutlined /> },
        { path: '/intent', name: '意图检测', icon: <AimOutlined /> },
        { path: '/compliance', name: '合规管理' },
      ],
    },
    {
      name: '市场与评测',
      icon: <ShopOutlined />,
      children: [
        { path: '/templates', name: '模板市场', icon: <AppstoreOutlined /> },
        { path: '/marketplace', name: 'Agent 市场' },
        { path: '/benchmark', name: 'Agent 评测', icon: <ExperimentOutlined /> },
        { path: '/ab-test', name: 'A/B 测试' },
      ],
    },
    {
      name: '集成与渠道',
      icon: <LinkOutlined />,
      children: [
        { path: '/im-channels', name: 'IM 渠道' },
        { path: '/a2a', name: 'A2A 协议', icon: <SwapOutlined /> },
        { path: '/workflows', name: '工作流', icon: <BranchesOutlined /> },
        { path: '/scheduled-tasks', name: '定时任务', icon: <ClockCircleOutlined /> },
      ],
    },
    {
      name: '系统管理',
      icon: <BankOutlined />,
      children: [
        { path: '/teams', name: '团队管理', icon: <TeamOutlined /> },
        { path: '/organizations', name: '组织管理' },
        { path: '/roles', name: '角色权限', icon: <CrownOutlined /> },
        { path: '/audit-logs', name: '审计日志', icon: <FileSearchOutlined /> },
        { path: '/environments', name: '环境管理', icon: <DeploymentUnitOutlined /> },
        { path: '/i18n', name: '国际化设置', icon: <GlobalOutlined /> },
      ],
    },
  ],
};

const BasicLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const themeMode = useThemeStore((s: { mode: 'light' | 'dark' }) => s.mode);
  const toggleTheme = useThemeStore((s: { toggle: () => void }) => s.toggle);
  const { isMobile } = useResponsive();
  const { token } = theme.useToken();

  const currentEnv = useEnvironmentStore((s) => s.current);
  const setCurrentEnv = useEnvironmentStore((s) => s.setCurrent);
  const [envList, setEnvList] = useState<Environment[]>([]);

  useEffect(() => {
    environmentService.list().then((res) => setEnvList(res.data)).catch(() => {});
  }, []);

  return (
    <ProLayout
      title="CkyClaw"
      logo={false}
      layout="mix"
      fixSiderbar
      collapsed={isMobile ? true : undefined}
      breakpoint="md"
      route={menuRoutes}
      location={{ pathname: location.pathname }}
      token={{
        header: {
          heightLayoutHeader: 56,
          colorBgHeader: token.colorBgContainer,
          colorHeaderTitle: token.colorText,
        },
        sider: {
          colorMenuBackground: token.colorBgContainer,
          colorBgMenuItemSelected: token.colorPrimaryBg,
          colorTextMenuSelected: token.colorPrimary,
          colorTextMenuItemHover: token.colorPrimary,
          colorTextMenu: token.colorTextSecondary,
          colorTextMenuTitle: token.colorText,
          paddingInlineLayoutMenu: 8,
          paddingBlockLayoutMenu: 4,
        },
        pageContainer: {
          paddingBlockPageContainerContent: 24,
          paddingInlinePageContainerContent: 24,
        },
      }}
      siderMenuType="sub"
      menuItemRender={(item, dom) => (
        <a
          role="link"
          tabIndex={0}
          aria-label={item.name}
          onClick={() => item.path && navigate(item.path)}
          onKeyDown={(e) => { if (e.key === 'Enter' && item.path) navigate(item.path); }}
        >
          {dom}
        </a>
      )}
      actionsRender={() => [
        <Select
          key="env"
          value={currentEnv}
          onChange={setCurrentEnv}
          allowClear
          placeholder={isMobile ? '环境' : '全部环境'}
          style={{ width: isMobile ? 90 : 130 }}
          size="small"
          variant="borderless"
        >
          {envList.map((e) => (
            <Select.Option key={e.name} value={e.name}>
              <Tag color={e.color} style={{ marginRight: 0 }}>{e.display_name}</Tag>
            </Select.Option>
          ))}
        </Select>,
        <Tooltip key="theme" title={themeMode === 'dark' ? '切换亮色模式' : '切换暗色模式'}>
          <Button
            type="text"
            aria-label={themeMode === 'dark' ? '切换亮色模式' : '切换暗色模式'}
            icon={themeMode === 'dark' ? <BulbFilled /> : <BulbOutlined />}
            onClick={toggleTheme}
          />
        </Tooltip>,
      ]}
    >
      <main
        role="main"
        aria-label="页面内容"
        style={{ padding: 24, minHeight: 'calc(100vh - 56px)', background: token.colorBgLayout }}
      >
        <Outlet />
      </main>
    </ProLayout>
  );
};

export default BasicLayout;
