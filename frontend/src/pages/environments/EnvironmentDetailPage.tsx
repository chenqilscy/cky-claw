import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Tag, Table, Button, App, Space, Modal, Form, Input, Select, Typography } from 'antd';
import { ArrowLeftOutlined, RocketOutlined, RollbackOutlined } from '@ant-design/icons';
import { environmentService } from '../../services/environmentService';
import type { Environment, BindingResponse } from '../../services/environmentService';

const { Text } = Typography;

const EnvironmentDetailPage: React.FC = () => {
  const { envName } = useParams<{ envName: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [env, setEnv] = useState<Environment | null>(null);
  const [agents, setAgents] = useState<BindingResponse[]>([]);
  const [loading, setLoading] = useState(false);

  // 发布弹窗
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishForm] = Form.useForm();

  // Diff 弹窗
  const [diffOpen, setDiffOpen] = useState(false);
  const [diffForm] = Form.useForm();
  const [diffResult, setDiffResult] = useState<{ snapshot_env1: Record<string, unknown>; snapshot_env2: Record<string, unknown> } | null>(null);

  // 环境列表用于 diff 选择
  const [allEnvs, setAllEnvs] = useState<Environment[]>([]);

  const fetchDetail = async () => {
    if (!envName) return;
    setLoading(true);
    try {
      const [envData, agentData] = await Promise.all([
        environmentService.get(envName),
        environmentService.listAgents(envName),
      ]);
      setEnv(envData);
      setAgents(agentData.data);
    } catch {
      message.error('获取环境详情失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
    environmentService.list().then((res) => setAllEnvs(res.data)).catch(() => {});
  }, [envName]); // eslint-disable-line react-hooks/exhaustive-deps

  const handlePublish = async () => {
    try {
      const values = await publishForm.validateFields();
      if (!envName) return;
      await environmentService.publishAgent(envName, values.agent_name, {
        version_id: values.version_id || undefined,
        notes: values.notes || '',
      });
      message.success('发布成功');
      setPublishOpen(false);
      fetchDetail();
    } catch {
      message.error('发布失败');
    }
  };

  const handleRollback = async (agentName: string) => {
    if (!envName) return;
    try {
      await environmentService.rollbackAgent(envName, agentName, { notes: '从详情页回滚' });
      message.success('回滚成功');
      fetchDetail();
    } catch {
      message.error('回滚失败');
    }
  };

  const handleDiff = async () => {
    try {
      const values = await diffForm.validateFields();
      const result = await environmentService.diff(values.agent_name, values.env1, values.env2);
      setDiffResult({ snapshot_env1: result.snapshot_env1, snapshot_env2: result.snapshot_env2 });
    } catch {
      message.error('对比失败');
    }
  };

  const agentColumns = [
    {
      title: 'Agent Config ID',
      dataIndex: 'agent_config_id',
      ellipsis: true,
    },
    {
      title: '版本 ID',
      dataIndex: 'version_id',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (val: boolean) => val ? <Tag color="green">活跃</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '发布时间',
      dataIndex: 'published_at',
      width: 180,
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: '备注',
      dataIndex: 'notes',
      ellipsis: true,
    },
    {
      title: '操作',
      width: 100,
      render: (_: unknown, record: BindingResponse) => (
        <Button
          type="link"
          size="small"
          icon={<RollbackOutlined />}
          onClick={() => handleRollback(record.agent_config_id)}
        >
          回滚
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/environments')}>
          返回列表
        </Button>
        <Button type="primary" icon={<RocketOutlined />} onClick={() => { publishForm.resetFields(); setPublishOpen(true); }}>
          发布 Agent
        </Button>
        <Button onClick={() => { diffForm.resetFields(); setDiffResult(null); setDiffOpen(true); }}>
          环境对比
        </Button>
      </Space>

      {env && (
        <Card title={<><Tag color={env.color}>{env.display_name}</Tag> {env.name}</>} style={{ marginBottom: 16 }}>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="描述">{env.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="受保护">{env.is_protected ? '是' : '否'}</Descriptions.Item>
            <Descriptions.Item label="排序">{env.sort_order}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{new Date(env.created_at).toLocaleString()}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Card title="已发布 Agent">
        <Table
          rowKey="id"
          columns={agentColumns}
          dataSource={agents}
          loading={loading}
          pagination={false}
          size="small"
        />
      </Card>

      {/* 发布弹窗 */}
      <Modal title="发布 Agent" open={publishOpen} onOk={handlePublish} onCancel={() => setPublishOpen(false)} destroyOnHidden>
        <Form form={publishForm} layout="vertical">
          <Form.Item name="agent_name" label="Agent 名称" rules={[{ required: true, message: '请输入 Agent 名称' }]}>
            <Input placeholder="code-reviewer" />
          </Form.Item>
          <Form.Item name="version_id" label="版本 ID（可选，默认最新）">
            <Input placeholder="留空则使用最新版本" />
          </Form.Item>
          <Form.Item name="notes" label="发布备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Diff 弹窗 */}
      <Modal
        title="环境对比"
        open={diffOpen}
        onCancel={() => setDiffOpen(false)}
        width={800}
        footer={[
          <Button key="cancel" onClick={() => setDiffOpen(false)}>关闭</Button>,
          <Button key="compare" type="primary" onClick={handleDiff}>对比</Button>,
        ]}
        destroyOnHidden
      >
        <Form form={diffForm} layout="inline" style={{ marginBottom: 16 }}>
          <Form.Item name="agent_name" label="Agent" rules={[{ required: true }]}>
            <Input placeholder="Agent 名称" style={{ width: 160 }} />
          </Form.Item>
          <Form.Item name="env1" label="环境 1" rules={[{ required: true }]}>
            <Select style={{ width: 120 }} placeholder="选择环境">
              {allEnvs.map((e) => (
                <Select.Option key={e.name} value={e.name}>
                  <Tag color={e.color}>{e.display_name}</Tag>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="env2" label="环境 2" rules={[{ required: true }]}>
            <Select style={{ width: 120 }} placeholder="选择环境">
              {allEnvs.map((e) => (
                <Select.Option key={e.name} value={e.name}>
                  <Tag color={e.color}>{e.display_name}</Tag>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
        {diffResult && (
          <div style={{ display: 'flex', gap: 16 }}>
            <Card title="环境 1 快照" style={{ flex: 1 }} size="small">
              <Text>
                <pre style={{ fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
                  {JSON.stringify(diffResult.snapshot_env1, null, 2)}
                </pre>
              </Text>
            </Card>
            <Card title="环境 2 快照" style={{ flex: 1 }} size="small">
              <Text>
                <pre style={{ fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
                  {JSON.stringify(diffResult.snapshot_env2, null, 2)}
                </pre>
              </Text>
            </Card>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default EnvironmentDetailPage;
