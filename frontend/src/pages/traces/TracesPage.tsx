import { useCallback, useEffect, useState } from 'react';
import {
  message,
  Card,
  Tag,
  Space,
  Input,
  Modal,
  Tree,
  Descriptions,
  Typography,
  Row,
  Col,
  Statistic,
} from 'antd';
import {
  ApartmentOutlined,
  ClockCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { traceService } from '../../services/traceService';
import type { TraceItem, SpanItem } from '../../services/traceService';
import type { DataNode } from 'antd/es/tree';

const { Text } = Typography;

const SPAN_TYPE_COLORS: Record<string, string> = {
  agent: 'blue',
  llm: 'green',
  tool: 'orange',
  handoff: 'purple',
  guardrail: 'red',
};

interface SpanTreeNode extends DataNode {
  span: SpanItem;
}

function buildSpanTree(spans: SpanItem[]): SpanTreeNode[] {
  const map = new Map<string, SpanTreeNode>();
  const roots: SpanTreeNode[] = [];

  for (const span of spans) {
    const duration = span.end_time
      ? new Date(span.end_time).getTime() - new Date(span.start_time).getTime()
      : null;
    const durationText = duration !== null ? `${duration}ms` : '-';

    map.set(span.id, {
      key: span.id,
      title: (
        <Space size={4}>
          <Tag color={SPAN_TYPE_COLORS[span.type] || 'default'} style={{ margin: 0 }}>
            {span.type}
          </Tag>
          <Text strong>{span.name}</Text>
          {span.model && <Text type="secondary">({span.model})</Text>}
          <Text type="secondary">
            <ClockCircleOutlined /> {durationText}
          </Text>
          {span.token_usage && (
            <Text type="secondary">
              tokens: {span.token_usage.total_tokens}
            </Text>
          )}
          <Tag color={span.status === 'completed' ? 'success' : 'error'}>{span.status}</Tag>
        </Space>
      ),
      span,
      children: [],
    });
  }

  for (const span of spans) {
    const node = map.get(span.id);
    if (!node) continue;

    if (span.parent_span_id && map.has(span.parent_span_id)) {
      const parent = map.get(span.parent_span_id)!;
      (parent.children as SpanTreeNode[]).push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

const TracesPage: React.FC = () => {
  const [data, setData] = useState<TraceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [agentFilter, setAgentFilter] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // Detail modal
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailTrace, setDetailTrace] = useState<TraceItem | null>(null);
  const [detailSpans, setDetailSpans] = useState<SpanItem[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedSpan, setSelectedSpan] = useState<SpanItem | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number | undefined> = {
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      };
      if (agentFilter) params.agent_name = agentFilter;
      const res = await traceService.list(params);
      setData(res.items);
      setTotal(res.total);
    } catch {
      message.error('获取 Trace 列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination, agentFilter]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openDetail = async (traceId: string) => {
    setDetailVisible(true);
    setDetailLoading(true);
    setSelectedSpan(null);
    try {
      const res = await traceService.detail(traceId);
      setDetailTrace(res.trace);
      setDetailSpans(res.spans);
    } catch {
      message.error('获取 Trace 详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const columns: ProColumns<TraceItem>[] = [
    {
      title: 'Trace ID',
      dataIndex: 'id',
      width: 200,
      ellipsis: true,
      copyable: true,
      render: (_, record) => (
        <a onClick={() => openDetail(record.id)}>{record.id.slice(0, 12)}...</a>
      ),
    },
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 160,
      render: (_, record) =>
        record.agent_name ? <Tag color="blue">{record.agent_name}</Tag> : '-',
    },
    {
      title: 'Workflow',
      dataIndex: 'workflow_name',
      width: 140,
    },
    {
      title: 'Span 数',
      dataIndex: 'span_count',
      width: 90,
      sorter: (a, b) => a.span_count - b.span_count,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (_, record) => (
        <Tag color={record.status === 'completed' ? 'success' : 'error'}>{record.status}</Tag>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      width: 180,
      render: (_, record) => new Date(record.start_time).toLocaleString('zh-CN'),
    },
    {
      title: '耗时',
      width: 100,
      render: (_, record) => {
        if (!record.end_time) return '-';
        const ms = new Date(record.end_time).getTime() - new Date(record.start_time).getTime();
        return `${ms}ms`;
      },
    },
  ];

  const spanTree = buildSpanTree(detailSpans);
  const allKeys = detailSpans.map((s) => s.id);

  return (
    <>
      <Card
        title={
          <Space>
            <ApartmentOutlined />
            Trace 追踪
          </Space>
        }
        extra={
          <Input
            placeholder="按 Agent 筛选"
            prefix={<SearchOutlined />}
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            onPressEnter={() => setPagination((p) => ({ ...p, current: 1 }))}
            allowClear
            style={{ width: 200 }}
          />
        }
      >
        <ProTable<TraceItem>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          search={false}
          toolBarRender={false}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>

      <Modal
        title={
          <Space>
            <ApartmentOutlined />
            Trace 详情
          </Space>
        }
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={960}
        loading={detailLoading}
      >
        {detailTrace && (
          <>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Statistic title="Span 数" value={detailTrace.span_count} />
              </Col>
              <Col span={6}>
                <Statistic title="状态" value={detailTrace.status} />
              </Col>
              <Col span={6}>
                <Statistic title="Agent" value={detailTrace.agent_name || '-'} />
              </Col>
              <Col span={6}>
                <Statistic title="Workflow" value={detailTrace.workflow_name} />
              </Col>
            </Row>

            <Card title="Span 树" size="small" style={{ marginBottom: 16 }}>
              {spanTree.length > 0 ? (
                <Tree
                  showLine
                  defaultExpandAll
                  expandedKeys={allKeys}
                  treeData={spanTree}
                  onSelect={(_, info) => {
                    const node = info.node as SpanTreeNode;
                    setSelectedSpan(node.span);
                  }}
                />
              ) : (
                <Text type="secondary">无 Span 数据</Text>
              )}
            </Card>

            {selectedSpan && (
              <Card title={`Span 详情: ${selectedSpan.name}`} size="small">
                <Descriptions column={2} size="small" bordered>
                  <Descriptions.Item label="ID">{selectedSpan.id}</Descriptions.Item>
                  <Descriptions.Item label="类型">
                    <Tag color={SPAN_TYPE_COLORS[selectedSpan.type] || 'default'}>
                      {selectedSpan.type}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={selectedSpan.status === 'completed' ? 'success' : 'error'}>
                      {selectedSpan.status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="模型">{selectedSpan.model || '-'}</Descriptions.Item>
                  <Descriptions.Item label="开始时间">
                    {new Date(selectedSpan.start_time).toLocaleString('zh-CN')}
                  </Descriptions.Item>
                  <Descriptions.Item label="结束时间">
                    {selectedSpan.end_time
                      ? new Date(selectedSpan.end_time).toLocaleString('zh-CN')
                      : '-'}
                  </Descriptions.Item>
                  {selectedSpan.token_usage && (
                    <>
                      <Descriptions.Item label="输入 Token">
                        {selectedSpan.token_usage.prompt_tokens}
                      </Descriptions.Item>
                      <Descriptions.Item label="输出 Token">
                        {selectedSpan.token_usage.completion_tokens}
                      </Descriptions.Item>
                    </>
                  )}
                  {selectedSpan.input && (
                    <Descriptions.Item label="输入" span={2}>
                      <pre style={{ margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
                        {JSON.stringify(selectedSpan.input, null, 2)}
                      </pre>
                    </Descriptions.Item>
                  )}
                  {selectedSpan.output && (
                    <Descriptions.Item label="输出" span={2}>
                      <pre style={{ margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
                        {JSON.stringify(selectedSpan.output, null, 2)}
                      </pre>
                    </Descriptions.Item>
                  )}
                </Descriptions>
              </Card>
            )}
          </>
        )}
      </Modal>
    </>
  );
};

export default TracesPage;
