import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Input, App, Popconfirm, Space, Tag, Typography } from 'antd';
import { DeleteOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { checkpointService } from '../../services/checkpointService';
import type { CheckpointResponse } from '../../services/checkpointService';

const { Title, Text } = Typography;

const CheckpointPage: React.FC = () => {
  const { message } = App.useApp();
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<CheckpointResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchCheckpoints = useCallback(async () => {
    if (!runId.trim()) return;
    setLoading(true);
    try {
      const res = await checkpointService.list(runId.trim());
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取检查点列表失败');
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [runId, message]);

  useEffect(() => {
    if (runId.trim()) {
      fetchCheckpoints();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async () => {
    if (!runId.trim()) return;
    try {
      await checkpointService.delete(runId.trim());
      message.success('检查点已删除');
      setData([]);
      setTotal(0);
    } catch {
      message.error('删除失败');
    }
  };

  const columns: ProColumns<CheckpointResponse>[] = [
    {
      title: '轮次',
      dataIndex: 'turn_count',
      width: 80,
      render: (_, record) => <Tag color="blue">{record.turn_count}</Tag>,
    },
    {
      title: '当前 Agent',
      dataIndex: 'current_agent_name',
      width: 160,
    },
    {
      title: '消息数',
      width: 100,
      render: (_, record) => record.messages.length,
    },
    {
      title: 'Token 使用',
      width: 160,
      render: (_, record) => {
        const prompt = record.token_usage.prompt_tokens ?? 0;
        const completion = record.token_usage.completion_tokens ?? 0;
        return <Text type="secondary">{prompt + completion} ({prompt}+{completion})</Text>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 200,
      render: (_, record) => new Date(record.created_at).toLocaleString('zh-CN'),
    },
    {
      title: 'Checkpoint ID',
      dataIndex: 'checkpoint_id',
      width: 280,
      ellipsis: true,
      copyable: true,
    },
  ];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Title level={4}>检查点管理</Title>
      <Text type="secondary">
        查询指定执行（Run）的所有检查点，支持从检查点恢复执行。
      </Text>

      <Card style={{ marginTop: 16 }}>
        <Space>
          <Input
            placeholder="输入 Run ID"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            style={{ width: 360 }}
            onPressEnter={fetchCheckpoints}
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={fetchCheckpoints}
            loading={loading}
            disabled={!runId.trim()}
          >
            查询
          </Button>
          {data.length > 0 && (
            <Popconfirm
              title="确定删除该 Run 的所有检查点？"
              onConfirm={handleDelete}
              okText="删除"
              cancelText="取消"
            >
              <Button danger icon={<DeleteOutlined />}>
                清除全部
              </Button>
            </Popconfirm>
          )}
        </Space>
      </Card>

      {data.length > 0 && (
        <ProTable<CheckpointResponse>
          headerTitle={`检查点列表（共 ${total} 个）`}
          rowKey="checkpoint_id"
          columns={columns}
          dataSource={data}
          loading={loading}
          search={false}
          pagination={false}
          style={{ marginTop: 16 }}
          toolBarRender={() => [
            <ReloadOutlined
              key="reload"
              style={{ cursor: 'pointer', fontSize: 16 }}
              onClick={fetchCheckpoints}
            />,
          ]}
        />
      )}
    </div>
  );
};

export default CheckpointPage;
