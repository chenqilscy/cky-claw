import { useState } from 'react';
import { Button, App, Input, Space, Tag, Upload, Dropdown, Modal } from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  HistoryOutlined,
  ApartmentOutlined,
  DownloadOutlined,
  UploadOutlined,
  EditOutlined,
  DeleteOutlined,
  MoreOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { useNavigate } from 'react-router-dom';
import type { AgentConfig } from '../../services/agentService';
import { agentService } from '../../services/agentService';
import { useAgentList, useDeleteAgent } from '../../hooks/useAgentQueries';
import { PageContainer } from '../../components/PageContainer';
import { RobotOutlined } from '@ant-design/icons';

const AgentListPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const { data: listData, isLoading: loading, refetch: fetchAgents } = useAgentList({
    search: search || undefined,
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const data = listData?.data ?? [];
  const total = listData?.total ?? 0;

  const deleteMutation = useDeleteAgent();

  const handleDelete = async (name: string) => {
    try {
      await deleteMutation.mutateAsync(name);
      message.success('删除成功');
    } catch {
      message.error('删除失败');
    }
  };

  const handleExport = async (name: string) => {
    try {
      await agentService.exportAgent(name, 'yaml');
      message.success('导出成功');
    } catch {
      message.error('导出失败');
    }
  };

  const handleImport = async (file: File) => {
    try {
      await agentService.importAgent(file);
      message.success('导入成功');
      void fetchAgents();
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导入失败');
    }
  };

  const columns: ProColumns<AgentConfig>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 180,
      render: (_, record) => (
        <a onClick={() => navigate(`/agents/${record.name}/edit`)}>{record.name}</a>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
      width: 200,
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
      width: 160,
      fixed: 'right',
      render: (_, record) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => navigate(`/agents/${record.name}/edit`)}
          >
            编辑
          </Button>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'versions',
                  icon: <HistoryOutlined />,
                  label: '版本历史',
                  onClick: () => navigate(`/agents/${record.id}/versions`),
                },
                {
                  key: 'export',
                  icon: <DownloadOutlined />,
                  label: '导出',
                  onClick: () => void handleExport(record.name),
                },
                { type: 'divider' },
                {
                  key: 'delete',
                  icon: <DeleteOutlined />,
                  label: '删除',
                  danger: true,
                  onClick: () => {
                    Modal.confirm({
                      title: '确认删除',
                      content: `确定要删除 Agent「${record.name}」吗？此操作不可恢复。`,
                      okText: '确认删除',
                      okButtonProps: { danger: true },
                      cancelText: '取消',
                      onOk: () => handleDelete(record.name),
                    });
                  },
                },
              ],
            }}
            trigger={['click']}
          >
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer
      title="Agent 管理"
      icon={<RobotOutlined />}
      description="创建和管理你的 AI Agent，配置模型、工具和安全策略"
      extra={[
        <Button
          key="handoff"
          icon={<ApartmentOutlined />}
          onClick={() => navigate('/agents/handoff-editor')}
        >
          Handoff 编排
        </Button>,
        <Upload
          key="import"
          accept=".yaml,.yml,.json"
          showUploadList={false}
          beforeUpload={(file) => {
            void handleImport(file);
            return false;
          }}
        >
          <Button icon={<UploadOutlined />}>导入</Button>
        </Upload>,
        <Button
          key="create"
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/agents/new')}
        >
          创建 Agent
        </Button>,
      ]}
    >
      <ProTable<AgentConfig>
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        search={false}
        options={false}
        scroll={{ x: 'max-content' }}
        cardProps={{ bodyStyle: { padding: 0 } }}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
        }}
        toolBarRender={() => [
          <Input.Search
            key="search"
            placeholder="搜索名称 / 描述"
            allowClear
            onSearch={(v) => { setSearch(v); setPagination((p) => ({ ...p, current: 1 })); }}
            style={{ width: 260 }}
          />,
          <Button
            key="reload"
            type="text"
            icon={<ReloadOutlined />}
            onClick={() => void fetchAgents()}
          />,
        ]}
      />
    </PageContainer>
  );
};

export default AgentListPage;
