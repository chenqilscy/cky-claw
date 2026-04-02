import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { ProLayout } from '@ant-design/pro-components';
import {
  MessageOutlined,
  RobotOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';

const menuRoutes = {
  routes: [
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
      path: '/runs',
      name: '执行记录',
      icon: <UnorderedListOutlined />,
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
