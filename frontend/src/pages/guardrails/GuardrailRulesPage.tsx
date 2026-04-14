import { useState } from 'react';
import {
  Form,
  Input,
  InputNumber,
  App,
  Radio,
  Select,
  Switch,
  Tag,
} from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import {
  useGuardrailList,
  useCreateGuardrail,
  useUpdateGuardrail,
  useDeleteGuardrail,
} from '../../hooks/useGuardrailQueries';
import type {
  GuardrailRuleItem,
  GuardrailRuleCreateParams,
  GuardrailRuleUpdateParams,
} from '../../services/guardrailService';
import { CrudTable, PageContainer, buildActionColumn, createJsonValidatorRule, JsonEditor } from '../../components';
import type { CrudTableActions } from '../../components';

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

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<GuardrailRuleItem>,
  handleToggleEnabled: (record: GuardrailRuleItem, enabled: boolean) => void,
): ProColumns<GuardrailRuleItem>[] => [
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
  buildActionColumn<GuardrailRuleItem>(actions, {
    deleteConfirmTitle: '确认删除护栏规则',
  }),
];

/* ---- 动态表单（使用 Form.useWatch 监听 mode 字段）---- */

const GuardrailFormFields: React.FC<{ editing: GuardrailRuleItem | null }> = ({ editing }) => {
  const form = Form.useFormInstance();
  const currentMode = Form.useWatch('mode', form) as string || 'regex';

  return (
    <>
      <Form.Item
        name="name"
        label="规则名称"
        rules={[
          { required: true, message: '请输入规则名称' },
          { pattern: /^[a-z0-9][a-z0-9_-]*[a-z0-9]$/, message: '只能包含小写字母、数字、下划线和连字符' },
        ]}
      >
        <Input placeholder="如: sql-injection-detect" disabled={!!editing} />
      </Form.Item>

      <Form.Item name="description" label="描述">
        <Input placeholder="规则用途描述" />
      </Form.Item>

      <Form.Item name="type" label="护栏类型" rules={[{ required: true }]}>
        <Select options={TYPE_OPTIONS} />
      </Form.Item>

      <Form.Item name="mode" label="检测模式" rules={[{ required: true }]}>
        <Radio.Group options={MODE_OPTIONS} />
      </Form.Item>

      {currentMode === 'regex' && (
        <Form.Item
          name="patterns"
          label="正则表达式（每行一个）"
          rules={[{ required: true, message: '请输入至少一个正则' }]}
        >
          <TextArea rows={4} placeholder={'DROP\\s+TABLE\nDELETE\\s+FROM'} />
        </Form.Item>
      )}

      {currentMode === 'keyword' && (
        <Form.Item
          name="keywords"
          label="关键词（每行一个）"
          rules={[{ required: true, message: '请输入至少一个关键词' }]}
        >
          <TextArea rows={4} placeholder={'暴力\n色情\n违禁'} />
        </Form.Item>
      )}

      {currentMode === 'llm' && (
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
                  extra='必须包含 {content} 占位符，LLM 需返回 JSON: {safe, confidence, reason}'
                >
                  <TextArea rows={6} placeholder={'判断以下内容是否安全：\n{content}\n\n回复 JSON: {"safe": true/false, "confidence": 0.0~1.0, "reason": "理由"}'} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
        </>
      )}

      <Form.Item name="message" label="拦截提示信息">
        <Input placeholder="触发规则时给用户的提示（可选）" />
      </Form.Item>

      <Form.Item
        name="conditions_json"
        label="条件启用配置（JSON）"
        extra='留空表示始终启用。示例：{"agent_name": "my-agent"}'
        rules={[createJsonValidatorRule()]}
      >
        <JsonEditor height={80} placeholder='{"agent_name": "my-agent"}' />
      </Form.Item>
    </>
  );
};

/* ---- payload 构建辅助 ---- */

const buildConfig = (values: Record<string, unknown>): Record<string, unknown> => {
  const config: Record<string, unknown> = {};
  const mode = values.mode as string;
  if (mode === 'regex') {
    config.patterns = (values.patterns as string)
      .split('\n').map((s) => s.trim()).filter(Boolean);
  } else if (mode === 'keyword') {
    config.keywords = (values.keywords as string)
      .split('\n').map((s) => s.trim()).filter(Boolean);
  } else if (mode === 'llm') {
    config.preset = values.llm_preset || 'custom';
    if (values.llm_model) config.model = values.llm_model;
    if (values.llm_threshold !== undefined) config.threshold = values.llm_threshold;
    if (values.llm_preset === 'custom' && values.llm_prompt_template) {
      config.prompt_template = values.llm_prompt_template;
    }
  }
  if (values.message) config.message = values.message;
  return config;
};

const parseConditions = (raw: string): Record<string, unknown> => {
  if (!raw || !raw.trim()) return {};
  return JSON.parse(raw) as Record<string, unknown>;
};

/* ---- 页面组件 ---- */

const GuardrailRulesPage: React.FC = () => {
  const { message } = App.useApp();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const queryResult = useGuardrailList({
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const createMutation = useCreateGuardrail();
  const updateMutation = useUpdateGuardrail();
  const deleteMutation = useDeleteGuardrail();

  const handleToggleEnabled = async (record: GuardrailRuleItem, enabled: boolean) => {
    try {
      await updateMutation.mutateAsync({ id: record.id, data: { is_enabled: enabled } });
      message.success(enabled ? '已启用' : '已禁用');
    } catch {
      message.error('操作失败');
    }
  };

  return (
    <PageContainer
      title="Guardrail 规则管理"
      icon={<SafetyCertificateOutlined />}
      description="管理输入 / 输出 / 工具护栏规则"
    >
    <CrudTable<
      GuardrailRuleItem,
      GuardrailRuleCreateParams,
      { id: string; data: GuardrailRuleUpdateParams }
    >
      hideTitle
      mobileHiddenColumns={['description']}
      title="Guardrail 规则管理"
      icon={<SafetyCertificateOutlined />}
      queryResult={queryResult}
      createMutation={createMutation}
      updateMutation={updateMutation}
      deleteMutation={deleteMutation}
      createButtonText="新建规则"
      modalTitle={(editing) => (editing ? '编辑 Guardrail 规则' : '新建 Guardrail 规则')}
      createDefaults={{ type: 'input', mode: 'regex' }}
      pagination={pagination}
      onPaginationChange={(page, pageSize) => setPagination({ current: page, pageSize })}
      columns={(actions) => buildColumns(actions, handleToggleEnabled)}
      renderForm={(_form: FormInstance, editing: GuardrailRuleItem | null) => (
        <GuardrailFormFields editing={editing} />
      )}
      toFormValues={(record) => {
        const config = record.config;
        return {
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
          conditions_json: Object.keys(record.conditions || {}).length > 0
            ? JSON.stringify(record.conditions, null, 2)
            : '',
        };
      }}
      toCreatePayload={(values) => ({
        name: values.name as string,
        type: values.type as string,
        mode: values.mode as string,
        config: buildConfig(values),
        conditions: parseConditions((values.conditions_json as string) || ''),
        description: values.description as string,
      })}
      toUpdatePayload={(values, record) => ({
        id: record.id,
        data: {
          description: values.description as string,
          type: values.type as string,
          mode: values.mode as string,
          config: buildConfig(values),
          conditions: parseConditions((values.conditions_json as string) || ''),
        },
      })}
    />    </PageContainer>  );
};

export default GuardrailRulesPage;
