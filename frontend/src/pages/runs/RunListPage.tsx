import { useMemo, useState, useCallback } from 'react';
import { Card, Row, Col, Statistic, DatePicker, Input, Space, Tag, Segmented, Button, App } from 'antd';
import { ReloadOutlined, DownloadOutlined, BarChartOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import type {
  TokenUsageLog,
  TokenUsageSummaryItem,
  TokenUsageByUserItem,
  TokenUsageByModelItem,
  TokenUsageListParams,
  SummaryGroupBy,
} from '../../services/tokenUsageService';
import { useTokenUsageList, useTokenUsageSummary } from '../../hooks/useTokenUsageQueries';

const { RangePicker } = DatePicker;

type AnySummaryItem = TokenUsageSummaryItem | TokenUsageByUserItem | TokenUsageByModelItem;

const GROUP_BY_OPTIONS: { label: string; value: SummaryGroupBy }[] = [
  { label: 'Agent + 模型', value: 'agent_model' },
  { label: '按用户', value: 'user' },
  { label: '按模型', value: 'model' },
];

const RunListPage: React.FC = () => {
  const { message } = App.useApp();
  const [agentFilter, setAgentFilter] = useState<string>('');
  const [modelFilter, setModelFilter] = useState<string>('');
  const [timeRange, setTimeRange] = useState<[string, string] | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [groupBy, setGroupBy] = useState<SummaryGroupBy>('agent_model');
  const [exporting, setExporting] = useState(false);

  const handleExportCSV = useCallback(async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (agentFilter) params.set('agent_name', agentFilter);
      if (modelFilter) params.set('model', modelFilter);
      if (timeRange) {
        params.set('start_time', timeRange[0]);
        params.set('end_time', timeRange[1]);
      }
      const token = localStorage.getItem('kasaya_token');
      const resp = await fetch(`/api/v1/export/token-usage?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error(`导出失败: ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `token_usage_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      void message.error(err instanceof Error ? err.message : '导出失败');
    } finally {
      setExporting(false);
    }
  }, [agentFilter, modelFilter, timeRange, message]);

  // TanStack Query
  const listParams: TokenUsageListParams = {
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  };
  if (agentFilter) listParams.agent_name = agentFilter;
  if (modelFilter) listParams.model = modelFilter;
  if (timeRange) {
    listParams.start_time = timeRange[0];
    listParams.end_time = timeRange[1];
  }

  const { data: listData, isLoading: loading, refetch: refetchList } = useTokenUsageList(listParams);
  const data = listData?.data ?? [];
  const total = listData?.total ?? 0;

  const summaryParams = {
    group_by: groupBy,
    ...(agentFilter ? { agent_name: agentFilter } : {}),
    ...(modelFilter ? { model: modelFilter } : {}),
    ...(timeRange ? { start_time: timeRange[0], end_time: timeRange[1] } : {}),
  };
  const { data: summaryResponse, isLoading: summaryLoading, refetch: refetchSummary } = useTokenUsageSummary(summaryParams);
  const summaryData = (summaryResponse?.data ?? []) as AnySummaryItem[];

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

  const summaryRowKey = (record: AnySummaryItem) => {
    if (groupBy === 'agent_model') {
      const r = record as TokenUsageSummaryItem;
      return `${r.agent_name}-${r.model}`;
    } else if (groupBy === 'user') {
      return `user-${(record as TokenUsageByUserItem).user_id ?? 'null'}`;
    }
    return `model-${(record as TokenUsageByModelItem).model}`;
  };

  const summaryTitle = useMemo(() => {
    const labels: Record<SummaryGroupBy, string> = {
      agent_model: 'Agent Token 汇总（按 Agent + 模型）',
      user: 'Token 汇总（按用户）',
      model: 'Token 汇总（按模型）',
    };
    return labels[groupBy];
  }, [groupBy]);

  return (
    <PageContainer
      title="执行记录"
      icon={<BarChartOutlined />}
      description="Token 用量统计与多维度调用分析"
    >
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
            onClick={() => { void refetchList(); void refetchSummary(); }}
          />,
          <Button
            key="export"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={() => { void handleExportCSV(); }}
          >
            导出 CSV
          </Button>,
        ]}
      />
    </PageContainer>
  );
};

export default RunListPage;
