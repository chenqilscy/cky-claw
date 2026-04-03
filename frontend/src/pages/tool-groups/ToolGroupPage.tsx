import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  message,
  Modal,
  Space,
  Switch,
  Tag,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  ToolOutlined,
  DeleteOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { toolGroupService } from '../../services/toolGroupService';
import type {
  ToolGroupResponse,
  ToolGroupCreateRequest,
  ToolGroupUpdateRequest,
  ToolDefinition,
} from '../../services/toolGroupService';

const { TextArea } = Input;

const SOURCE_COLORS: Record<string, string> = {
  builtin: 'blue',
  custom: 'green',
};

const ToolGroupPage: React.FC = () => {
  const [data, setData] = useState<ToolGroupResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const [modalVisible, setModalVisible] = useState(false);
  const [editingGroup, setEditingGroup] = useState<ToolGroupResponse | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await toolGroupService.list();
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取工具组列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const parseToolsJson = (raw: string): ToolDefinition[] => {
    if (!raw.trim()) return [];
    try {
      const parsed = JSON.parse(raw) as ToolDefinition[];
      if (!Array.isArray(parsed)) throw new Error('tools must be an array');
      return parsed;
    } catch {
      throw new Error('工具定义 JSON 格式不合法');
    }
  };

  const openCreate = () => {
    setEditingGroup(null);
    form.resetFields();
    setModalVisible(true);
  };

  const openEdit = (record: ToolGroupResponse) => {
    setEditingGroup(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      tools_json: JSON.stringify(record.tools, null, 2),
      is_enabled: record.is_enabled,
    });
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      let tools: ToolDefinition[] = [];
      try {
        tools = parseToolsJson(values.tools_json || '[]');
      } catch (e) {
        message.error((e as Error).message);
        setSubmitting(false);
        return;
      }

      if (editingGroup) {
        const updateData: ToolGroupUpdateRequest = {
          description: values.description,
          tools,
          is_enabled: values.is_enabled,
        };
        await toolGroupService.update(editingGroup.name, updateData);
        message.success('更新成功');
      } else {
        const createData: ToolGroupCreateRequest = {
          name: values.name,
          description: values.description,
          tools,
        };
        await toolGroupService.create(createData);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchList();
    } catch {
      message.error('操作失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (name: string) => {
    try {
      await toolGroupService.delete(name);
      message.success('删除成功');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggleEnabled = async (record: ToolGroupResponse, enabled: boolean) => {
    try {
      await toolGroupService.update(record.name, { is_enabled: enabled });
      message.success(enabled ? '已启用' : '已禁用');
      fetchList();
    } catch {
      message.error('操作失败');
    }
  };

  const columns: ProColumns<ToolGroupResponse>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 160,
      render: (_, record) => <strong>{record.name}</strong>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      width: 200,
      ellipsis: true,
    },
    {
      title: '来源',
      dataIndex: 'source',
      width: 80,
      render: (_, record) => (
        <Tag color={SOURCE_COLORS[record.source] || 'default'}>
          {record.source === 'builtin' ? '内置' : '自定义'}
        </Tag>
      ),
    },
    {
      title: '工具数量',
      width: 100,
      render: (_, record) => (record.tools || []).length,
    },
    {
      title: '启用',
      dataIndex: 'is_enabled',
      width: 80,
      render: (_, record) => (
        <Switch
          checked={record.is_enabled}
          onChange={(checked) => handleToggleEnabled(record, checked)}
          size="small"
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (_, record) => new Date(record.created_at).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 140,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除此工具组？"
            onConfirm={() => handleDelete(record.name)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
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
            <ToolOutlined />
            工具组管理
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建工具组
          </Button>
        }
      >
        <ProTable<ToolGroupResponse>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          search={false}
          toolBarRender={false}
          pagination={{
            total,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>

      <Modal
        title={editingGroup ? '编辑工具组' : '新建工具组'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请输入工具组名称' },
              { min: 3, max: 64, message: '长度须在 3-64 字符之间' },
            ]}
          >
            <Input placeholder="如: web-search" disabled={!!editingGroup} />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input placeholder="工具组用途描述" />
          </Form.Item>

          <Form.Item
            name="tools_json"
            label="工具定义（JSON 数组）"
            tooltip='每个工具需 name、description 和 parameters_schema 字段'
          >
            <TextArea
              rows={8}
              placeholder={`[\n  {\n    "name": "web_search",\n    "description": "搜索网页内容",\n    "parameters_schema": {\n      "type": "object",\n      "properties": {\n        "query": { "type": "string" }\n      },\n      "required": ["query"]\n    }\n  }\n]`}
            />
          </Form.Item>

          {editingGroup && (
            <Form.Item name="is_enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </>
  );
};

export default ToolGroupPage;
