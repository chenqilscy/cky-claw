import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Card, Form, Input, Select, Space, message, Spin } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { agentService } from '../../services/agentService';
import type { AgentConfig, AgentCreateInput, AgentUpdateInput } from '../../services/agentService';
import { guardrailService } from '../../services/guardrailService';
import type { GuardrailRuleItem } from '../../services/guardrailService';

const { TextArea } = Input;

const APPROVAL_MODES = [
  { label: 'Suggest', value: 'suggest' },
  { label: 'Auto Edit', value: 'auto-edit' },
  { label: 'Full Auto', value: 'full-auto' },
];

const AgentEditPage: React.FC = () => {
  const navigate = useNavigate();
  const { name } = useParams<{ name: string }>();
  const isEdit = !!name;
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [guardrailOptions, setGuardrailOptions] = useState<{ label: string; value: string }[]>([]);
  const [agentOptions, setAgentOptions] = useState<{ label: string; value: string }[]>([]);

  useEffect(() => {
    guardrailService.list({ enabled_only: true, limit: 200 })
      .then((res) => {
        setGuardrailOptions(
          res.items
            .filter((r: GuardrailRuleItem) => r.type === 'input')
            .map((r: GuardrailRuleItem) => ({ label: `${r.name} (${r.mode})`, value: r.name }))
        );
      })
      .catch(() => { /* ignore */ });

    // 加载可选的 Agent 列表（用于 Agent-as-Tool 选择）
    agentService.list({ limit: 200 })
      .then((res) => {
        setAgentOptions(
          res.data
            .filter((a: AgentConfig) => a.name !== name) // 排除自身
            .map((a: AgentConfig) => ({ label: `${a.name}${a.description ? ` — ${a.description}` : ''}`, value: a.name }))
        );
      })
      .catch(() => { /* ignore */ });
  }, [name]);

  useEffect(() => {
    if (isEdit && name) {
      setLoading(true);
      agentService.get(name)
        .then((agent: AgentConfig) => {
          form.setFieldsValue({
            name: agent.name,
            description: agent.description,
            instructions: agent.instructions,
            model: agent.model,
            approval_mode: agent.approval_mode,
            tool_groups: agent.tool_groups?.join(', ') || '',
            handoffs: agent.handoffs?.join(', ') || '',
            agent_tools: agent.agent_tools || [],
            input_guardrails: agent.guardrails?.input || [],
          });
        })
        .catch(() => message.error('加载 Agent 失败'))
        .finally(() => setLoading(false));
    }
  }, [isEdit, name, form]);

  const onFinish = async (values: Record<string, unknown>) => {
    setSaving(true);
    try {
      const payload: AgentCreateInput = {
        name: values.name as string,
        description: (values.description as string) || '',
        instructions: (values.instructions as string) || '',
        model: (values.model as string) || 'openai/glm-4-flash',
        approval_mode: (values.approval_mode as string) || 'suggest',
        tool_groups: (values.tool_groups as string)
          ? (values.tool_groups as string).split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        handoffs: (values.handoffs as string)
          ? (values.handoffs as string).split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        agent_tools: (values.agent_tools as string[]) || [],
        guardrails: {
          input: (values.input_guardrails as string[]) || [],
          output: [],
          tool: [],
        },
      };

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

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/agents')}>
          返回列表
        </Button>
      </Space>

      <Card title={isEdit ? `编辑 Agent: ${name}` : '创建新 Agent'}>
        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            onFinish={onFinish}
            initialValues={{ approval_mode: 'suggest', model: 'openai/glm-4-flash' }}
          >
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

            <Form.Item name="model" label="模型">
              <Input placeholder="openai/glm-4-flash" />
            </Form.Item>

            <Form.Item name="approval_mode" label="审批模式">
              <Select options={APPROVAL_MODES} />
            </Form.Item>

            <Form.Item name="tool_groups" label="工具组（逗号分隔）">
              <Input placeholder="web_search, code_executor" />
            </Form.Item>

            <Form.Item name="handoffs" label="Handoff 目标（逗号分隔）">
              <Input placeholder="specialist-agent, reviewer-agent" />
            </Form.Item>

            <Form.Item name="agent_tools" label="Agent-as-Tool（子 Agent 作为工具）">
              <Select
                mode="multiple"
                placeholder="选择要作为工具调用的子 Agent"
                options={agentOptions}
                allowClear
              />
            </Form.Item>

            <Form.Item name="input_guardrails" label="Input Guardrails">
              <Select
                mode="multiple"
                placeholder="选择要启用的输入安全护栏"
                options={guardrailOptions}
                allowClear
              />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={saving}>
                  {isEdit ? '保存' : '创建'}
                </Button>
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
