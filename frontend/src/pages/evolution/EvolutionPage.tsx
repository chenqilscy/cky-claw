import { useEffect, useState } from 'react';
import {
  Card, Button, Space, Table, Tag, Modal, Form, Input, InputNumber,
  Select, message, Popconfirm, Typography, Tooltip, Progress,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, CheckOutlined, CloseOutlined,
  DeleteOutlined, RocketOutlined, RollbackOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type {
  EvolutionProposal,
  EvolutionProposalCreate,
} from '../../services/evolutionService';
import { evolutionService } from '../../services/evolutionService';

const { Text } = Typography;

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

const EvolutionPage: React.FC = () => {
  const [proposals, setProposals] = useState<EvolutionProposal[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filterAgent, setFilterAgent] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await evolutionService.list({
        agent_name: filterAgent || undefined,
        proposal_type: filterType || undefined,
        status: filterStatus || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setProposals(res.data);
      setTotal(res.total);
    } catch {
      message.error('加载进化建议失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [page, pageSize, filterAgent, filterType, filterStatus]);

  const handleApprove = async (id: string) => {
    try {
      await evolutionService.update(id, { status: 'approved' });
      message.success('已批准');
      fetchData();
    } catch {
      message.error('操作失败');
    }
  };

  const handleReject = async (id: string) => {
    try {
      await evolutionService.update(id, { status: 'rejected' });
      message.success('已拒绝');
      fetchData();
    } catch {
      message.error('操作失败');
    }
  };

  const handleApply = async (id: string) => {
    try {
      await evolutionService.update(id, { status: 'applied' });
      message.success('已应用');
      fetchData();
    } catch {
      message.error('操作失败');
    }
  };

  const handleRollback = async (id: string) => {
    try {
      await evolutionService.update(id, { status: 'rolled_back' });
      message.success('已回滚');
      fetchData();
    } catch {
      message.error('操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await evolutionService.delete(id);
      message.success('已删除');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleCreate = async (values: EvolutionProposalCreate) => {
    try {
      await evolutionService.create(values);
      message.success('建议已创建');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const columns: ColumnsType<EvolutionProposal> = [
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 120,
    },
    {
      title: '类型',
      dataIndex: 'proposal_type',
      width: 100,
      render: (v: string) => <Tag color={typeColor[v]}>{typeLabel[v] || v}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (v: string) => <Tag color={statusColor[v]}>{statusLabel[v] || v}</Tag>,
    },
    {
      title: '置信度',
      dataIndex: 'confidence_score',
      width: 120,
      render: (v: number) => <Progress percent={Math.round(v * 100)} size="small" />,
    },
    {
      title: '触发原因',
      dataIndex: 'trigger_reason',
      ellipsis: true,
      render: (v: string) => <Tooltip title={v}><Text>{v}</Text></Tooltip>,
    },
    {
      title: '评分变化',
      width: 120,
      render: (_: unknown, r: EvolutionProposal) => {
        if (r.eval_before !== null && r.eval_after !== null) {
          const delta = r.eval_after - r.eval_before;
          const color = delta >= 0 ? '#52c41a' : '#ff4d4f';
          return <Text style={{ color }}>{r.eval_before.toFixed(2)} → {r.eval_after.toFixed(2)}</Text>;
        }
        return <Text type="secondary">—</Text>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 180,
      render: (_: unknown, r: EvolutionProposal) => (
        <Space size="small">
          {r.status === 'pending' && (
            <>
              <Tooltip title="批准">
                <Button type="link" size="small" icon={<CheckOutlined />} onClick={() => handleApprove(r.id)} />
              </Tooltip>
              <Tooltip title="拒绝">
                <Button type="link" size="small" danger icon={<CloseOutlined />} onClick={() => handleReject(r.id)} />
              </Tooltip>
            </>
          )}
          {r.status === 'approved' && (
            <Tooltip title="应用">
              <Button type="link" size="small" icon={<RocketOutlined />} onClick={() => handleApply(r.id)} />
            </Tooltip>
          )}
          {r.status === 'applied' && (
            <Tooltip title="回滚">
              <Button type="link" size="small" danger icon={<RollbackOutlined />} onClick={() => handleRollback(r.id)} />
            </Tooltip>
          )}
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="进化建议"
      extra={
        <Space>
          <Input
            placeholder="Agent 名称"
            allowClear
            style={{ width: 140 }}
            value={filterAgent}
            onChange={(e) => { setFilterAgent(e.target.value); setPage(1); }}
          />
          <Select
            placeholder="类型"
            allowClear
            style={{ width: 120 }}
            value={filterType || undefined}
            onChange={(v) => { setFilterType(v || ''); setPage(1); }}
            options={Object.entries(typeLabel).map(([k, v]) => ({ label: v, value: k }))}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 110 }}
            value={filterStatus || undefined}
            onChange={(v) => { setFilterStatus(v || ''); setPage(1); }}
            options={Object.entries(statusLabel).map(([k, v]) => ({ label: v, value: k }))}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建建议
          </Button>
        </Space>
      }
    >
      <Table
        rowKey="id"
        columns={columns}
        dataSource={proposals}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (p, s) => { setPage(p); setPageSize(s); },
        }}
      />

      <Modal
        title="新建进化建议"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
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
        </Form>
      </Modal>
    </Card>
  );
};

export default EvolutionPage;
