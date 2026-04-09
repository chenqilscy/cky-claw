import { useState } from 'react';
import { App, Tag, Badge, Modal, Descriptions, Input, Space, Card, Row, Col, Statistic, theme } from 'antd';
import { ReloadOutlined, PauseCircleOutlined, PlayCircleOutlined, EyeOutlined } from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { supervisionService } from '../../services/supervisionService';
import type {
  SupervisionSessionItem,
  SupervisionSessionDetail,
} from '../../services/supervisionService';
import {
  useSupervisionSessionList,
  usePauseSession,
  useResumeSession,
} from '../../hooks/useSupervisionQueries';

const STATUS_MAP: Record<string, { color: string; text: string }> = {
  active: { color: 'green', text: '运行中' },
  paused: { color: 'orange', text: '已暂停' },
  completed: { color: 'default', text: '已完成' },
};

const SupervisionPage: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const [agentFilter, setAgentFilter] = useState<string>('');
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailData, setDetailData] = useState<SupervisionSessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // TanStack Query
  const params = agentFilter ? { agent_name: agentFilter } : undefined;
  const { data: listData, isLoading: loading, refetch } = useSupervisionSessionList(params);
  const data = listData?.data ?? [];

  const pauseMutation = usePauseSession();
  const resumeMutation = useResumeSession();

  const handleViewDetail = async (sessionId: string) => {
    setDetailVisible(true);
    setDetailLoading(true);
    try {
      const detail = await supervisionService.getSessionDetail(sessionId);
      setDetailData(detail);
    } catch {
      message.error('获取会话详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const handlePause = async (sessionId: string) => {
    try {
      const res = await pauseMutation.mutateAsync({ sessionId });
      message.success(res.message);
      void refetch();
    } catch {
      message.error('暂停会话失败');
    }
  };

  const handleResume = async (sessionId: string) => {
    try {
      const res = await resumeMutation.mutateAsync({ sessionId });
      message.success(res.message);
      void refetch();
    } catch {
      message.error('恢复会话失败');
    }
  };

  const totalSessions = data.length;
  const activeSessions = data.filter((s) => s.status === 'active').length;
  const pausedSessions = data.filter((s) => s.status === 'paused').length;
  const totalTokens = data.reduce((sum, s) => sum + s.token_used, 0);

  const columns: ProColumns<SupervisionSessionItem>[] = [
    {
      title: '会话 ID',
      dataIndex: 'session_id',
      width: 140,
      ellipsis: true,
      copyable: true,
    },
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 160,
      render: (_, record) => <Tag color="blue">{record.agent_name}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (_, record) => {
        const s = STATUS_MAP[record.status] ?? { color: 'default', text: record.status };
        return <Badge color={s.color} text={s.text} />;
      },
    },
    {
      title: '标题',
      dataIndex: 'title',
      width: 200,
      ellipsis: true,
    },
    {
      title: 'Token 消耗',
      dataIndex: 'token_used',
      width: 120,
      sorter: (a, b) => a.token_used - b.token_used,
      render: (_, record) => record.token_used.toLocaleString(),
    },
    {
      title: '调用次数',
      dataIndex: 'call_count',
      width: 100,
      render: (_, record) => record.call_count.toLocaleString(),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
      render: (_, record) => new Date(record.updated_at).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) => (
        <Space>
          <a onClick={() => handleViewDetail(record.session_id)}>
            <EyeOutlined /> 详情
          </a>
          {record.status === 'active' && (
            <a onClick={() => handlePause(record.session_id)} style={{ color: token.colorWarning }}>
              <PauseCircleOutlined /> 暂停
            </a>
          )}
          {record.status === 'paused' && (
            <a onClick={() => handleResume(record.session_id)} style={{ color: token.colorSuccess }}>
              <PlayCircleOutlined /> 恢复
            </a>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="活跃会话" value={totalSessions} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="运行中" value={activeSessions} valueStyle={{ color: token.colorSuccess }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="已暂停" value={pausedSessions} valueStyle={{ color: token.colorWarning }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="总 Token 消耗" value={totalTokens} />
          </Card>
        </Col>
      </Row>

      <ProTable<SupervisionSessionItem>
        headerTitle="监督面板 — 活跃会话"
        rowKey="session_id"
        columns={columns}
        dataSource={data}
        loading={loading}
        search={false}
        pagination={false}
        toolBarRender={() => [
          <Input.Search
            key="filter"
            placeholder="按 Agent 名称筛选"
            allowClear
            onSearch={(v) => setAgentFilter(v)}
            style={{ width: 200 }}
          />,
          <ReloadOutlined
            key="reload"
            style={{ cursor: 'pointer', fontSize: 16 }}
            onClick={() => void refetch()}
          />,
        ]}
      />

      <Modal
        title="会话详情"
        open={detailVisible}
        onCancel={() => { setDetailVisible(false); setDetailData(null); }}
        footer={null}
        width={720}
        loading={detailLoading}
      >
        {detailData && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="会话 ID" span={2}>{detailData.session_id}</Descriptions.Item>
            <Descriptions.Item label="Agent">{detailData.agent_name}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Badge
                color={STATUS_MAP[detailData.status]?.color ?? 'default'}
                text={STATUS_MAP[detailData.status]?.text ?? detailData.status}
              />
            </Descriptions.Item>
            <Descriptions.Item label="Token 消耗">{detailData.token_used.toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="调用次数">{detailData.call_count.toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{new Date(detailData.created_at).toLocaleString('zh-CN')}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{new Date(detailData.updated_at).toLocaleString('zh-CN')}</Descriptions.Item>
            {Object.keys(detailData.metadata).length > 0 && (
              <Descriptions.Item label="元数据" span={2}>
                <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(detailData.metadata, null, 2)}</pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default SupervisionPage;
