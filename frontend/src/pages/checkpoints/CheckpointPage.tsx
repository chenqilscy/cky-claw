import { useState } from 'react';
import { Button, Card, Input, App, Popconfirm, Space, Tag, Typography } from 'antd';
import { DeleteOutlined, ReloadOutlined, SearchOutlined, SaveOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import type { CheckpointResponse } from '../../services/checkpointService';
import { useCheckpointList, useDeleteCheckpoint } from '../../hooks/useCheckpointQueries';

const { Text } = Typography;

const CheckpointPage: React.FC = () => {
  const { message } = App.useApp();
  const [runId, setRunId] = useState('');
  const [submittedRunId, setSubmittedRunId] = useState<string | undefined>();

  const { data: listData, isLoading: loading, refetch } = useCheckpointList(submittedRunId);
  const data = listData?.data ?? [];
  const total = listData?.total ?? 0;

  const deleteMutation = useDeleteCheckpoint();

  const handleSearch = () => {
    if (runId.trim()) setSubmittedRunId(runId.trim());
  };

  const handleDelete = async () => {
    if (!submittedRunId) return;
    try {
      await deleteMutation.mutateAsync(submittedRunId);
      message.success('检查点已删除');
      setSubmittedRunId(undefined);
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
    <PageContainer
      title="检查点管理"
      icon={<SaveOutlined />}
      description="查询与管理执行检查点，支持恢复运行"
    >
      <Card style={{ marginTop: 16 }}>
        <Space>
          <Input
            placeholder="输入 Run ID"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            style={{ width: 360 }}
            onPressEnter={handleSearch}
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearch}
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
              onClick={() => void refetch()}
            />,
          ]}
        />
      )}
    </PageContainer>
  );
};

export default CheckpointPage;
