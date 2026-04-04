import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { ProLayout } from '@ant-design/pro-components';
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
  BookOutlined,
} from '@ant-design/icons';

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
  ],
};

const BasicLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <ProLayout
      title="CkyClaw"
      logo={false}
      layout="mix"
      fixSiderbar
      route={menuRoutes}
      location={{ pathname: location.pathname }}
      menuItemRender={(item, dom) => (
        <a onClick={() => item.path && navigate(item.path)}>{dom}</a>
      )}
    >
      <Outlet />
    </ProLayout>
  );
};

export default BasicLayout;
