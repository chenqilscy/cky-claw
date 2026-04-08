import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card, Button, Space, Modal, Form, Input, Select, Tag, message,
  Popconfirm, Empty, Table, Typography, Tooltip,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined,
  TeamOutlined, ApartmentOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TeamConfig, TeamConfigCreate } from '../../services/teamService';
import { listTeams, createTeam, updateTeam, deleteTeam } from '../../services/teamService';

const { TextArea } = Input;
const { Text } = Typography;

const protocolLabel: Record<string, string> = {
  SEQUENTIAL: '顺序执行',
  PARALLEL: '并行执行',
  COORDINATOR: '协调者模式',
};

const protocolColor: Record<string, string> = {
  SEQUENTIAL: 'blue',
  PARALLEL: 'green',
  COORDINATOR: 'purple',
};

const TeamPage: React.FC = () => {
  const navigate = useNavigate();
  const [teams, setTeams] = useState<TeamConfig[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<TeamConfig | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listTeams({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        search: search || undefined,
      });
      setTeams(res.data);
      setTotal(res.total);
    } catch {
      message.error('加载团队列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCreate = () => {
    setEditRecord(null);
    form.resetFields();
    form.setFieldsValue({ protocol: 'SEQUENTIAL', member_agent_ids_str: '', config_json: '{}' });
    setModalOpen(true);
  };

  const handleEdit = (record: TeamConfig) => {
    setEditRecord(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      protocol: record.protocol,
      member_agent_ids_str: record.member_agent_ids.join(', '),
      coordinator_agent_id: record.coordinator_agent_id ?? '',
      config_json: JSON.stringify(record.config, null, 2),
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTeam(id);
      message.success('已删除');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const memberIds = (values.member_agent_ids_str as string)
        .split(',')
        .map((s: string) => s.trim())
        .filter(Boolean);
      let configObj = {};
      try {
        configObj = values.config_json ? JSON.parse(values.config_json) : {};
      } catch {
        message.error('扩展配置必须是合法 JSON');
        return;
      }
      const payload: TeamConfigCreate = {
        name: values.name,
        description: values.description || '',
        protocol: values.protocol,
        member_agent_ids: memberIds,
        coordinator_agent_id: values.coordinator_agent_id || null,
        config: configObj,
      };
      if (editRecord) {
        await updateTeam(editRecord.id, payload);
        message.success('更新成功');
      } else {
        await createTeam(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch {
      // form validation error
    }
  };

  const columns: ColumnsType<TeamConfig> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: '协作协议',
      dataIndex: 'protocol',
      key: 'protocol',
      render: (val: string) => (
        <Tag color={protocolColor[val] || 'default'}>
          {protocolLabel[val] || val}
        </Tag>
      ),
    },
    {
      title: '成员数',
      key: 'members',
      render: (_: unknown, record: TeamConfig) => record.member_agent_ids.length,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: TeamConfig) => (
        <Space size="small">
          <Tooltip title="查看拓扑">
            <Button type="text" icon={<ApartmentOutlined />} onClick={() => navigate(`/teams/flow?id=${record.id}`)} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <TeamOutlined />
          <span>Agent 团队管理</span>
        </Space>
      }
      extra={
        <Space>
          <Input.Search
            placeholder="搜索团队名称"
            allowClear
            onSearch={(v) => { setSearch(v); setPage(1); }}
            style={{ width: 200 }}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            创建团队
          </Button>
        </Space>
      }
    >
      {teams.length === 0 && !loading ? (
        <Empty description="暂无团队配置" />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={teams}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
            showTotal: (t) => `共 ${t} 个团队`,
          }}
        />
      )}

      <Modal
        title={editRecord ? '编辑团队' : '创建团队'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="团队名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input maxLength={64} placeholder="如: research-team" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} maxLength={2000} placeholder="团队功能描述" />
          </Form.Item>
          <Form.Item name="protocol" label="协作协议" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'SEQUENTIAL', label: '顺序执行 (Sequential)' },
                { value: 'PARALLEL', label: '并行执行 (Parallel)' },
                { value: 'COORDINATOR', label: '协调者模式 (Coordinator)' },
              ]}
            />
          </Form.Item>
          <Form.Item name="member_agent_ids_str" label="成员 Agent ID（逗号分隔）">
            <TextArea rows={2} placeholder="agent-1, agent-2, agent-3" />
          </Form.Item>
          <Form.Item name="coordinator_agent_id" label="协调者 Agent ID（仅 Coordinator 模式）">
            <Input maxLength={64} placeholder="coordinator-agent" />
          </Form.Item>
          <Form.Item name="config_json" label="扩展配置 (JSON)">
            <TextArea rows={4} placeholder='{"max_rounds": 5}' />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default TeamPage;
