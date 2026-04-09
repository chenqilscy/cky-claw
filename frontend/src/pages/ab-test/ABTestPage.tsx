import { useState } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  App,
  Row,
  Select,
  Spin,
  Statistic,
  Tag,
  Typography,
} from 'antd';
import { ExperimentOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { abTestService } from '../../services/abTestService';
import type { ABTestModelResult } from '../../services/abTestService';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

const ABTestPage: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ABTestModelResult[]>([]);
  const [prompt, setPrompt] = useState<string>('');

  const handleRun = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      setResults([]);
      const res = await abTestService.run({
        prompt: values.prompt,
        models: values.models,
        provider_name: values.provider_name || undefined,
        max_tokens: values.max_tokens || 1024,
      });
      setPrompt(res.prompt);
      setResults(res.results);
    } catch {
      message.error('A/B 测试执行失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Card
        title={<span><ExperimentOutlined /> 多模型 A/B 测试</span>}
        style={{ marginBottom: 16 }}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="prompt"
            label="测试 Prompt"
            rules={[{ required: true, message: '请输入测试 Prompt' }]}
          >
            <TextArea rows={4} placeholder="输入要测试的 Prompt..." maxLength={10000} showCount />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="models"
                label="模型列表"
                rules={[
                  { required: true, message: '请选择至少 2 个模型' },
                  {
                    validator: (_, value) =>
                      value && value.length >= 2
                        ? Promise.resolve()
                        : Promise.reject(new Error('至少选择 2 个模型')),
                  },
                ]}
              >
                <Select
                  mode="tags"
                  placeholder="输入模型名称（如 gpt-4o, claude-3-sonnet）"
                  maxCount={5}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="provider_name" label="Provider（可选）">
                <Input placeholder="留空使用默认" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="max_tokens" label="最大 Token 数" initialValue={1024}>
                <InputNumber min={1} max={8192} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleRun}
            loading={loading}
          >
            开始测试
          </Button>
        </Form>
      </Card>

      {loading && (
        <Card>
          <Spin spinning>
            <div style={{ height: 100, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              正在并行调用模型...
            </div>
          </Spin>
        </Card>
      )}

      {results.length > 0 && (
        <div>
          <Card size="small" style={{ marginBottom: 12 }}>
            <Text strong>Prompt: </Text>
            <Text>{prompt}</Text>
          </Card>
          <Row gutter={16}>
            {results.map((r) => (
              <Col key={r.model} span={Math.max(8, Math.floor(24 / results.length))}>
                <Card
                  title={
                    <span>
                      <Tag color={r.error ? 'red' : 'blue'}>{r.model}</Tag>
                      {r.error && <Tag color="red">失败</Tag>}
                    </span>
                  }
                  size="small"
                  style={{ marginBottom: 16 }}
                >
                  <Row gutter={16} style={{ marginBottom: 12 }}>
                    <Col span={8}>
                      <Statistic
                        title="延迟"
                        value={r.latency_ms}
                        suffix="ms"
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="Prompt Tokens"
                        value={r.token_usage.prompt_tokens ?? 0}
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="输出 Tokens"
                        value={r.token_usage.completion_tokens ?? 0}
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                  </Row>
                  {r.error ? (
                    <Paragraph type="danger" style={{ fontSize: 12 }}>{r.error}</Paragraph>
                  ) : (
                    <div
                      style={{
                        maxHeight: 300,
                        overflowY: 'auto',
                        padding: 8,
                        background: '#fafafa',
                        borderRadius: 4,
                        fontSize: 13,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {r.output}
                    </div>
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      )}
    </div>
  );
};

export default ABTestPage;
