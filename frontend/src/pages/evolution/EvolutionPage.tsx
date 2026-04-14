import { useState, useCallback } from 'react';
import {
  Button, Space, Tag, Input, InputNumber,
  Select, App, Typography, Tooltip, Progress, Form, Dropdown, Modal,
  theme,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  CheckOutlined, CloseOutlined,
  DeleteOutlined, RocketOutlined, RollbackOutlined, MoreOutlined,
} from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import type {
  EvolutionProposal,
  EvolutionProposalCreate,
  EvolutionProposalUpdate,
} from '../../services/evolutionService';
import {
  useEvolutionList,
  useCreateEvolution,
  useUpdateEvolution,
  useDeleteEvolution,
  useScanRollback,
} from '../../hooks/useEvolutionQueries';
import { CrudTable, PageContainer } from '../../components';
import type { CrudTableActions } from '../../components';

const { Text } = Typography;

type DesignToken = ReturnType<typeof theme.useToken>['token'];

const typeLabel: Record<string, string> = {
  instructions: '指令优化',
  tools: '工具调整',
  guardrails: '护栏优化',
  model: '模型切换',
  memory: '记忆管理',
};

const typeColor: Record<string, string> = {
  instructions: 'blue',
  tools: 'green',
  guardrails: 'orange',
  model: 'purple',
  memory: 'cyan',
};

const statusLabel: Record<string, string> = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
  applied: '已应用',
  rolled_back: '已回滚',
};

const statusColor: Record<string, string> = {
  pending: 'default',
  approved: 'processing',
  rejected: 'error',
  applied: 'success',
  rolled_back: 'warning',
};

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<EvolutionProposal>,
  onStatusChange: (id: string, status: string) => void,
  token: DesignToken,
): ProColumns<EvolutionProposal>[] => [
  {
    title: 'Agent',
    dataIndex: 'agent_name',
    width: 120,
  },
  {
    title: '类型',
    dataIndex: 'proposal_type',
    width: 100,
    render: (_, r) => <Tag color={typeColor[r.proposal_type]}>{typeLabel[r.proposal_type] || r.proposal_type}</Tag>,
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 100,
    render: (_, r) => <Tag color={statusColor[r.status]}>{statusLabel[r.status] || r.status}</Tag>,
  },
  {
    title: '置信度',
    dataIndex: 'confidence_score',
    width: 120,
    render: (_, r) => <Progress percent={Math.round(r.confidence_score * 100)} size="small" />,
  },
  {
    title: '触发原因',
    dataIndex: 'trigger_reason',
    ellipsis: true,
    render: (_, r) => <Tooltip title={r.trigger_reason}><Text>{r.trigger_reason}</Text></Tooltip>,
  },
  {
    title: '评分变化',
    width: 120,
    render: (_, r) => {
      if (r.eval_before !== null && r.eval_after !== null) {
        const delta = r.eval_after - r.eval_before;
        const color = delta >= 0 ? token.colorSuccess : token.colorError;
        return <Text style={{ color }}>{r.eval_before.toFixed(2)} → {r.eval_after.toFixed(2)}</Text>;
      }
      return <Text type="secondary">—</Text>;
    },
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 180,
    render: (_, r) => new Date(r.created_at).toLocaleString('zh-CN'),
  },
  {
    title: '操作',
    width: 180,
    render: (_, r) => {
      /* 状态条件化主操作 */
      let primaryBtn: React.ReactNode = null;
      if (r.status === 'pending') {
        primaryBtn = (
          <Tooltip title="批准">
            <Button type="link" size="small" icon={<CheckOutlined />} onClick={() => onStatusChange(r.id, 'approved')} />
          </Tooltip>
        );
      } else if (r.status === 'approved') {
        primaryBtn = (
          <Tooltip title="应用">
            <Button type="link" size="small" icon={<RocketOutlined />} onClick={() => onStatusChange(r.id, 'applied')} />
          </Tooltip>
        );
      } else if (r.status === 'applied') {
        primaryBtn = (
          <Tooltip title="回滚">
            <Button type="link" size="small" danger icon={<RollbackOutlined />} onClick={() => onStatusChange(r.id, 'rolled_back')} />
          </Tooltip>
        );
      }

      /* Dropdown 菜单项 */
      const menuItems: MenuProps['items'] = [];
      if (r.status === 'pending') {
        menuItems.push({ key: 'reject', label: '拒绝', icon: <CloseOutlined />, danger: true });
        menuItems.push({ type: 'divider', key: '__d' });
      }
      menuItems.push({ key: '__delete', label: '删除', icon: <DeleteOutlined />, danger: true });

      const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
        if (key === 'reject') {
          onStatusChange(r.id, 'rejected');
        } else if (key === '__delete') {
          Modal.confirm({
            title: '确认删除',
            content: `确定要删除该进化建议吗？此操作不可恢复。`,
            okText: '确认删除',
            okType: 'danger',
            onOk: () => actions.handleDelete(r.id),
          });
        }
      };

      return (
        <Space size={4}>
          {primaryBtn}
          <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }}>
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      );
    },
  },
];

/* ---- 表单 ---- */

const renderForm = (_form: FormInstance, _editing: EvolutionProposal | null) => (
  <>
    <Form.Item name="agent_name" label="Agent 名称" rules={[{ required: true }]}>
      <Input />
    </Form.Item>
    <Form.Item name="proposal_type" label="建议类型" rules={[{ required: true }]}>
      <Select options={Object.entries(typeLabel).map(([k, v]) => ({ label: v, value: k }))} />
    </Form.Item>
    <Form.Item name="trigger_reason" label="触发原因">
      <Input.TextArea rows={3} />
    </Form.Item>
    <Form.Item name="confidence_score" label="置信度" initialValue={0.5}>
      <InputNumber min={0} max={1} step={0.1} />
    </Form.Item>
  </>
);

/* ---- 页面组件 ---- */

const EvolutionPage: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [filterAgent, setFilterAgent] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const queryResult = useEvolutionList({
    agent_name: filterAgent || undefined,
    proposal_type: filterType || undefined,
    status: filterStatus || undefined,
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const createMutation = useCreateEvolution();
  const updateMutation = useUpdateEvolution();
  const deleteMutation = useDeleteEvolution();
  const scanRollbackMutation = useScanRollback();

  const handleStatusChange = useCallback(async (id: string, status: string) => {
    try {
      await updateMutation.mutateAsync({ id, data: { status } });
      message.success(statusLabel[status] ?? status);
    } catch {
      message.error('操作失败');
    }
  }, [updateMutation, message]);

  const handleScanRollback = useCallback(async () => {
    try {
      const result = await scanRollbackMutation.mutateAsync(0.1);
      if (result.rolled_back_count > 0) {
        message.warning(`已回滚 ${result.rolled_back_count} 条效果退化的建议`);
      } else {
        message.success('未发现需要回滚的建议');
      }
    } catch {
      message.error('扫描回滚失败');
    }
  }, [scanRollbackMutation, message]);

  return (
    <PageContainer
      title="进化建议"
      icon={<RocketOutlined />}
      description="管理 Agent 进化建议，自动扫描与回滚"
    >
    <CrudTable<
      EvolutionProposal,
      EvolutionProposalCreate,
      { id: string; data: EvolutionProposalUpdate }
    >
      hideTitle
      title="进化建议"
      queryResult={queryResult}
      createMutation={createMutation}
      updateMutation={updateMutation}
      deleteMutation={deleteMutation}
      createButtonText="新建建议"
      modalTitle={(editing) => (editing ? '编辑建议' : '新建进化建议')}
      columns={(actions) => buildColumns(actions, handleStatusChange, token)}
      renderForm={renderForm}
      toCreatePayload={(values) => values as unknown as EvolutionProposalCreate}
      toUpdatePayload={(values, record) => ({
        id: record.id,
        data: {
          status: values.status as string | undefined,
          eval_before: values.eval_before as number | undefined,
          eval_after: values.eval_after as number | undefined,
          metadata: values.metadata as Record<string, unknown> | undefined,
        },
      })}
      extraToolbar={
        <Space>
          <Input
            placeholder="Agent 名称"
            allowClear
            style={{ width: 140 }}
            value={filterAgent}
            onChange={(e) => { setFilterAgent(e.target.value); setPagination(p => ({ ...p, current: 1 })); }}
          />
          <Select
            placeholder="类型"
            allowClear
            style={{ width: 120 }}
            value={filterType || undefined}
            onChange={(v) => { setFilterType(v || ''); setPagination(p => ({ ...p, current: 1 })); }}
            options={Object.entries(typeLabel).map(([k, v]) => ({ label: v, value: k }))}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 110 }}
            value={filterStatus || undefined}
            onChange={(v) => { setFilterStatus(v || ''); setPagination(p => ({ ...p, current: 1 })); }}
            options={Object.entries(statusLabel).map(([k, v]) => ({ label: v, value: k }))}
          />
          <Button
              icon={<RollbackOutlined />}
              loading={scanRollbackMutation.isPending}
              onClick={() => {
                Modal.confirm({
                  title: '扫描回滚',
                  content: '扫描所有已应用建议，对评分退化超过 10% 的自动回滚。确认继续？',
                  okText: '确认扫描',
                  onOk: handleScanRollback,
                });
              }}
            >
              扫描回滚
            </Button>
        </Space>
      }
      pagination={pagination}
      onPaginationChange={(current, pageSize) => setPagination({ current, pageSize })}
      showRefresh
    />
    </PageContainer>
  );
};

export default EvolutionPage;
