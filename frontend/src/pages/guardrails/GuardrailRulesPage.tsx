import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Radio,
  Select,
  Space,
  Switch,
  Tag,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  SafetyCertificateOutlined,
  DeleteOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { guardrailService } from '../../services/guardrailService';
import type {
  GuardrailRuleItem,
  GuardrailRuleCreateParams,
  GuardrailRuleUpdateParams,
} from '../../services/guardrailService';

const { TextArea } = Input;

const TYPE_OPTIONS = [
  { label: 'Input（输入检测）', value: 'input' },
  { label: 'Output（输出检测）', value: 'output' },
  { label: 'Tool（工具调用）', value: 'tool' },
];

const MODE_OPTIONS = [
  { label: 'Regex（正则)', value: 'regex' },
  { label: 'Keyword（关键词）', value: 'keyword' },
  { label: 'LLM（AI 语义检测）', value: 'llm' },
];

const LLM_PRESET_OPTIONS = [
  { label: 'Prompt 注入检测', value: 'prompt_injection' },
  { label: '内容安全检测', value: 'content_safety' },
  { label: '自定义 Prompt', value: 'custom' },
];

const TYPE_COLORS: Record<string, string> = {
  input: 'blue',
  output: 'green',
  tool: 'orange',
};

const GuardrailRulesPage: React.FC = () => {
  const [data, setData] = useState<GuardrailRuleItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // Modal
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<GuardrailRuleItem | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [selectedMode, setSelectedMode] = useState('regex');

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await guardrailService.list({
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      });
      setData(res.items);
      setTotal(res.total);
    } catch {
      message.error('获取规则列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openCreate = () => {
    setEditingRule(null);
    setSelectedMode('regex');
    form.resetFields();
    form.setFieldsValue({ type: 'input', mode: 'regex' });
    setModalVisible(true);
  };

  const openEdit = (record: GuardrailRuleItem) => {
    setEditingRule(record);
    setSelectedMode(record.mode);
    const config = record.config;
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      type: record.type,
      mode: record.mode,
      patterns: record.mode === 'regex' ? (config.patterns as string[] || []).join('\n') : '',
      keywords: record.mode === 'keyword' ? (config.keywords as string[] || []).join('\n') : '',
      message: (config.message as string) || '',
      llm_preset: record.mode === 'llm' ? (config.preset as string) || 'custom' : 'prompt_injection',
      llm_model: record.mode === 'llm' ? (config.model as string) || '' : '',
      llm_threshold: record.mode === 'llm' ? (config.threshold as number) ?? 0.8 : 0.8,
      llm_prompt_template: record.mode === 'llm' ? (config.prompt_template as string) || '' : '',
    });
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const config: Record<string, unknown> = {};
      if (values.mode === 'regex') {
        config.patterns = (values.patterns as string)
          .split('\n')
          .map((s: string) => s.trim())
          .filter(Boolean);
      } else if (values.mode === 'keyword') {
        config.keywords = (values.keywords as string)
          .split('\n')
          .map((s: string) => s.trim())
          .filter(Boolean);
      } else if (values.mode === 'llm') {
        config.preset = values.llm_preset || 'custom';
        if (values.llm_model) config.model = values.llm_model;
        if (values.llm_threshold !== undefined) config.threshold = values.llm_threshold;
        if (values.llm_preset === 'custom' && values.llm_prompt_template) {
          config.prompt_template = values.llm_prompt_template;
        }
      }
      if (values.message) {
        config.message = values.message;
      }

      if (editingRule) {
        const updateData: GuardrailRuleUpdateParams = {
          description: values.description,
          type: values.type,
          mode: values.mode,
          config,
        };
        await guardrailService.update(editingRule.id, updateData);
        message.success('更新成功');
      } else {
        const createData: GuardrailRuleCreateParams = {
          name: values.name,
          type: values.type,
          mode: values.mode,
          config,
          description: values.description,
        };
        await guardrailService.create(createData);
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

  const handleDelete = async (id: string) => {
    try {
      await guardrailService.delete(id);
      message.success('删除成功');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggleEnabled = async (record: GuardrailRuleItem, enabled: boolean) => {
    try {
      await guardrailService.update(record.id, { is_enabled: enabled });
      message.success(enabled ? '已启用' : '已禁用');
      fetchList();
    } catch {
      message.error('操作失败');
    }
  };

  const columns: ProColumns<GuardrailRuleItem>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 180,
      render: (_, record) => <strong>{record.name}</strong>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      width: 200,
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'type',
      width: 120,
      render: (_, record) => (
        <Tag color={TYPE_COLORS[record.type] || 'default'}>{record.type}</Tag>
      ),
    },
    {
      title: '模式',
      dataIndex: 'mode',
      width: 120,
      render: (_, record) => {
        const modeMap: Record<string, { label: string; color: string }> = {
          regex: { label: '正则', color: 'default' },
          keyword: { label: '关键词', color: 'default' },
          llm: { label: 'LLM', color: 'purple' },
        };
        const m = modeMap[record.mode] || { label: record.mode, color: 'default' };
        return <Tag color={m.color}>{m.label}</Tag>;
      },
    },
    {
      title: '规则数',
      width: 100,
      render: (_, record) => {
        const config = record.config;
        if (record.mode === 'llm') {
          return <Tag color="purple">{(config.preset as string) || 'custom'}</Tag>;
        }
        const count = (config.patterns as string[] || []).length
          + (config.keywords as string[] || []).length;
        return count;
      },
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
            title="确认删除此规则？"
            onConfirm={() => handleDelete(record.id)}
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
            <SafetyCertificateOutlined />
            Guardrail 规则管理
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建规则
          </Button>
        }
      >
        <ProTable<GuardrailRuleItem>
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
        title={editingRule ? '编辑 Guardrail 规则' : '新建 Guardrail 规则'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="规则名称"
            rules={[
              { required: true, message: '请输入规则名称' },
              { pattern: /^[a-z0-9][a-z0-9_-]*[a-z0-9]$/, message: '只能包含小写字母、数字、下划线和连字符' },
            ]}
          >
            <Input placeholder="如: sql-injection-detect" disabled={!!editingRule} />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input placeholder="规则用途描述" />
          </Form.Item>

          <Form.Item name="type" label="护栏类型" rules={[{ required: true }]}>
            <Select options={TYPE_OPTIONS} />
          </Form.Item>

          <Form.Item name="mode" label="检测模式" rules={[{ required: true }]}>
            <Radio.Group
              options={MODE_OPTIONS}
              onChange={(e) => setSelectedMode(e.target.value)}
            />
          </Form.Item>

          {selectedMode === 'regex' && (
            <Form.Item
              name="patterns"
              label="正则表达式（每行一个）"
              rules={[{ required: true, message: '请输入至少一个正则' }]}
            >
              <TextArea rows={4} placeholder={'DROP\\s+TABLE\nDELETE\\s+FROM'} />
            </Form.Item>
          )}

          {selectedMode === 'keyword' && (
            <Form.Item
              name="keywords"
              label="关键词（每行一个）"
              rules={[{ required: true, message: '请输入至少一个关键词' }]}
            >
              <TextArea rows={4} placeholder={'暴力\n色情\n违禁'} />
            </Form.Item>
          )}

          {selectedMode === 'llm' && (
            <>
              <Form.Item
                name="llm_preset"
                label="LLM 预设场景"
                initialValue="prompt_injection"
              >
                <Select options={LLM_PRESET_OPTIONS} />
              </Form.Item>

              <Form.Item name="llm_model" label="LLM 模型">
                <Input placeholder="gpt-4o-mini（留空使用默认）" />
              </Form.Item>

              <Form.Item name="llm_threshold" label="判定阈值" initialValue={0.8}>
                <InputNumber min={0} max={1} step={0.05} placeholder="0.8" style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                noStyle
                shouldUpdate={(prev, cur) => prev.llm_preset !== cur.llm_preset}
              >
                {({ getFieldValue }) =>
                  getFieldValue('llm_preset') === 'custom' ? (
                    <Form.Item
                      name="llm_prompt_template"
                      label="自定义 Prompt"
                      rules={[{ required: true, message: '自定义模式必须提供 Prompt' }]}
                      extra="必须包含 {content} 占位符，LLM 需返回 JSON: {safe, confidence, reason}"
                    >
                      <TextArea rows={6} placeholder={'判断以下内容是否安全：\n{content}\n\n回复 JSON: {"safe": true/false, "confidence": 0.0~1.0, "reason": "理由"}'} />
                    </Form.Item>
                  ) : null
                }
              </Form.Item>
            </>
          )}

          <Form.Item name="message" label="拦截提示消息">
            <Input placeholder="当规则触发时返回的提示信息" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default GuardrailRulesPage;
