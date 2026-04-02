import { useCallback, useEffect, useMemo, useState } from 'react';
import { message, Card, Row, Col, Statistic, DatePicker, Input, Space, Tag, Segmented } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { tokenUsageService } from '../../services/tokenUsageService';
import type {
  TokenUsageLog,
  TokenUsageSummaryItem,
  TokenUsageByUserItem,
  TokenUsageByModelItem,
  TokenUsageListParams,
  TokenUsageSummaryParams,
  SummaryGroupBy,
} from '../../services/tokenUsageService';

const { RangePicker } = DatePicker;

type AnySummaryItem = TokenUsageSummaryItem | TokenUsageByUserItem | TokenUsageByModelItem;

const GROUP_BY_OPTIONS: { label: string; value: SummaryGroupBy }[] = [
  { label: 'Agent + 模型', value: 'agent_model' },
  { label: '按用户', value: 'user' },
  { label: '按模型', value: 'model' },
];

const RunListPage: React.FC = () => {
  const [data, setData] = useState<TokenUsageLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [summaryData, setSummaryData] = useState<AnySummaryItem[]>([]);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [agentFilter, setAgentFilter] = useState<string>('');
  const [modelFilter, setModelFilter] = useState<string>('');
  const [timeRange, setTimeRange] = useState<[string, string] | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [groupBy, setGroupBy] = useState<SummaryGroupBy>('agent_model');

  const buildParams = useCallback((): TokenUsageListParams => {
    const params: TokenUsageListParams = {
      limit: pagination.pageSize,
      offset: (pagination.current - 1) * pagination.pageSize,
    };
    if (agentFilter) params.agent_name = agentFilter;
    if (modelFilter) params.model = modelFilter;
    if (timeRange) {
      params.start_time = timeRange[0];
      params.end_time = timeRange[1];
    }
    return params;
  }, [pagination, agentFilter, modelFilter, timeRange]);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await tokenUsageService.list(buildParams());
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取 Token 消耗记录失败');
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  const fetchSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const params: TokenUsageSummaryParams = { group_by: groupBy };
      if (agentFilter) params.agent_name = agentFilter;
      if (modelFilter) params.model = modelFilter;
      if (timeRange) {
        params.start_time = timeRange[0];
        params.end_time = timeRange[1];
      }
      const res = await tokenUsageService.summary(params);
      setSummaryData(res.data);
    } catch {
      message.error('获取汇总数据失败');
    } finally {
      setSummaryLoading(false);
    }
  }, [agentFilter, modelFilter, timeRange, groupBy]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const totalTokens = summaryData.reduce((sum, item) => sum + item.total_tokens, 0);
  const totalCalls = summaryData.reduce((sum, item) => sum + item.call_count, 0);
  const totalPrompt = summaryData.reduce((sum, item) => sum + item.total_prompt_tokens, 0);
  const totalCompletion = summaryData.reduce((sum, item) => sum + item.total_completion_tokens, 0);

  const columns: ProColumns<TokenUsageLog>[] = [
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 160,
      render: (_, record) => <Tag color="blue">{record.agent_name}</Tag>,
    },
    {
      title: '模型',
      dataIndex: 'model',
      width: 180,
      ellipsis: true,
    },
    {
      title: '输入 Token',
      dataIndex: 'prompt_tokens',
      width: 120,
      sorter: (a, b) => a.prompt_tokens - b.prompt_tokens,
      render: (_, record) => record.prompt_tokens.toLocaleString(),
    },
    {
      title: '输出 Token',
      dataIndex: 'completion_tokens',
      width: 120,
      sorter: (a, b) => a.completion_tokens - b.completion_tokens,
      render: (_, record) => record.completion_tokens.toLocaleString(),
    },
    {
      title: '总 Token',
      dataIndex: 'total_tokens',
      width: 120,
      sorter: (a, b) => a.total_tokens - b.total_tokens,
      render: (_, record) => <strong>{record.total_tokens.toLocaleString()}</strong>,
    },
    {
      title: 'Trace ID',
      dataIndex: 'trace_id',
      width: 180,
      ellipsis: true,
      copyable: true,
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      width: 180,
      render: (_, record) => new Date(record.timestamp).toLocaleString('zh-CN'),
    },
  ];

  const summaryColumns = useMemo((): ProColumns<AnySummaryItem>[] => {
    const shared: ProColumns<AnySummaryItem>[] = [
      {
        title: '输入 Token',
        dataIndex: 'total_prompt_tokens',
        render: (_, record) => record.total_prompt_tokens.toLocaleString(),
      },
      {
        title: '输出 Token',
        dataIndex: 'total_completion_tokens',
        render: (_, record) => record.total_completion_tokens.toLocaleString(),
      },
      {
        title: '总 Token',
        dataIndex: 'total_tokens',
        render: (_, record) => <strong>{record.total_tokens.toLocaleString()}</strong>,
      },
      {
        title: '调用次数',
        dataIndex: 'call_count',
        render: (_, record) => record.call_count.toLocaleString(),
      },
    ];

    const dimensionCols: ProColumns<AnySummaryItem>[] = [];
    if (groupBy === 'agent_model') {
      dimensionCols.push(
        {
          title: 'Agent',
          dataIndex: 'agent_name',
          render: (_, record) => <Tag color="blue">{(record as TokenUsageSummaryItem).agent_name}</Tag>,
        },
        {
          title: '模型',
          dataIndex: 'model',
        },
      );
    } else if (groupBy === 'user') {
      dimensionCols.push({
        title: '用户 ID',
        dataIndex: 'user_id',
        render: (_, record) => (record as TokenUsageByUserItem).user_id ?? <Tag>未知用户</Tag>,
      });
    } else {
      dimensionCols.push({
        title: '模型',
        dataIndex: 'model',
        render: (_, record) => <Tag color="green">{(record as TokenUsageByModelItem).model}</Tag>,
      });
    }
    return [...dimensionCols, ...shared];
  }, [groupBy]);

  const summaryRowKey = useCallback((record: AnySummaryItem) => {
    if (groupBy === 'agent_model') {
      const r = record as TokenUsageSummaryItem;
      return `${r.agent_name}-${r.model}`;
    } else if (groupBy === 'user') {
      return `user-${(record as TokenUsageByUserItem).user_id ?? 'null'}`;
    }
    return `model-${(record as TokenUsageByModelItem).model}`;
  }, [groupBy]);

  const summaryTitle = useMemo(() => {
    const labels: Record<SummaryGroupBy, string> = {
      agent_model: 'Agent Token 汇总（按 Agent + 模型）',
      user: 'Token 汇总（按用户）',
      model: 'Token 汇总（按模型）',
    };
    return labels[groupBy];
  }, [groupBy]);

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card loading={summaryLoading} size="small">
            <Statistic title="总调用次数" value={totalCalls} />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={summaryLoading} size="small">
            <Statistic title="总 Token" value={totalTokens} />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={summaryLoading} size="small">
            <Statistic title="输入 Token" value={totalPrompt} />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={summaryLoading} size="small">
            <Statistic title="输出 Token" value={totalCompletion} />
          </Card>
        </Col>
      </Row>

      <ProTable<AnySummaryItem>
        headerTitle={summaryTitle}
        rowKey={summaryRowKey}
        columns={summaryColumns}
        dataSource={summaryData}
        loading={summaryLoading}
        search={false}
        pagination={false}
        size="small"
        style={{ marginBottom: 16 }}
        toolBarRender={() => [
          <Segmented
            key="groupBy"
            options={GROUP_BY_OPTIONS}
            value={groupBy}
            onChange={(v) => setGroupBy(v as SummaryGroupBy)}
          />,
        ]}
      />

      <ProTable<TokenUsageLog>
        headerTitle="Token 消耗明细"
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        search={false}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total,
          showSizeChanger: true,
          onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
        }}
        toolBarRender={() => [
          <Space key="filters">
            <Input.Search
              placeholder="按 Agent 名称筛选"
              allowClear
              onSearch={(v) => {
                setAgentFilter(v);
                setPagination((p) => ({ ...p, current: 1 }));
              }}
              style={{ width: 200 }}
            />
            <Input.Search
              placeholder="按模型筛选"
              allowClear
              onSearch={(v) => {
                setModelFilter(v);
                setPagination((p) => ({ ...p, current: 1 }));
              }}
              style={{ width: 200 }}
            />
            <RangePicker
              showTime
              onChange={(_, dateStrings) => {
                if (dateStrings[0] && dateStrings[1]) {
                  setTimeRange(dateStrings as [string, string]);
                } else {
                  setTimeRange(null);
                }
                setPagination((p) => ({ ...p, current: 1 }));
              }}
            />
          </Space>,
          <ReloadOutlined
            key="reload"
            style={{ cursor: 'pointer', fontSize: 16 }}
            onClick={() => { fetchList(); fetchSummary(); }}
          />,
        ]}
      />
    </div>
  );
};

export default RunListPage;
