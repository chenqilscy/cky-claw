import { useCallback, useEffect, useState } from 'react';
import {
  Card, Button, Space, Modal, Form, Input, InputNumber, Select, Tag, message,
  Table, Typography, Tabs, Statistic, Row, Col, Progress,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, StarOutlined, LikeOutlined,
  DislikeOutlined, BarChartOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type {
  RunEvaluation, RunEvaluationCreate,
  RunFeedback, RunFeedbackCreate,
  AgentQualitySummary,
} from '../../services/evaluationService';
import {
  listEvaluations, createEvaluation,
  listFeedbacks, createFeedback,
  getAgentQuality,
} from '../../services/evaluationService';

const { TextArea } = Input;
const { Text } = Typography;

const DIMENSIONS = [
  { key: 'accuracy', label: '准确性' },
  { key: 'relevance', label: '相关性' },
  { key: 'coherence', label: '连贯性' },
  { key: 'helpfulness', label: '实用性' },
  { key: 'safety', label: '安全性' },
  { key: 'efficiency', label: '效率' },
  { key: 'tool_usage', label: '工具使用' },
] as const;

const methodLabel: Record<string, string> = {
  manual: '人工评估',
  auto: '自动评估',
  llm_judge: 'LLM 评委',
};

const methodColor: Record<string, string> = {
  manual: 'blue',
  auto: 'green',
  llm_judge: 'purple',
};

const ratingIcon: Record<number, React.ReactNode> = {
  '-1': <DislikeOutlined style={{ color: '#ff4d4f' }} />,
  '0': <span style={{ color: '#faad14' }}>—</span>,
  '1': <LikeOutlined style={{ color: '#52c41a' }} />,
};

// ── 评估 Tab ──────────────────────────────────────

const EvaluationTab: React.FC = () => {
  const [evals, setEvals] = useState<RunEvaluation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filterAgentId, setFilterAgentId] = useState('');
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listEvaluations({
        agent_id: filterAgentId || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setEvals(res.data);
      setTotal(res.total);
    } catch {
      message.error('加载评估列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterAgentId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCreate = () => {
    form.resetFields();
    form.setFieldsValue({ eval_method: 'manual' });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: RunEvaluationCreate = {
        run_id: values.run_id,
        agent_id: values.agent_id || null,
        accuracy: values.accuracy ?? 0,
        relevance: values.relevance ?? 0,
        coherence: values.coherence ?? 0,
        helpfulness: values.helpfulness ?? 0,
        safety: values.safety ?? 0,
        efficiency: values.efficiency ?? 0,
        tool_usage: values.tool_usage ?? 0,
        eval_method: values.eval_method,
        evaluator: values.evaluator || '',
        comment: values.comment || '',
      };
      await createEvaluation(payload);
      message.success('评估已创建');
      setModalOpen(false);
      fetchData();
    } catch {
      // form validation
    }
  };

  const columns: ColumnsType<RunEvaluation> = [
    {
      title: 'Run ID',
      dataIndex: 'run_id',
      key: 'run_id',
      width: 120,
      render: (val: string) => <Text code>{val.length > 12 ? `${val.slice(0, 12)}...` : val}</Text>,
    },
    {
      title: '总分',
      dataIndex: 'overall_score',
      key: 'overall_score',
      width: 100,
      sorter: (a: RunEvaluation, b: RunEvaluation) => a.overall_score - b.overall_score,
      render: (val: number) => (
        <Text strong style={{ color: val >= 0.7 ? '#52c41a' : val >= 0.4 ? '#faad14' : '#ff4d4f' }}>
          {(val * 100).toFixed(0)}%
        </Text>
      ),
    },
    ...DIMENSIONS.map((d) => ({
      title: d.label,
      dataIndex: d.key,
      key: d.key,
      width: 80,
      render: (val: number) => <Progress percent={Math.round(val * 100)} size="small" showInfo={false} />,
    })),
    {
      title: '评估方式',
      dataIndex: 'eval_method',
      key: 'eval_method',
      width: 100,
      render: (val: string) => <Tag color={methodColor[val]}>{methodLabel[val] || val}</Tag>,
    },
    {
      title: '评语',
      dataIndex: 'comment',
      key: 'comment',
      ellipsis: true,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => new Date(val).toLocaleString(),
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="按 Agent ID 筛选"
          allowClear
          onSearch={(v) => { setFilterAgentId(v); setPage(1); }}
          style={{ width: 280 }}
        />
        <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建评估</Button>
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={evals}
        loading={loading}
        scroll={{ x: 1200 }}
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          showTotal: (t) => `共 ${t} 条评估`,
        }}
      />

      <Modal
        title="新建运行评估"
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="run_id" label="Run ID" rules={[{ required: true, message: '请输入 Run ID' }]}>
            <Input placeholder="运行记录 ID" />
          </Form.Item>
          <Form.Item name="agent_id" label="Agent ID">
            <Input placeholder="关联的 Agent ID（可选）" />
          </Form.Item>
          <Row gutter={16}>
            {DIMENSIONS.map((d) => (
              <Col span={8} key={d.key}>
                <Form.Item name={d.key} label={d.label} initialValue={0.5}>
                  <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            ))}
          </Row>
          <Form.Item name="eval_method" label="评估方式">
            <Select
              options={[
                { value: 'manual', label: '人工评估' },
                { value: 'auto', label: '自动评估' },
                { value: 'llm_judge', label: 'LLM 评委' },
              ]}
            />
          </Form.Item>
          <Form.Item name="evaluator" label="评估者">
            <Input placeholder="评估者名称" />
          </Form.Item>
          <Form.Item name="comment" label="评语">
            <TextArea rows={3} placeholder="对本次运行的评价" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

// ── 反馈 Tab ──────────────────────────────────────

const FeedbackTab: React.FC = () => {
  const [feedbacks, setFeedbacks] = useState<RunFeedback[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listFeedbacks({ limit: pageSize, offset: (page - 1) * pageSize });
      setFeedbacks(res.data);
      setTotal(res.total);
    } catch {
      message.error('加载反馈列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const tagsArr = values.tags_str
        ? (values.tags_str as string).split(',').map((s: string) => s.trim()).filter(Boolean)
        : [];
      const payload: RunFeedbackCreate = {
        run_id: values.run_id,
        rating: values.rating,
        comment: values.comment || '',
        tags: tagsArr,
      };
      await createFeedback(payload);
      message.success('反馈已提交');
      setModalOpen(false);
      fetchData();
    } catch {
      // form validation
    }
  };

  const columns: ColumnsType<RunFeedback> = [
    {
      title: 'Run ID',
      dataIndex: 'run_id',
      key: 'run_id',
      render: (val: string) => <Text code>{val.length > 12 ? `${val.slice(0, 12)}...` : val}</Text>,
    },
    {
      title: '评分',
      dataIndex: 'rating',
      key: 'rating',
      width: 80,
      render: (val: number) => ratingIcon[val] ?? val,
    },
    {
      title: '评论',
      dataIndex: 'comment',
      key: 'comment',
      ellipsis: true,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (val: string[]) => (
        <Space size={4} wrap>
          {(Array.isArray(val) ? val : []).map((t) => <Tag key={t}>{t}</Tag>)}
        </Space>
      ),
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => new Date(val).toLocaleString(),
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModalOpen(true); }}>
          提交反馈
        </Button>
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={feedbacks}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          showTotal: (t) => `共 ${t} 条反馈`,
        }}
      />

      <Modal
        title="提交用户反馈"
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="run_id" label="Run ID" rules={[{ required: true, message: '请输入 Run ID' }]}>
            <Input placeholder="运行记录 ID" />
          </Form.Item>
          <Form.Item name="rating" label="评分" rules={[{ required: true, message: '请选择评分' }]}>
            <Select
              options={[
                { value: 1, label: '👍 好' },
                { value: 0, label: '😐 一般' },
                { value: -1, label: '👎 差' },
              ]}
            />
          </Form.Item>
          <Form.Item name="comment" label="评论">
            <TextArea rows={3} placeholder="具体反馈内容" />
          </Form.Item>
          <Form.Item name="tags_str" label="标签（逗号分隔）">
            <Input placeholder="准确, 快速, 有用" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

// ── Agent 质量 Tab ────────────────────────────────

const QualityTab: React.FC = () => {
  const [agentId, setAgentId] = useState('');
  const [summary, setSummary] = useState<AgentQualitySummary | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchQuality = async () => {
    if (!agentId.trim()) {
      message.warning('请输入 Agent ID');
      return;
    }
    setLoading(true);
    try {
      const res = await getAgentQuality(agentId.trim());
      setSummary(res);
    } catch {
      message.error('获取质量数据失败');
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Space style={{ marginBottom: 24 }}>
        <Input
          placeholder="输入 Agent ID"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          style={{ width: 320 }}
          onPressEnter={fetchQuality}
        />
        <Button type="primary" icon={<BarChartOutlined />} onClick={fetchQuality} loading={loading}>
          查询质量
        </Button>
      </Space>

      {summary && (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card size="small">
                <Statistic title="评估次数" value={summary.eval_count} prefix={<StarOutlined />} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="综合得分"
                  value={summary.avg_overall * 100}
                  suffix="%"
                  valueStyle={{ color: summary.avg_overall >= 0.7 ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="反馈数" value={summary.feedback_count} prefix={<LikeOutlined />} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="好评率"
                  value={summary.positive_rate * 100}
                  suffix="%"
                  valueStyle={{ color: summary.positive_rate >= 0.6 ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="七维度评分" size="small">
            <Row gutter={[16, 12]}>
              {DIMENSIONS.map((d) => {
                const val = summary[`avg_${d.key}` as keyof AgentQualitySummary] as number;
                return (
                  <Col span={8} key={d.key}>
                    <Space>
                      <Text style={{ width: 60, display: 'inline-block' }}>{d.label}</Text>
                      <Progress percent={Math.round(val * 100)} style={{ width: 180 }} size="small" />
                    </Space>
                  </Col>
                );
              })}
            </Row>
          </Card>
        </>
      )}
    </>
  );
};

// ── 主页面 ────────────────────────────────────────

const EvaluationPage: React.FC = () => {
  return (
    <Card
      title={
        <Space>
          <StarOutlined />
          <span>Agent 评估与反馈</span>
        </Space>
      }
    >
      <Tabs
        items={[
          { key: 'evaluations', label: '运行评估', children: <EvaluationTab /> },
          { key: 'feedbacks', label: '用户反馈', children: <FeedbackTab /> },
          { key: 'quality', label: 'Agent 质量', children: <QualityTab /> },
        ]}
      />
    </Card>
  );
};

export default EvaluationPage;
