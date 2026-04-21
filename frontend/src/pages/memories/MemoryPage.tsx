import { useState, useMemo } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Slider,
  Timeline,
} from 'antd';
import {
  SearchOutlined,
  BulbOutlined,
  DatabaseOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import type {
  MemoryItem,
  MemoryCreateParams,
  MemoryUpdateParams,
} from '../../services/memoryService';
import {
  useMemoryList,
  useCreateMemory,
  useUpdateMemory,
  useDeleteMemory,
  useSearchMemory,
} from '../../hooks/useMemoryQueries';
import { CrudTable, PageContainer, buildActionColumn } from '../../components';
import type { CrudTableActions } from '../../components';

const { TextArea } = Input;

const TYPE_OPTIONS = [
  { label: '用户档案', value: 'user_profile' },
  { label: '历史摘要', value: 'history_summary' },
  { label: '结构化事实', value: 'structured_fact' },
];

const TYPE_COLORS: Record<string, string> = {
  user_profile: 'blue',
  history_summary: 'green',
  structured_fact: 'orange',
};

const TYPE_LABELS: Record<string, string> = {
  user_profile: '用户档案',
  history_summary: '历史摘要',
  structured_fact: '结构化事实',
};

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<MemoryItem>,
): ProColumns<MemoryItem>[] => [
  {
    title: '类型',
    dataIndex: 'type',
    width: 120,
    render: (_, record) => (
      <Tag color={TYPE_COLORS[record.type] ?? 'default'}>
        {TYPE_LABELS[record.type] ?? record.type}
      </Tag>
    ),
  },
  {
    title: '内容',
    dataIndex: 'content',
    ellipsis: true,
  },
  {
    title: '置信度',
    dataIndex: 'confidence',
    width: 100,
    render: (_, record) => (
      <Tag color={record.confidence >= 0.7 ? 'green' : record.confidence >= 0.4 ? 'orange' : 'red'}>
        {record.confidence.toFixed(2)}
      </Tag>
    ),
    sorter: (a, b) => a.confidence - b.confidence,
  },
  {
    title: '用户',
    dataIndex: 'user_id',
    width: 120,
    ellipsis: true,
  },
  {
    title: 'Agent',
    dataIndex: 'agent_name',
    width: 120,
    render: (v) => v || '-',
  },
  {
    title: '标签',
    dataIndex: 'tags',
    width: 160,
    render: (_, record) =>
      record.tags && record.tags.length > 0
        ? record.tags.map((t) => <Tag key={t} color="purple">{t}</Tag>)
        : '-',
  },
  {
    title: '访问次数',
    dataIndex: 'access_count',
    width: 90,
    sorter: (a, b) => a.access_count - b.access_count,
  },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    width: 180,
    render: (v) => new Date(v as string).toLocaleString('zh-CN'),
    sorter: (a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime(),
  },
  buildActionColumn<MemoryItem>(actions),
];

/* ---- 表单 ---- */

const renderForm = (_form: FormInstance, editing: MemoryItem | null) => (
  <>
    {!editing && (
      <Form.Item name="user_id" label="用户 ID" rules={[{ required: true, message: '请输入用户 ID' }]}>
        <Input placeholder="用户标识" />
      </Form.Item>
    )}
    <Form.Item name="type" label="类型" rules={[{ required: true }]}>
      <Select options={TYPE_OPTIONS} />
    </Form.Item>
    <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入记忆内容' }]}>
      <TextArea rows={4} placeholder="记忆内容" maxLength={10000} showCount />
    </Form.Item>
    <Form.Item name="confidence" label="置信度">
      <Slider min={0} max={1} step={0.01} marks={{ 0: '0', 0.5: '0.5', 1: '1' }} />
    </Form.Item>
    <Form.Item name="tags" label="标签">
      <Select mode="tags" placeholder="输入标签后按 Enter（可多个）" tokenSeparators={[',']} />
    </Form.Item>
    {!editing && (
      <Form.Item name="agent_name" label="Agent 名称">
        <Input placeholder="可选" />
      </Form.Item>
    )}
  </>
);

/* ---- 页面组件 ---- */

const MemoryPage: React.FC = () => {
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [filters, setFilters] = useState<{ user_id?: string; type?: string; agent_name?: string }>({});
  const [viewMode, setViewMode] = useState<'table' | 'timeline'>('table');

  // Search Modal
  const [searchVisible, setSearchVisible] = useState(false);
  const [searchForm] = Form.useForm();
  const [searchResults, setSearchResults] = useState<MemoryItem[]>([]);

  const queryResult = useMemoryList({
    ...filters,
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const createMutation = useCreateMemory();
  const updateMutation = useUpdateMemory();
  const deleteMutation = useDeleteMemory();
  const searchMutation = useSearchMemory();

  /* ---- 统计数据 ---- */
  const memories = queryResult.data?.data ?? [];
  const total = queryResult.data?.total ?? 0;

  const typeDistribution = useMemo(() => {
    const map: Record<string, number> = {};
    memories.forEach((m) => { map[m.type] = (map[m.type] || 0) + 1; });
    return Object.entries(map).map(([name, value]) => ({
      name: TYPE_LABELS[name] ?? name, value,
    }));
  }, [memories]);

  const avgConfidence = useMemo(() => {
    if (memories.length === 0) return 0;
    return memories.reduce((sum, m) => sum + m.confidence, 0) / memories.length;
  }, [memories]);

  const typePieOption = useMemo(() => ({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: typeDistribution.map((d) => ({
        value: d.value, name: d.name,
        itemStyle: { color: TYPE_COLORS[Object.entries(TYPE_LABELS).find(([, v]) => v === d.name)?.[0] ?? ''] ?? '#1677ff' },
      })),
      label: { show: true, formatter: '{b}: {c}' },
    }],
  }), [typeDistribution]);

  const confidenceBarOption = useMemo(() => {
    const buckets: number[] = [0, 0, 0, 0, 0]; // [0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0]
    memories.forEach((m) => {
      const i = Math.min(Math.floor(m.confidence * 5), 4);
      buckets[i] = (buckets[i] ?? 0) + 1;
    });
    return {
      tooltip: {},
      xAxis: { type: 'category' as const, data: ['0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0'] },
      yAxis: { type: 'value' as const },
      series: [{
        type: 'bar',
        data: buckets,
        itemStyle: { color: '#1677ff' },
      }],
    };
  }, [memories]);

  const handleSearch = async () => {
    try {
      const values = await searchForm.validateFields();
      const results = await searchMutation.mutateAsync({
        user_id: values.user_id,
        query: values.query,
        limit: values.limit ?? 10,
      });
      setSearchResults(results);
    } catch {
      // validation or API error
    }
  };

  /** 搜索结果表列（复用 buildColumns 但去掉 user_id 列） */
  const searchResultColumns: ProColumns<MemoryItem>[] = [
    { title: '类型', dataIndex: 'type', width: 120, render: (_, r) => <Tag color={TYPE_COLORS[r.type] ?? 'default'}>{TYPE_LABELS[r.type] ?? r.type}</Tag> },
    { title: '内容', dataIndex: 'content', ellipsis: true },
    { title: '置信度', dataIndex: 'confidence', width: 100, render: (_, r) => <Tag color={r.confidence >= 0.7 ? 'green' : r.confidence >= 0.4 ? 'orange' : 'red'}>{r.confidence.toFixed(2)}</Tag> },
    { title: 'Agent', dataIndex: 'agent_name', width: 120, render: (v) => v || '-' },
    { title: '更新时间', dataIndex: 'updated_at', width: 180, render: (v) => new Date(v as string).toLocaleString('zh-CN') },
  ];

  return (
    <PageContainer
      title="记忆管理"
      icon={<BulbOutlined />}
      description="管理 Agent 记忆（情景 / 语义 / 程序型），支持向量搜索"
    >
      {/* ---- 统计概览 ---- */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card size="small"><Statistic title="记忆总数" value={total} prefix={<DatabaseOutlined />} /></Card>
        </Col>
        <Col span={4}>
          <Card size="small"><Statistic title="当前页" value={memories.length} /></Card>
        </Col>
        <Col span={4}>
          <Card size="small"><Statistic title="平均置信度" value={avgConfidence} precision={2} /></Card>
        </Col>
        <Col span={6}>
          <Card size="small" styles={{ body: { padding: 8 } }}>
            <ReactECharts option={typePieOption} style={{ height: 120 }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" styles={{ body: { padding: 8 } }}>
            <ReactECharts option={confidenceBarOption} style={{ height: 120 }} />
          </Card>
        </Col>
      </Row>

      {/* ---- 视图切换 ---- */}
      <Space style={{ marginBottom: 16 }}>
        <Button
          type={viewMode === 'table' ? 'primary' : 'default'}
          icon={<DatabaseOutlined />}
          onClick={() => setViewMode('table')}
        >
          表格
        </Button>
        <Button
          type={viewMode === 'timeline' ? 'primary' : 'default'}
          icon={<HistoryOutlined />}
          onClick={() => setViewMode('timeline')}
        >
          时间线
        </Button>
      </Space>

      {/* ---- 时间线视图 ---- */}
      {viewMode === 'timeline' && (
        <Card style={{ marginBottom: 24 }}>
          {memories.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 24, color: '#999' }}>暂无记忆数据</div>
          ) : (
            <Timeline
              items={memories
                .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
                .map((m) => ({
                  color: TYPE_COLORS[m.type] ?? 'blue',
                  children: (
                    <div>
                      <Tag color={TYPE_COLORS[m.type] ?? 'default'}>{TYPE_LABELS[m.type] ?? m.type}</Tag>
                      <Tag color={m.confidence >= 0.7 ? 'green' : m.confidence >= 0.4 ? 'orange' : 'red'}>
                        {m.confidence.toFixed(2)}
                      </Tag>
                      {m.agent_name && <Tag>{m.agent_name}</Tag>}
                      <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                        {new Date(m.updated_at).toLocaleString('zh-CN')}
                      </span>
                      <div style={{ marginTop: 4 }}>{m.content}</div>
                    </div>
                  ),
                }))}
            />
          )}
        </Card>
      )}

      {/* ---- 表格视图 ---- */}
      {viewMode === 'table' && (
      <CrudTable<
        MemoryItem,
        MemoryCreateParams,
        { id: string; data: MemoryUpdateParams }
      >
        hideTitle
        mobileHiddenColumns={['tags', 'access_count', 'updated_at']}
        title="记忆管理"
        queryResult={queryResult}
        createMutation={createMutation}
        updateMutation={updateMutation}
        deleteMutation={deleteMutation}
        createButtonText="新建记忆"
        modalTitle={(editing) => (editing ? '编辑记忆' : '新建记忆')}
        columns={buildColumns}
        renderForm={renderForm}
        createDefaults={{ type: 'structured_fact', confidence: 1.0 }}
        toFormValues={(record) => ({
          type: record.type,
          content: record.content,
          confidence: record.confidence,
          user_id: record.user_id,
          agent_name: record.agent_name,
          tags: record.tags ?? [],
        })}
        toCreatePayload={(values) => ({
          type: values.type as string,
          content: values.content as string,
          confidence: (values.confidence as number) ?? 1.0,
          user_id: values.user_id as string,
          agent_name: values.agent_name as string | undefined,
          tags: (values.tags as string[] | undefined) ?? [],
        })}
        toUpdatePayload={(values, record) => ({
          id: record.id,
          data: {
            content: values.content as string,
            confidence: values.confidence as number,
            type: values.type as string,
            tags: (values.tags as string[] | undefined) ?? [],
          },
        })}
        extraToolbar={
          <Button icon={<SearchOutlined />} onClick={() => setSearchVisible(true)}>
            搜索记忆
          </Button>
        }
        beforeTable={
          <Space style={{ marginBottom: 16 }}>
            <Input
              placeholder="按用户 ID 筛选"
              allowClear
              style={{ width: 200 }}
              onChange={(e) => setFilters((prev) => ({ ...prev, user_id: e.target.value || undefined }))}
            />
            <Select
              placeholder="按类型筛选"
              allowClear
              style={{ width: 160 }}
              options={TYPE_OPTIONS}
              onChange={(v) => setFilters((prev) => ({ ...prev, type: v }))}
            />
            <Input
              placeholder="按 Agent 筛选"
              allowClear
              style={{ width: 200 }}
              onChange={(e) => setFilters((prev) => ({ ...prev, agent_name: e.target.value || undefined }))}
            />
          </Space>
        }
        pagination={pagination}
        onPaginationChange={(current, pageSize) => setPagination({ current, pageSize })}
        showRefresh
      />
      )}

      {/* Search Modal */}
      <Modal
        title="搜索记忆"
        open={searchVisible}
        onCancel={() => setSearchVisible(false)}
        footer={null}
        width={700}
        destroyOnHidden
      >
        <Form form={searchForm} layout="inline" style={{ marginBottom: 16 }}>
          <Form.Item name="user_id" rules={[{ required: true, message: '用户 ID' }]}>
            <Input placeholder="用户 ID" />
          </Form.Item>
          <Form.Item name="query" rules={[{ required: true, message: '关键词' }]}>
            <Input placeholder="搜索关键词" />
          </Form.Item>
          <Form.Item name="limit">
            <InputNumber placeholder="数量" min={1} max={100} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} loading={searchMutation.isPending} onClick={handleSearch}>
              搜索
            </Button>
          </Form.Item>
        </Form>
        {searchResults.length > 0 && (
          <ProTable<MemoryItem>
            rowKey="id"
            columns={searchResultColumns}
            dataSource={searchResults}
            search={false}
            options={false}
            pagination={false}
          />
        )}
      </Modal>
    </PageContainer>
  );
};

export default MemoryPage;
