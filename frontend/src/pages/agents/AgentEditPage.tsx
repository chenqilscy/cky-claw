import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Card, Form, Input, Select, Space, App, Spin, Switch, Steps, Divider, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { agentService } from '../../services/agentService';
import type { AgentConfig, AgentCreateInput, AgentUpdateInput } from '../../services/agentService';
import { guardrailService } from '../../services/guardrailService';
import type { GuardrailRuleItem } from '../../services/guardrailService';
import { providerService } from '../../services/providerService';
import type { ProviderResponse, ProviderModelResponse } from '../../services/providerService';
import { toolGroupService } from '../../services/toolGroupService';

const { TextArea } = Input;
const { Text } = Typography;

const APPROVAL_MODES = [
  { label: 'Suggest', value: 'suggest' },
  { label: 'Auto Edit', value: 'auto-edit' },
  { label: 'Full Auto', value: 'full-auto' },
];

const RESPONSE_STYLES = [
  { label: '默认', value: '' },
  { label: '简洁模式 (talk-normal)', value: 'concise' },
  { label: '正式模式', value: 'formal' },
  { label: '创意模式', value: 'creative' },
];

const STEP_ITEMS = [
  { title: '基本信息' },
  { title: '模型与工具' },
  { title: '安全与高级' },
];

const AgentEditPage: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { name } = useParams<{ name: string }>();
  const isEdit = !!name;
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [manualModel, setManualModel] = useState(false);
  const [guardrailOptions, setGuardrailOptions] = useState<{ label: string; value: string }[]>([]);
  const [outputGuardrailOptions, setOutputGuardrailOptions] = useState<{ label: string; value: string }[]>([]);
  const [toolGuardrailOptions, setToolGuardrailOptions] = useState<{ label: string; value: string }[]>([]);
  const [agentOptions, setAgentOptions] = useState<{ label: string; value: string }[]>([]);
  const [toolGroupOptions, setToolGroupOptions] = useState<{ label: string; value: string }[]>([]);
  const [providerOptions, setProviderOptions] = useState<{ label: string; value: string; id: string; providerType: string }[]>([]);
  const [modelOptions, setModelOptions] = useState<{ label: string; value: string }[]>([]);
  const [modelLoading, setModelLoading] = useState(false);

  useEffect(() => {
    guardrailService.list({ enabled_only: true, limit: 200 })
      .then((res) => {
        setGuardrailOptions(
          res.data
            .filter((r: GuardrailRuleItem) => r.type === 'input')
            .map((r: GuardrailRuleItem) => ({ label: `${r.name} (${r.mode})`, value: r.name }))
        );
        setOutputGuardrailOptions(
          res.data
            .filter((r: GuardrailRuleItem) => r.type === 'output')
            .map((r: GuardrailRuleItem) => ({ label: `${r.name} (${r.mode})`, value: r.name }))
        );
        setToolGuardrailOptions(
          res.data
            .filter((r: GuardrailRuleItem) => r.type === 'tool')
            .map((r: GuardrailRuleItem) => ({ label: `${r.name} (${r.mode})`, value: r.name }))
        );
      })
      .catch(() => { message.error('加载护栏规则失败'); });

    // 加载可选的工具组列表
    toolGroupService.list()
      .then((res) => {
        setToolGroupOptions(
          res.data
            .filter((g) => g.is_enabled)
            .map((g) => ({ label: `${g.name}${g.description ? ` — ${g.description}` : ''}`, value: g.name }))
        );
      })
      .catch(() => { message.error('加载工具组失败'); });

    // 加载可选的 Agent 列表（用于 Agent-as-Tool 选择）
    agentService.list({ limit: 200 })
      .then((res) => {
        setAgentOptions(
          res.data
            .filter((a: AgentConfig) => a.name !== name) // 排除自身
            .map((a: AgentConfig) => ({ label: `${a.name}${a.description ? ` — ${a.description}` : ''}`, value: a.name }))
        );
      })
      .catch(() => { message.error('加载 Agent 列表失败'); });

    // 加载可选的 Provider 列表
    providerService.list({ is_enabled: true, limit: 100 })
      .then((res) => {
        setProviderOptions(
          res.data.map((p: ProviderResponse) => ({
            label: `${p.name} (${p.provider_type})`,
            value: p.name,
            id: p.id,
            providerType: p.provider_type,
          }))
        );
      })
      .catch(() => { message.error('加载 Provider 列表失败'); });
  }, [name, message]);

  // 加载指定 Provider 下的模型列表
  const loadModels = useCallback(async (providerName: string) => {
    const provider = providerOptions.find((p) => p.value === providerName);
    if (!provider) return;
    setModelLoading(true);
    try {
      const res = await providerService.listModels(provider.id, true);
      const seen = new Set<string>();
      const options: { label: string; value: string }[] = [];
      for (const m of res.data) {
        const val = `${provider.providerType}/${m.model_name}`;
        if (!seen.has(val)) {
          seen.add(val);
          options.push({ label: m.display_name || m.model_name, value: val });
        }
      }
      setModelOptions(options);
    } catch {
      setModelOptions([]);
    } finally {
      setModelLoading(false);
    }
  }, [providerOptions]);

  // Provider 变更时联动加载模型
  const handleProviderChange = useCallback((providerName: string | undefined) => {
    form.setFieldValue('model', undefined);
    setModelOptions([]);
    if (providerName) {
      loadModels(providerName);
    }
  }, [form, loadModels]);

  useEffect(() => {
    if (isEdit && name) {
      setLoading(true);
      agentService.get(name)
        .then((agent: AgentConfig) => {
          form.setFieldsValue({
            name: agent.name,
            description: agent.description,
            instructions: agent.instructions,
            prompt_variables: agent.prompt_variables || [],
            model: agent.model,
            provider_name: agent.provider_name || undefined,
            approval_mode: agent.approval_mode,
            tool_groups: agent.tool_groups || [],
            handoffs: agent.handoffs?.join(', ') || '',
            agent_tools: agent.agent_tools || [],
            input_guardrails: agent.guardrails?.input || [],
            output_guardrails: agent.guardrails?.output || [],
            tool_guardrails: agent.guardrails?.tool || [],
            output_type: agent.output_type ? JSON.stringify(agent.output_type, null, 2) : '',
          });
          // 如果有 provider_name，加载其模型列表；否则打开手动输入模式
          if (agent.provider_name) {
            const prov = providerOptions.find((p) => p.value === agent.provider_name);
            if (prov) {
              loadModels(agent.provider_name);
            } else {
              setManualModel(true);
            }
          } else if (agent.model) {
            setManualModel(true);
          }
        })
        .catch(() => message.error('加载 Agent 失败'))
        .finally(() => setLoading(false));
    }
  }, [isEdit, name, form, message, providerOptions, loadModels]);

  const onFinish = async (values: Record<string, unknown>) => {
    setSaving(true);
    try {
      const payload: AgentCreateInput = {
        name: values.name as string,
        description: (values.description as string) || '',
        instructions: (values.instructions as string) || '',
        prompt_variables: (values.prompt_variables as Array<Record<string, unknown>> | undefined) || [],
        model: (values.model as string) || 'openai/glm-4-flash',
        provider_name: (values.provider_name as string) || null,
        approval_mode: (values.approval_mode as string) || 'suggest',
        response_style: (values.response_style as string) || null,
        tool_groups: (values.tool_groups as string[]) || [],
        handoffs: (values.handoffs as string)
          ? (values.handoffs as string).split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        agent_tools: (values.agent_tools as string[]) || [],
        guardrails: {
          input: (values.input_guardrails as string[]) || [],
          output: (values.output_guardrails as string[]) || [],
          tool: (values.tool_guardrails as string[]) || [],
        },
        output_type: (() => {
          const raw = (values.output_type as string || '').trim();
          if (!raw) return null;
          try { return JSON.parse(raw) as Record<string, unknown>; }
          catch { message.error('output_type 必须是有效的 JSON Schema'); return undefined; }
        })(),
      };

      if (payload.output_type === undefined) {
        setSaving(false);
        return;
      }

      if (isEdit && name) {
        const updatePayload: AgentUpdateInput = { ...payload };
        delete updatePayload.name;
        await agentService.update(name, updatePayload);
        message.success('更新成功');
      } else {
        await agentService.create(payload);
        message.success('创建成功');
      }
      navigate('/agents');
    } catch {
      message.error(isEdit ? '更新失败' : '创建失败');
    } finally {
      setSaving(false);
    }
  };

  // 步骤切换前校验当前步骤的字段
  const stepFields: string[][] = [
    ['name', 'description', 'instructions'],
    ['provider_name', 'model', 'approval_mode', 'response_style', 'tool_groups', 'handoffs', 'agent_tools'],
    ['input_guardrails', 'output_guardrails', 'tool_guardrails', 'output_type'],
  ];

  const handleNext = async () => {
    try {
      await form.validateFields(stepFields[currentStep]);
      setCurrentStep((s) => s + 1);
    } catch {
      // 校验不通过，停留在当前步骤
    }
  };

  const handlePrev = () => setCurrentStep((s) => s - 1);

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/agents')}>
          返回列表
        </Button>
      </Space>

      <Card title={isEdit ? `编辑 Agent: ${name}` : '创建新 Agent'}>
        <Steps current={currentStep} items={STEP_ITEMS} style={{ marginBottom: 32 }} />
        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            onFinish={onFinish}
            initialValues={{ approval_mode: 'suggest', model: 'openai/glm-4-flash' }}
          >
            {/* ========== 步骤 1：基本信息 ========== */}
            <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
              <Form.Item
                name="name"
                label="名称"
                rules={[
                  { required: true, message: '请输入名称' },
                  {
                    pattern: /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/,
                    message: '小写字母/数字/连字符，3-64 字符，不以连字符开头结尾',
                  },
                ]}
              >
                <Input placeholder="my-agent" disabled={isEdit} />
              </Form.Item>

              <Form.Item name="description" label="描述">
                <TextArea rows={2} placeholder="Agent 用途描述" />
              </Form.Item>

              <Form.Item name="instructions" label="系统指令">
                <TextArea rows={4} placeholder="Agent 的角色和行为指令" />
              </Form.Item>

              <Form.List name="prompt_variables">
                {(fields, { add, remove }) => (
                  <Card
                    type="inner"
                    title="模板变量"
                    extra={<Button onClick={() => add({ type: 'string', required: false })}>新增变量</Button>}
                    style={{ marginBottom: 16 }}
                  >
                    {fields.map((field) => (
                      <Space key={field.key} align="start" style={{ display: 'flex', marginBottom: 8 }} wrap>
                        <Form.Item
                          {...field}
                          name={[field.name, 'name']}
                          rules={[{ required: true, message: '变量名必填' }]}
                        >
                          <Input placeholder="name" style={{ width: 140 }} />
                        </Form.Item>
                        <Form.Item {...field} name={[field.name, 'type']} initialValue="string">
                          <Select
                            style={{ width: 110 }}
                            options={[
                              { label: 'string', value: 'string' },
                              { label: 'number', value: 'number' },
                              { label: 'boolean', value: 'boolean' },
                              { label: 'enum', value: 'enum' },
                            ]}
                          />
                        </Form.Item>
                        <Form.Item {...field} name={[field.name, 'default']}>
                          <Input placeholder="默认值" style={{ width: 140 }} />
                        </Form.Item>
                        <Form.Item {...field} name={[field.name, 'description']}>
                          <Input placeholder="描述" style={{ width: 200 }} />
                        </Form.Item>
                        <Form.Item {...field} name={[field.name, 'required']} valuePropName="checked" initialValue={false}>
                          <Switch checkedChildren="必填" unCheckedChildren="可选" />
                        </Form.Item>
                        <Button danger onClick={() => remove(field.name)}>删除</Button>
                      </Space>
                    ))}
                  </Card>
                )}
              </Form.List>
            </div>

            {/* ========== 步骤 2：模型与工具 ========== */}
            <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
              <Divider orientation="left">模型配置</Divider>

              <Form.Item name="provider_name" label="模型厂商">
                <Select
                  placeholder="选择模型厂商"
                  options={providerOptions}
                  allowClear
                  onChange={handleProviderChange}
                />
              </Form.Item>

              <div style={{ marginBottom: 16 }}>
                <Space>
                  <Text type="secondary">模型选择方式：</Text>
                  <Switch
                    checkedChildren="手动输入"
                    unCheckedChildren="下拉选择"
                    checked={manualModel}
                    onChange={(checked) => {
                      setManualModel(checked);
                      if (!checked) form.setFieldValue('model', undefined);
                    }}
                  />
                </Space>
              </div>

              {manualModel ? (
                <Form.Item name="model" label="模型标识" tooltip="格式：provider_type/model_name，如 openai/gpt-4o">
                  <Input placeholder="openai/glm-4-flash" />
                </Form.Item>
              ) : (
                <Form.Item name="model" label="选择模型">
                  <Select
                    placeholder={modelOptions.length === 0 ? '请先选择模型厂商' : '选择模型'}
                    options={modelOptions}
                    loading={modelLoading}
                    disabled={modelOptions.length === 0}
                    showSearch
                    allowClear
                  />
                </Form.Item>
              )}

              <Form.Item name="approval_mode" label="审批模式">
                <Select options={APPROVAL_MODES} />
              </Form.Item>

              <Form.Item name="response_style" label="输出风格">
                <Select options={RESPONSE_STYLES} allowClear placeholder="默认" />
              </Form.Item>

              <Divider orientation="left">工具与编排</Divider>

              <Form.Item name="tool_groups" label="工具组">
                <Select
                  mode="multiple"
                  placeholder="选择要关联的工具组"
                  options={toolGroupOptions}
                  allowClear
                />
              </Form.Item>

              <Form.Item name="handoffs" label="Handoff 目标（逗号分隔）">
                <Input placeholder="specialist-agent, reviewer-agent" />
              </Form.Item>

              <Form.Item
                name="agent_tools"
                label="Agent-as-Tool（子 Agent 作为工具）"
                tooltip="可选 — 将其他 Agent 注册为当前 Agent 可调用的工具"
              >
                <Select
                  mode="multiple"
                  placeholder="可选 — 选择要作为工具调用的子 Agent"
                  options={agentOptions}
                  allowClear
                />
              </Form.Item>
            </div>

            {/* ========== 步骤 3：安全与高级 ========== */}
            <div style={{ display: currentStep === 2 ? 'block' : 'none' }}>
              <Divider orientation="left">安全护栏</Divider>

              <Form.Item name="input_guardrails" label="Input Guardrails">
                <Select
                  mode="multiple"
                  placeholder="选择要启用的输入安全护栏"
                  options={guardrailOptions}
                  allowClear
                />
              </Form.Item>

              <Form.Item name="output_guardrails" label="Output Guardrails">
                <Select
                  mode="multiple"
                  placeholder="选择要启用的输出安全护栏"
                  options={outputGuardrailOptions}
                  allowClear
                />
              </Form.Item>

              <Form.Item name="tool_guardrails" label="Tool Guardrails">
                <Select
                  mode="multiple"
                  placeholder="选择要启用的工具调用护栏"
                  options={toolGuardrailOptions}
                  allowClear
                />
              </Form.Item>

              <Divider orientation="left">高级设置</Divider>

              <Form.Item
                name="output_type"
                label="结构化输出（JSON Schema）"
                tooltip="可选 — 定义 Agent 返回的结构化数据格式，留空则返回纯文本"
                rules={[
                  {
                    validator: (_, value) => {
                      if (!value || !(value as string).trim()) return Promise.resolve();
                      try { JSON.parse(value as string); return Promise.resolve(); }
                      catch { return Promise.reject(new Error('请输入有效的 JSON Schema')); }
                    },
                  },
                ]}
              >
                <TextArea
                  rows={6}
                  placeholder={'{\n  "type": "object",\n  "properties": {\n    "summary": { "type": "string" },\n    "score": { "type": "integer" }\n  },\n  "required": ["summary", "score"]\n}'}
                />
              </Form.Item>
            </div>

            {/* ========== 底部操作按钮 ========== */}
            <Form.Item style={{ marginTop: 24 }}>
              <Space>
                {currentStep > 0 && (
                  <Button onClick={handlePrev}>上一步</Button>
                )}
                {currentStep < STEP_ITEMS.length - 1 && (
                  <Button type="primary" onClick={handleNext}>下一步</Button>
                )}
                {currentStep === STEP_ITEMS.length - 1 && (
                  <Button type="primary" htmlType="submit" loading={saving}>
                    {isEdit ? '保存' : '创建'}
                  </Button>
                )}
                <Button onClick={() => navigate('/agents')}>取消</Button>
              </Space>
            </Form.Item>
          </Form>
        </Spin>
      </Card>
    </div>
  );
};

export default AgentEditPage;
