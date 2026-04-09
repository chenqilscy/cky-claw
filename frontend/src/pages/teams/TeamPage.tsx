import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Select, Tag, Button, Space, Popconfirm, Tooltip } from 'antd';
import {
  DeleteOutlined, EditOutlined,
  TeamOutlined, ApartmentOutlined,
} from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import type { TeamConfig, TeamConfigCreate, TeamConfigUpdate } from '../../services/teamService';
import {
  useTeamList,
  useCreateTeam,
  useUpdateTeam,
  useDeleteTeam,
} from '../../hooks/useTeamQueries';
import { CrudTable } from '../../components';
import type { CrudTableActions } from '../../components';

const { TextArea } = Input;

import { PROTOCOL_LABELS as protocolLabel, PROTOCOL_TAG_COLORS as protocolColor } from '../../constants/colors';

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<TeamConfig>,
  navigate: ReturnType<typeof useNavigate>,
): ProColumns<TeamConfig>[] => [
  {
    title: '名称',
    dataIndex: 'name',
    width: 160,
    render: (_, record) => <strong>{record.name}</strong>,
  },
  {
    title: '协作协议',
    dataIndex: 'protocol',
    width: 120,
    render: (_, record) => (
      <Tag color={protocolColor[record.protocol] || 'default'}>
        {protocolLabel[record.protocol] || record.protocol}
      </Tag>
    ),
  },
  {
    title: '成员数',
    width: 80,
    render: (_, record) => record.member_agent_ids.length,
  },
  {
    title: '描述',
    dataIndex: 'description',
    ellipsis: true,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 180,
    render: (_, record) => new Date(record.created_at).toLocaleString(),
  },
  {
    title: '操作',
    width: 140,
    render: (_, record) => (
      <Space size="small">
        <Tooltip title="查看拓扑">
          <Button type="text" icon={<ApartmentOutlined />} onClick={() => navigate(`/teams/flow?id=${record.id}`)} />
        </Tooltip>
        <Tooltip title="编辑">
          <Button type="text" icon={<EditOutlined />} onClick={() => actions.openEdit(record)} />
        </Tooltip>
        <Popconfirm title="确认删除？" onConfirm={() => actions.handleDelete(record.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    ),
  },
];

/* ---- 表单渲染 ---- */

const renderForm = (_form: FormInstance, editing: TeamConfig | null) => (
  <>
    <Form.Item name="name" label="团队名称" rules={[{ required: true, message: '请输入名称' }]}>
      <Input maxLength={64} placeholder="如: research-team" disabled={!!editing} />
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
  </>
);

/* ---- 页面组件 ---- */

const TeamPage: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const queryResult = useTeamList({
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
    search: search || undefined,
  });
  const createMutation = useCreateTeam();
  const updateMutation = useUpdateTeam();
  const deleteMutation = useDeleteTeam();

  return (
    <CrudTable<
      TeamConfig,
      TeamConfigCreate,
      { id: string; data: TeamConfigUpdate }
    >
      title="Agent 团队管理"
      icon={<TeamOutlined />}
      queryResult={queryResult}
      createMutation={createMutation}
      updateMutation={updateMutation}
      deleteMutation={deleteMutation}
      createButtonText="创建团队"
      modalTitle={(editing) => (editing ? '编辑团队' : '创建团队')}
      columns={(actions) => buildColumns(actions, navigate)}
      renderForm={renderForm}
      createDefaults={{ protocol: 'SEQUENTIAL', member_agent_ids_str: '', config_json: '{}' }}
      toFormValues={(record) => ({
        name: record.name,
        description: record.description,
        protocol: record.protocol,
        member_agent_ids_str: record.member_agent_ids.join(', '),
        coordinator_agent_id: record.coordinator_agent_id ?? '',
        config_json: JSON.stringify(record.config, null, 2),
      })}
      toCreatePayload={(values) => {
        const memberIds = (values.member_agent_ids_str as string)
          .split(',').map((s: string) => s.trim()).filter(Boolean);
        const config = values.config_json ? JSON.parse(values.config_json as string) : {};
        return {
          name: values.name as string,
          description: (values.description as string) || '',
          protocol: values.protocol as string,
          member_agent_ids: memberIds,
          coordinator_agent_id: (values.coordinator_agent_id as string) || null,
          config,
        };
      }}
      toUpdatePayload={(values, record) => {
        const memberIds = (values.member_agent_ids_str as string)
          .split(',').map((s: string) => s.trim()).filter(Boolean);
        const config = values.config_json ? JSON.parse(values.config_json as string) : {};
        return {
          id: record.id,
          data: {
            name: values.name as string,
            description: (values.description as string) || '',
            protocol: values.protocol as string,
            member_agent_ids: memberIds,
            coordinator_agent_id: (values.coordinator_agent_id as string) || null,
            config,
          },
        };
      }}
      pagination={pagination}
      onPaginationChange={(current, pageSize) => setPagination({ current, pageSize })}
      extraToolbar={
        <Input.Search
          placeholder="搜索团队名称"
          allowClear
          onSearch={(v) => { setSearch(v); setPagination((p) => ({ ...p, current: 1 })); }}
          style={{ width: 200 }}
        />
      }
      showRefresh
    />
  );
};

export default TeamPage;
