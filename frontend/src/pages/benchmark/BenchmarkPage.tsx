import { useState } from 'react';
import {
  Card, Row, Col, Statistic, Tag, Table, Tabs, Typography, Space, App,
  Progress, Button, Modal, Form, Input, Select,
} from 'antd';
import {
  ExperimentOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { benchmarkService } from '../../services/benchmarkService';
import type { BenchmarkSuiteItem } from '../../services/benchmarkService';

const { Title } = Typography;

const statusColors: Record<string, string> = {
  pending: 'gold',
  running: 'blue',
  completed: 'green',
  failed: 'red',
};

const BenchmarkPage: React.FC = () => {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [suiteModalOpen, setSuiteModalOpen] = useState(false);
  const [suiteForm] = Form.useForm();

  const { data: dashboard } = useQuery({
    queryKey: ['benchmark-dashboard'],
    queryFn: () => benchmarkService.getDashboard(),
  });

  const { data: suitesData, isLoading: suitesLoading } = useQuery({
    queryKey: ['benchmark-suites'],
    queryFn: () => benchmarkService.listSuites({ limit: 100 }),
  });

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['benchmark-runs'],
    queryFn: () => benchmarkService.listRuns({ limit: 100 }),
  });

  const createSuiteMutation = useMutation({
    mutationFn: (body: { name: string; description?: string; agent_name?: string; model?: string; tags?: string[] }) =>
      benchmarkService.createSuite(body),
    onSuccess: () => {
      message.success('套件已创建');
      setSuiteModalOpen(false);
      suiteForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['benchmark-suites'] });
      queryClient.invalidateQueries({ queryKey: ['benchmark-dashboard'] });
    },
  });

  const deleteSuiteMutation = useMutation({
    mutationFn: (id: string) => benchmarkService.deleteSuite(id),
    onSuccess: () => {
      message.success('套件已删除');
      queryClient.invalidateQueries({ queryKey: ['benchmark-suites'] });
      queryClient.invalidateQueries({ queryKey: ['benchmark-dashboard'] });
    },
  });

  const createRunMutation = useMutation({
    mutationFn: (suiteId: string) => benchmarkService.createRun(suiteId),
    onSuccess: () => {
      message.success('运行已创建');
      queryClient.invalidateQueries({ queryKey: ['benchmark-runs'] });
      queryClient.invalidateQueries({ queryKey: ['benchmark-dashboard'] });
    },
  });

  /* ─── 表格列 ─── */

  const suiteColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: 'Agent', dataIndex: 'agent_name', key: 'agent_name' },
    { title: '模型', dataIndex: 'model', key: 'model' },
    {
      title: '标签', dataIndex: 'tags', key: 'tags',
      render: (tags: string[] | null) => tags?.map((t) => <Tag key={t}>{t}</Tag>) ?? '—',
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作', key: 'actions',
      render: (_: unknown, record: BenchmarkSuiteItem) => (
        <Space>
          <Button
            size="small"
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={() => createRunMutation.mutate(record.id)}
          >
            运行
          </Button>
          <Button
            size="small"
            danger
            onClick={() => deleteSuiteMutation.mutate(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const runColumns = [
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={statusColors[s] ?? 'default'}>{s}</Tag>,
    },
    { title: '用例总数', dataIndex: 'total_cases', key: 'total_cases' },
    {
      title: '通过率', dataIndex: 'pass_rate', key: 'pass_rate',
      render: (v: number) => <Progress percent={Math.round(v * 100)} size="small" />,
    },
    {
      title: '综合评分', dataIndex: 'overall_score', key: 'overall_score',
      render: (v: number) => v.toFixed(2),
    },
    { title: 'Token', dataIndex: 'total_tokens', key: 'total_tokens' },
    {
      title: '耗时(ms)', dataIndex: 'total_latency_ms', key: 'total_latency_ms',
      render: (v: number) => v.toFixed(0),
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}><ExperimentOutlined /> Agent 评测基准</Title>

      {/* Dashboard */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card><Statistic title="套件总数" value={dashboard?.total_suites ?? 0} prefix={<TrophyOutlined />} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="运行总数" value={dashboard?.total_runs ?? 0} prefix={<PlayCircleOutlined />} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="已完成" value={dashboard?.completed_runs ?? 0} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="平均评分" value={dashboard?.avg_score ?? 0} precision={4} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="平均通过率" value={(dashboard?.avg_pass_rate ?? 0) * 100} precision={1} suffix="%" />
          </Card>
        </Col>
      </Row>

      {/* Tabs: Suites / Runs */}
      <Tabs
        defaultActiveKey="suites"
        items={[
          {
            key: 'suites',
            label: '评测套件',
            children: (
              <>
                <div style={{ marginBottom: 16 }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setSuiteModalOpen(true)}>
                    创建套件
                  </Button>
                </div>
                <Table
                  rowKey="id"
                  columns={suiteColumns}
                  dataSource={suitesData?.data ?? []}
                  loading={suitesLoading}
                  pagination={{ pageSize: 10 }}
                />
              </>
            ),
          },
          {
            key: 'runs',
            label: '评测运行',
            children: (
              <Table
                rowKey="id"
                columns={runColumns}
                dataSource={runsData?.data ?? []}
                loading={runsLoading}
                pagination={{ pageSize: 10 }}
              />
            ),
          },
        ]}
      />

      {/* 创建套件弹窗 */}
      <Modal
        title="创建评测套件"
        open={suiteModalOpen}
        onCancel={() => setSuiteModalOpen(false)}
        onOk={() => suiteForm.submit()}
        confirmLoading={createSuiteMutation.isPending}
      >
        <Form
          form={suiteForm}
          layout="vertical"
          onFinish={(values) => createSuiteMutation.mutate(values)}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入套件名称' }]}>
            <Input placeholder="e.g. accuracy-v1" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="agent_name" label="Agent 名称">
            <Input />
          </Form.Item>
          <Form.Item name="model" label="模型">
            <Input placeholder="e.g. gpt-4" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default BenchmarkPage;
