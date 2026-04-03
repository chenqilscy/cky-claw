import { useCallback, useEffect, useState } from 'react';
import { Button, message, Popconfirm, Input, Space, Tag } from 'antd';
import { PlusOutlined, ReloadOutlined, HistoryOutlined, ApartmentOutlined } from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { useNavigate } from 'react-router-dom';
import { agentService } from '../../services/agentService';
import type { AgentConfig } from '../../services/agentService';

const AgentListPage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<AgentConfig[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    try {
      const offset = (pagination.current - 1) * pagination.pageSize;
      const res = await agentService.list({
        search: search || undefined,
        limit: pagination.pageSize,
        offset,
      });
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取 Agent 列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination, search]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const handleDelete = async (name: string) => {
    try {
      await agentService.delete(name);
      message.success('删除成功');
      fetchAgents();
    } catch {
      message.error('删除失败');
    }
  };

  const columns: ProColumns<AgentConfig>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      render: (_, record) => (
        <a onClick={() => navigate(`/agents/${record.name}/edit`)}>{record.name}</a>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
    },
    {
      title: '模型',
      dataIndex: 'model',
      width: 200,
    },
    {
      title: '审批模式',
      dataIndex: 'approval_mode',
      width: 120,
      render: (_, record) => {
        const colorMap: Record<string, string> = {
          'suggest': 'blue',
          'auto-edit': 'green',
          'full-auto': 'orange',
        };
        return <Tag color={colorMap[record.approval_mode] || 'default'}>{record.approval_mode}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (_, record) => new Date(record.created_at).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 240,
      render: (_, record) => (
        <Space>
          <a onClick={() => navigate(`/agents/${record.name}/edit`)}>编辑</a>
          <a onClick={() => navigate(`/agents/${record.id}/versions`)}><HistoryOutlined /> 版本</a>
          <Popconfirm
            title="确认删除该 Agent？"
            onConfirm={() => handleDelete(record.name)}
          >
            <a style={{ color: '#ff4d4f' }}>删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <ProTable<AgentConfig>
        headerTitle="Agent 管理"
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        search={false}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total,
          onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
        }}
        toolBarRender={() => [
          <Input.Search
            key="search"
            placeholder="搜索名称 / 描述"
            allowClear
            onSearch={(v) => { setSearch(v); setPagination((p) => ({ ...p, current: 1 })); }}
            style={{ width: 240 }}
          />,
          <Button
            key="reload"
            icon={<ReloadOutlined />}
            onClick={fetchAgents}
          />,
          <Button
            key="handoff"
            icon={<ApartmentOutlined />}
            onClick={() => navigate('/agents/handoff-editor')}
          >
            Handoff 编排
          </Button>,
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/agents/new')}
          >
            创建 Agent
          </Button>,
        ]}
      />
    </div>
  );
};

export default AgentListPage;
