import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Select,
  Space,
  Tag,
  Popconfirm,
  Slider,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  SearchOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { memoryService } from '../../services/memoryService';
import type {
  MemoryItem,
  MemoryCreateParams,
  MemoryUpdateParams,
} from '../../services/memoryService';

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

const MemoryPage: React.FC = () => {
  const [data, setData] = useState<MemoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [filters, setFilters] = useState<{ user_id?: string; type?: string; agent_name?: string }>({});

  // Create/Edit Modal
  const [modalVisible, setModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState<MemoryItem | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  // Search Modal
  const [searchVisible, setSearchVisible] = useState(false);
  const [searchForm] = Form.useForm();
  const [searchResults, setSearchResults] = useState<MemoryItem[]>([]);
  const [searching, setSearching] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await memoryService.list({
        ...filters,
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      });
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取记忆列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination, filters]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openCreate = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ type: 'structured_fact', confidence: 1.0 });
    setModalVisible(true);
  };

  const openEdit = (record: MemoryItem) => {
    setEditingItem(record);
    form.setFieldsValue({
      type: record.type,
      content: record.content,
      confidence: record.confidence,
      user_id: record.user_id,
      agent_name: record.agent_name,
    });
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      if (editingItem) {
        const updateData: MemoryUpdateParams = {
          content: values.content,
          confidence: values.confidence,
          type: values.type,
        };
        await memoryService.update(editingItem.id, updateData);
        message.success('更新成功');
      } else {
        const createData: MemoryCreateParams = {
          type: values.type,
          content: values.content,
          confidence: values.confidence ?? 1.0,
          user_id: values.user_id,
          agent_name: values.agent_name,
        };
        await memoryService.create(createData);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchList();
    } catch {
      // form validation error or API error
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await memoryService.delete(id);
      message.success('删除成功');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSearch = async () => {
    try {
      const values = await searchForm.validateFields();
      setSearching(true);
      const results = await memoryService.search({
        user_id: values.user_id,
        query: values.query,
        limit: values.limit ?? 10,
      });
      setSearchResults(results);
    } catch {
      // validation or API error
    } finally {
      setSearching(false);
    }
  };

  const columns: ProColumns<MemoryItem>[] = [
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
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
      render: (v) => new Date(v as string).toLocaleString('zh-CN'),
      sorter: (a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime(),
    },
    {
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title={
          <Space>
            <BulbOutlined />
            <span>记忆管理</span>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<SearchOutlined />} onClick={() => setSearchVisible(true)}>
              搜索记忆
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建记忆
            </Button>
          </Space>
        }
      >
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
        <ProTable<MemoryItem>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          search={false}
          options={false}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            onChange: (page, size) => setPagination({ current: page, pageSize: size }),
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>

      {/* Create / Edit Modal */}
      <Modal
        title={editingItem ? '编辑记忆' : '新建记忆'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          {!editingItem && (
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
          {!editingItem && (
            <Form.Item name="agent_name" label="Agent 名称">
              <Input placeholder="可选" />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* Search Modal */}
      <Modal
        title="搜索记忆"
        open={searchVisible}
        onCancel={() => setSearchVisible(false)}
        footer={null}
        width={700}
        destroyOnClose
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
            <Button type="primary" icon={<SearchOutlined />} loading={searching} onClick={handleSearch}>
              搜索
            </Button>
          </Form.Item>
        </Form>
        {searchResults.length > 0 && (
          <ProTable<MemoryItem>
            rowKey="id"
            columns={columns.filter((c) => c.dataIndex !== 'user_id')}
            dataSource={searchResults}
            search={false}
            options={false}
            pagination={false}
          />
        )}
      </Modal>
    </>
  );
};

export default MemoryPage;
