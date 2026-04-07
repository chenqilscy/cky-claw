import { useState } from 'react';
import { Button, Card, Col, Form, Input, App, Progress, Row, Slider, Space, Tag, Typography } from 'antd';
import { AimOutlined } from '@ant-design/icons';
import { intentService } from '../../services/intentService';
import type { IntentDetectResponse } from '../../services/intentService';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const IntentDetectionPage: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IntentDetectResponse | null>(null);

  const handleDetect = async () => {
    let values;
    try {
      values = await form.validateFields();
    } catch {
      return; // 表单校验失败
    }
    setLoading(true);
    try {
      const res = await intentService.detect({
        original_intent: values.original_intent,
        current_message: values.current_message,
        threshold: values.threshold,
      });
      setResult(res);
    } catch {
      message.error('检测失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const driftColor = result
    ? result.is_drifted ? '#ff4d4f' : '#52c41a'
    : undefined;

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <Title level={4}>意图飘移检测</Title>
      <Paragraph type="secondary">
        输入原始意图和当前消息，检测对话是否偏离初始主题。基于关键词 Jaccard 距离算法。
      </Paragraph>

      <Card>
        <Form form={form} layout="vertical" initialValues={{ threshold: 0.6 }}>
          <Form.Item
            name="original_intent"
            label="原始意图"
            rules={[{ required: true, message: '请输入原始意图' }]}
          >
            <TextArea rows={3} placeholder="例如：帮我写一个 Python 排序算法" />
          </Form.Item>
          <Form.Item
            name="current_message"
            label="当前消息"
            rules={[{ required: true, message: '请输入当前消息' }]}
          >
            <TextArea rows={3} placeholder="例如：今天天气怎么样？" />
          </Form.Item>
          <Form.Item name="threshold" label="飘移阈值">
            <Slider min={0} max={1} step={0.05} marks={{ 0: '0', 0.5: '0.5', 1: '1.0' }} />
          </Form.Item>
          <Button type="primary" icon={<AimOutlined />} onClick={handleDetect} loading={loading}>
            检测飘移
          </Button>
        </Form>
      </Card>

      {result && (
        <Card style={{ marginTop: 16 }} title="检测结果">
          <Row gutter={[24, 16]}>
            <Col span={12}>
              <Text strong>飘移分数</Text>
              <Progress
                percent={Math.round(result.drift_score * 100)}
                strokeColor={driftColor}
                format={(_p) => `${(result.drift_score * 100).toFixed(1)}%`}
                style={{ marginTop: 8 }}
              />
            </Col>
            <Col span={12}>
              <Text strong>判定结果</Text>
              <div style={{ marginTop: 8 }}>
                {result.is_drifted
                  ? <Tag color="red" style={{ fontSize: 14, padding: '4px 12px' }}>已飘移</Tag>
                  : <Tag color="green" style={{ fontSize: 14, padding: '4px 12px' }}>未飘移</Tag>}
                <Text type="secondary" style={{ marginLeft: 8 }}>阈值: {result.threshold}</Text>
              </div>
            </Col>
          </Row>
          <Row gutter={[24, 16]} style={{ marginTop: 16 }}>
            <Col span={12}>
              <Text strong>原始关键词</Text>
              <div style={{ marginTop: 8 }}>
                <Space wrap>
                  {result.original_keywords.map((kw) => (
                    <Tag key={kw} color="blue">{kw}</Tag>
                  ))}
                  {result.original_keywords.length === 0 && <Text type="secondary">无关键词</Text>}
                </Space>
              </div>
            </Col>
            <Col span={12}>
              <Text strong>当前关键词</Text>
              <div style={{ marginTop: 8 }}>
                <Space wrap>
                  {result.current_keywords.map((kw) => (
                    <Tag key={kw} color="orange">{kw}</Tag>
                  ))}
                  {result.current_keywords.length === 0 && <Text type="secondary">无关键词</Text>}
                </Space>
              </div>
            </Col>
          </Row>
        </Card>
      )}
    </div>
  );
};

export default IntentDetectionPage;
