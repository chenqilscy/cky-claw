import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { ProLayout } from '@ant-design/pro-components';
import { Button, Grid, Tooltip } from 'antd';
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
} from '@ant-design/icons';
import useThemeStore from '../stores/themeStore';

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
      path: '/agents',
      name: 'Agent 管理',
      icon: <RobotOutlined />,
    },
    {
      path: '/providers',
      name: '模型厂商',
      icon: <CloudServerOutlined />,
    },
    {
      path: '/runs',
      name: '执行记录',
      icon: <UnorderedListOutlined />,
    },
    {
      path: '/supervision',
      name: '监督面板',
      icon: <EyeOutlined />,
    },
    {
      path: '/traces',
      name: 'Trace 追踪',
      icon: <ApartmentOutlined />,
    },
    {
      path: '/guardrails',
      name: 'Guardrail 护栏',
      icon: <SafetyCertificateOutlined />,
    },
    {
      path: '/approvals',
      name: '审批队列',
      icon: <AuditOutlined />,
    },
    {
      path: '/mcp-servers',
      name: 'MCP Server',
      icon: <ApiOutlined />,
    },
    {
      path: '/tool-groups',
      name: '工具组',
      icon: <ToolOutlined />,
    },
    {
      path: '/memories',
      name: '记忆管理',
      icon: <BulbOutlined />,
    },
    {
      path: '/skills',
      name: '技能管理',
      icon: <BookOutlined />,
    },
    {
      path: '/templates',
      name: '模板市场',
      icon: <AppstoreOutlined />,
    },
    {
      path: '/workflows',
      name: '工作流',
      icon: <BranchesOutlined />,
    },
    {
      path: '/teams',
      name: '团队管理',
      icon: <TeamOutlined />,
    },
    {
      path: '/audit-logs',
      name: '审计日志',
      icon: <FileSearchOutlined />,
    },
    {
      path: '/roles',
      name: '角色权限',
      icon: <CrownOutlined />,
    },
    {
      path: '/im-channels',
      name: 'IM 渠道',
      icon: <LinkOutlined />,
    },
    {
      path: '/evaluations',
      name: 'Agent 评估',
      icon: <StarOutlined />,
    },
    {
      path: '/evolution',
      name: '自动进化',
      icon: <ExperimentOutlined />,
    },
    {
      path: '/organizations',
      name: '组织管理',
      icon: <BankOutlined />,
    },
    {
      path: '/scheduled-tasks',
      name: '定时任务',
      icon: <ClockCircleOutlined />,
    },
    {
      path: '/apm',
      name: 'APM 仪表盘',
      icon: <LineChartOutlined />,
    },
    {
      path: '/i18n',
      name: '国际化设置',
      icon: <GlobalOutlined />,
    },
  ],
};

const BasicLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const themeMode = useThemeStore((s: { mode: 'light' | 'dark' }) => s.mode);
  const toggleTheme = useThemeStore((s: { toggle: () => void }) => s.toggle);
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

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
      menuItemRender={(item, dom) => (
        <a onClick={() => item.path && navigate(item.path)}>{dom}</a>
      )}
      actionsRender={() => [
        <Tooltip key="theme" title={themeMode === 'dark' ? '切换亮色模式' : '切换暗色模式'}>
          <Button
            type="text"
            icon={themeMode === 'dark' ? <BulbFilled /> : <BulbOutlined />}
            onClick={toggleTheme}
          />
        </Tooltip>,
      ]}
    >
      <Outlet />
    </ProLayout>
  );
};

export default BasicLayout;
