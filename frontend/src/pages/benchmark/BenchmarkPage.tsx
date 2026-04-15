import { useState, useMemo } from 'react';
import {
  Card, Row, Col, Statistic, Tag, Table, Tabs, Space, App,
  Progress, Button, Modal, Form, Input, Select, Descriptions, Empty,
} from 'antd';
import {
  ExperimentOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  TrophyOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { PageContainer } from '../../components/PageContainer';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { benchmarkService } from '../../services/benchmarkService';
import type { BenchmarkSuiteItem, BenchmarkRunItem } from '../../services/benchmarkService';

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
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null);
  const [reportRun, setReportRun] = useState<BenchmarkRunItem | null>(null);

  const { data: dashboard } = useQuery({
    queryKey: ['benchmark-dashboard'],
    queryFn: () => benchmarkService.getDashboard(),
  });

  const { data: suitesData, isLoading: suitesLoading } = useQuery({
    queryKey: ['benchmark-suites'],
    queryFn: () => benchmarkService.listSuites({ limit: 100 }),
  });

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['benchmark-runs', selectedSuiteId],
    queryFn: () => benchmarkService.listRuns({
      limit: 100,
      ...(selectedSuiteId ? { suite_id: selectedSuiteId } : {}),
    }),
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

  /* ─── ECharts 配置 ─── */

  /** 通过率饼图。 */
  const passPieOption = useMemo(() => {
    if (!reportRun) return {};
    return {
      title: { text: '用例通过率', left: 'center' },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: [
          { value: reportRun.passed_cases, name: '通过', itemStyle: { color: '#52c41a' } },
          { value: reportRun.failed_cases, name: '失败', itemStyle: { color: '#ff4d4f' } },
          { value: reportRun.error_cases, name: '异常', itemStyle: { color: '#faad14' } },
        ],
      }],
    };
  }, [reportRun]);

  /** 评分仪表盘。 */
  const gaugeOption = useMemo(() => {
    if (!reportRun) return {};
    return {
      series: [{
        type: 'gauge',
        detail: { formatter: '{value}', fontSize: 20 },
        data: [{ value: +(reportRun.overall_score * 100).toFixed(1), name: '综合评分' }],
        max: 100,
        axisLine: { lineStyle: { width: 15, color: [[0.3, '#ff4d4f'], [0.7, '#faad14'], [1, '#52c41a']] } },
      }],
    };
  }, [reportRun]);

  /** 维度雷达图（如果 dimension_summaries 存在）。 */
  const radarOption = useMemo(() => {
    if (!reportRun?.dimension_summaries) return null;
    const dims = reportRun.dimension_summaries as Record<string, { score?: number }>;
    const keys = Object.keys(dims);
    if (keys.length === 0) return null;
    return {
      title: { text: '维度评分', left: 'center' },
      radar: { indicator: keys.map((k) => ({ name: k, max: 1 })) },
      series: [{
        type: 'radar',
        data: [{ value: keys.map((k) => dims[k]?.score ?? 0), name: '评分' }],
      }],
    };
  }, [reportRun]);

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
            type="link"
            icon={<BarChartOutlined />}
            onClick={() => {
              setSelectedSuiteId(record.id);
              // 自动切换到 Runs tab（通过 tab activeKey state 实现联动）
            }}
          >
            查看运行
          </Button>
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
    {
      title: '操作', key: 'actions',
      render: (_: unknown, record: BenchmarkRunItem) => (
        <Button
          size="small"
          type="link"
          icon={<BarChartOutlined />}
          onClick={() => setReportRun(record)}
          disabled={record.status !== 'completed'}
        >
          报告
        </Button>
      ),
    },
  ];

  /* ─── Tab 状态联动 ─── */
  const [activeTab, setActiveTab] = useState('suites');

  return (
    <PageContainer
      title="Agent 评测基准"
      icon={<ExperimentOutlined />}
      description="评测套件管理、运行与评分报告"
    >
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
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key);
          if (key === 'suites') setSelectedSuiteId(null);
        }}
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
                  onRow={(record) => ({
                    onDoubleClick: () => {
                      setSelectedSuiteId(record.id);
                      setActiveTab('runs');
                    },
                  })}
                />
              </>
            ),
          },
          {
            key: 'runs',
            label: selectedSuiteId
              ? `运行（${suitesData?.data?.find((s) => s.id === selectedSuiteId)?.name ?? ''}）`
              : '全部运行',
            children: (
              <>
                {selectedSuiteId && (
                  <Space style={{ marginBottom: 16 }}>
                    <Tag color="blue">
                      筛选套件: {suitesData?.data?.find((s) => s.id === selectedSuiteId)?.name ?? selectedSuiteId}
                    </Tag>
                    <Button size="small" onClick={() => setSelectedSuiteId(null)}>查看全部</Button>
                  </Space>
                )}
                <Table
                  rowKey="id"
                  columns={runColumns}
                  dataSource={runsData?.data ?? []}
                  loading={runsLoading}
                  pagination={{ pageSize: 10 }}
                />
              </>
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

      {/* 运行报告弹窗 */}
      <Modal
        title="评测报告"
        open={!!reportRun}
        onCancel={() => setReportRun(null)}
        footer={null}
        width={900}
        destroyOnHidden
      >
        {reportRun && (
          <>
            <Descriptions bordered size="small" column={3} style={{ marginBottom: 24 }}>
              <Descriptions.Item label="状态">
                <Tag color={statusColors[reportRun.status]}>{reportRun.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="用例总数">{reportRun.total_cases}</Descriptions.Item>
              <Descriptions.Item label="通过">
                <Tag color="green">{reportRun.passed_cases}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="失败">
                <Tag color="red">{reportRun.failed_cases}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="异常">
                <Tag color="orange">{reportRun.error_cases}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="综合评分">{reportRun.overall_score.toFixed(4)}</Descriptions.Item>
              <Descriptions.Item label="Token">{reportRun.total_tokens}</Descriptions.Item>
              <Descriptions.Item label="耗时">{reportRun.total_latency_ms.toFixed(0)} ms</Descriptions.Item>
              <Descriptions.Item label="完成时间">
                {reportRun.finished_at ? new Date(reportRun.finished_at).toLocaleString() : '—'}
              </Descriptions.Item>
            </Descriptions>

            <Row gutter={16}>
              <Col span={12}>
                <ReactECharts option={passPieOption} style={{ height: 280 }} />
              </Col>
              <Col span={12}>
                <ReactECharts option={gaugeOption} style={{ height: 280 }} />
              </Col>
            </Row>

            {radarOption && (
              <Row style={{ marginTop: 16 }}>
                <Col span={24}>
                  <ReactECharts option={radarOption} style={{ height: 320 }} />
                </Col>
              </Row>
            )}

            {!radarOption && !reportRun.dimension_summaries && (
              <Empty description="无维度评分数据" style={{ marginTop: 16 }} />
            )}
          </>
        )}
      </Modal>
    </PageContainer>
  );
};

export default BenchmarkPage;
