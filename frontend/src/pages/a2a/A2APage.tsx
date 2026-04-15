import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  List,
  message,
  Modal,
  Row,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  PlusOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import type { ColumnsType } from 'antd/es/table';
import {
  a2aService,
  type A2AAgentCard,
  type A2ATask,
} from '../../services/a2aService';

const { Text } = Typography;

const statusColors: Record<string, string> = {
  submitted: 'blue',
  working: 'orange',
  completed: 'green',
  failed: 'red',
  canceled: 'default',
};

/**
 * A2A 协议管理页 — Agent Card 注册 + Task 管理 + 服务发现。
 */
const A2APage: React.FC = () => {
  const [cards, setCards] = useState<A2AAgentCard[]>([]);
  const [tasks, setTasks] = useState<A2ATask[]>([]);
  const [cardsTotal, setCardsTotal] = useState(0);
  const [tasksTotal, setTasksTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [cardModalOpen, setCardModalOpen] = useState(false);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [detailCard, setDetailCard] = useState<A2AAgentCard | null>(null);
  const [editCard, setEditCard] = useState<A2AAgentCard | null>(null);
  const [cardForm] = Form.useForm();
  const [taskForm] = Form.useForm();

  const fetchCards = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await a2aService.listAgentCards({ limit: 50 });
      setCards(resp.data);
      setCardsTotal(resp.total);
    } catch {
      message.error('获取 Agent Card 列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTasks = useCallback(async () => {
    try {
      const resp = await a2aService.listTasks({ limit: 50 });
      setTasks(resp.data);
      setTasksTotal(resp.total);
    } catch {
      message.error('获取 Task 列表失败');
    }
  }, []);

  useEffect(() => {
    fetchCards();
    fetchTasks();
  }, [fetchCards, fetchTasks]);

  const handleCreateCard = async (values: { agent_id: string; name: string; url?: string; description?: string }) => {
    try {
      await a2aService.createAgentCard(values);
      message.success('Agent Card 创建成功');
      setCardModalOpen(false);
      cardForm.resetFields();
      fetchCards();
    } catch {
      message.error('创建失败');
    }
  };

  const handleUpdateCard = async (values: { name: string; url?: string; description?: string }) => {
    if (!editCard) return;
    try {
      await a2aService.updateAgentCard(editCard.id, values);
      message.success('更新成功');
      setEditCard(null);
      fetchCards();
    } catch {
      message.error('更新失败');
    }
  };

  const handleDeleteCard = async (id: string) => {
    try {
      await a2aService.deleteAgentCard(id);
      message.success('已删除');
      fetchCards();
    } catch {
      message.error('删除失败');
    }
  };

  const handleCreateTask = async (values: { agent_card_id: string; input_text: string }) => {
    try {
      await a2aService.createTask({
        agent_card_id: values.agent_card_id,
        input_messages: [
          { role: 'user', parts: [{ type: 'text/plain', text: values.input_text }] },
        ],
      });
      message.success('Task 创建成功');
      setTaskModalOpen(false);
      taskForm.resetFields();
      fetchTasks();
    } catch {
      message.error('创建失败');
    }
  };

  const handleCancelTask = async (taskId: string) => {
    try {
      await a2aService.cancelTask(taskId);
      message.success('Task 已取消');
      fetchTasks();
    } catch {
      message.error('取消失败');
    }
  };

  const cardColumns: ColumnsType<A2AAgentCard> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: 'URL', dataIndex: 'url', key: 'url', width: 260, ellipsis: true },
    { title: '版本', dataIndex: 'version', key: 'version', width: 80 },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: A2AAgentCard) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => setDetailCard(record)} />
          <Button size="small" icon={<EditOutlined />} onClick={() => { setEditCard(record); cardForm.setFieldsValue(record); }} />
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteCard(record.id)} />
        </Space>
      ),
    },
  ];

  const taskColumns: ColumnsType<A2ATask> = [
    { title: 'Task ID', dataIndex: 'id', key: 'id', width: 280, ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => <Tag color={statusColors[s] ?? 'default'}>{s}</Tag>,
    },
    { title: 'Agent Card', dataIndex: 'agent_card_id', key: 'agent_card_id', width: 280, ellipsis: true },
    {
      title: '历史',
      dataIndex: 'history',
      key: 'history',
      width: 80,
      render: (h: Record<string, unknown>[]) => h?.length ?? 0,
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: A2ATask) =>
        !['completed', 'failed', 'canceled'].includes(record.status) ? (
          <Button size="small" danger icon={<StopOutlined />} onClick={() => handleCancelTask(record.id)}>
            取消
          </Button>
        ) : null,
    },
  ];

  return (
    <PageContainer
      title="A2A 协议"
      icon={<ApiOutlined />}
      description="管理 Agent Card 发布、Task 生命周期，实现跨平台 Agent 互操作"
    >
      <Row gutter={24}>
        <Col span={24}>
          <Card
            title="Agent Cards"
            extra={
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setCardModalOpen(true)}>
                注册 Agent Card
              </Button>
            }
            style={{ marginBottom: 24 }}
          >
            <Table
              rowKey="id"
              columns={cardColumns}
              dataSource={cards}
              loading={loading}
              pagination={{ total: cardsTotal, pageSize: 20 }}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={24}>
        <Col span={24}>
          <Card
            title="Tasks"
            extra={
              <Button icon={<SendOutlined />} onClick={() => setTaskModalOpen(true)}>
                发送 Task
              </Button>
            }
          >
            <Table
              rowKey="id"
              columns={taskColumns}
              dataSource={tasks}
              pagination={{ total: tasksTotal, pageSize: 20 }}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* 创建 Agent Card Modal */}
      <Modal
        title="注册 Agent Card"
        open={cardModalOpen}
        onCancel={() => setCardModalOpen(false)}
        onOk={() => cardForm.submit()}
        destroyOnClose
      >
        <Form form={cardForm} layout="vertical" onFinish={handleCreateCard}>
          <Form.Item name="agent_id" label="Agent ID" rules={[{ required: true }]}>
            <Input placeholder="关联的 Agent UUID" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="A2A 端点 URL">
            <Input placeholder="https://example.com/a2a" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑 Agent Card Modal */}
      <Modal
        title="编辑 Agent Card"
        open={!!editCard}
        onCancel={() => setEditCard(null)}
        onOk={() => cardForm.submit()}
        destroyOnClose
      >
        <Form form={cardForm} layout="vertical" onFinish={handleUpdateCard}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="A2A 端点 URL">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Agent Card 详情 Modal */}
      <Modal
        title="Agent Card 详情"
        open={!!detailCard}
        onCancel={() => setDetailCard(null)}
        footer={null}
        width={640}
      >
        {detailCard && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="ID">{detailCard.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{detailCard.name}</Descriptions.Item>
            <Descriptions.Item label="描述">{detailCard.description}</Descriptions.Item>
            <Descriptions.Item label="URL">{detailCard.url}</Descriptions.Item>
            <Descriptions.Item label="版本">{detailCard.version}</Descriptions.Item>
            <Descriptions.Item label="能力">
              {JSON.stringify(detailCard.capabilities)}
            </Descriptions.Item>
            <Descriptions.Item label="技能">
              <List
                size="small"
                dataSource={detailCard.skills}
                renderItem={(s) => (
                  <List.Item>
                    <Text code>{String(s.name ?? s.id)}</Text>
                  </List.Item>
                )}
              />
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      {/* 创建 Task Modal */}
      <Modal
        title="发送 A2A Task"
        open={taskModalOpen}
        onCancel={() => setTaskModalOpen(false)}
        onOk={() => taskForm.submit()}
        destroyOnClose
      >
        <Form form={taskForm} layout="vertical" onFinish={handleCreateTask}>
          <Form.Item name="agent_card_id" label="Agent Card ID" rules={[{ required: true }]}>
            <Input placeholder="目标 Agent Card UUID" />
          </Form.Item>
          <Form.Item name="input_text" label="输入消息" rules={[{ required: true }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default A2APage;
