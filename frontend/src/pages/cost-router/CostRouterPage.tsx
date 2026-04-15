import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Input, Button, Tag, Space, Typography, Descriptions, Alert, Select } from 'antd';
import { SendOutlined, ThunderboltOutlined, SettingOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { useMutation } from '@tanstack/react-query';
import { costRouterService } from '../../services/costRouterService';
import type { ClassifyResponse, RecommendResponse } from '../../services/costRouterService';

const { TextArea } = Input;
const { Title, Text } = Typography;

const TIER_COLORS: Record<string, string> = {
  simple: 'green',
  moderate: 'blue',
  complex: 'orange',
  reasoning: 'purple',
  multimodal: 'red',
};

const TIER_LABELS: Record<string, string> = {
  simple: '简单',
  moderate: '中等',
  complex: '复杂',
  reasoning: '推理',
  multimodal: '多模态',
};

const CAPABILITY_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: '代码', value: 'code' },
  { label: '视觉', value: 'vision' },
  { label: '推理', value: 'reasoning' },
  { label: '函数调用', value: 'function_calling' },
];

const CostRouterPage: React.FC = () => {
  const navigate = useNavigate();
  const [inputText, setInputText] = useState('');
  const [capabilities, setCapabilities] = useState<string[]>([]);

  const classifyMutation = useMutation({
    mutationFn: (text: string) => costRouterService.classify({ text }),
  });

  const recommendMutation = useMutation({
    mutationFn: (text: string) =>
      costRouterService.recommend({ text }, capabilities.length > 0 ? capabilities : undefined),
  });

  const handleClassify = () => {
    if (!inputText.trim()) return;
    classifyMutation.mutate(inputText);
    recommendMutation.mutate(inputText);
  };

  const classifyResult: ClassifyResponse | undefined = classifyMutation.data;
  const recommendResult: RecommendResponse | undefined = recommendMutation.data;

  return (
    <PageContainer
      title="成本路由测试器"
      icon={<ThunderboltOutlined />}
      description="输入文本以测试复杂度分类和 Provider 推荐"
    >
      <Card style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <TextArea
            rows={4}
            placeholder="输入要分析的文本内容..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            maxLength={10000}
            showCount
          />

          <Space>
            <Select
              mode="multiple"
              placeholder="筛选 Provider 能力（可选）"
              style={{ minWidth: 280 }}
              options={CAPABILITY_OPTIONS}
              value={capabilities}
              onChange={setCapabilities}
              allowClear
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleClassify}
              loading={classifyMutation.isPending || recommendMutation.isPending}
              disabled={!inputText.trim()}
            >
              分析
            </Button>
          </Space>
        </Space>
      </Card>

      {classifyMutation.isError && (
        <Alert
          type="error"
          message="分类失败"
          description={String(classifyMutation.error)}
          style={{ marginTop: 16 }}
          showIcon
        />
      )}

      {recommendMutation.isError && (
        <Alert
          type="error"
          message="推荐失败"
          description={String(recommendMutation.error)}
          style={{ marginTop: 16 }}
          showIcon
        />
      )}

      {classifyResult && (
        <Card title="分类结果" style={{ marginTop: 16 }}>
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="推荐层级">
              <Tag color={TIER_COLORS[classifyResult.tier] ?? 'default'}>
                {TIER_LABELS[classifyResult.tier] ?? classifyResult.tier}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="文本长度">
              {classifyResult.text_length} 字符
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {recommendResult && (
        <Card title="Provider 推荐" style={{ marginTop: 16 }}>
          {recommendResult.provider_name ? (
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="分类层级">
                <Tag color={TIER_COLORS[recommendResult.tier] ?? 'default'}>
                  {TIER_LABELS[recommendResult.tier] ?? recommendResult.tier}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="推荐 Provider">
                <Text strong>{recommendResult.provider_name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Provider 层级">
                <Tag color={TIER_COLORS[recommendResult.provider_tier ?? ''] ?? 'default'}>
                  {TIER_LABELS[recommendResult.provider_tier ?? ''] ?? recommendResult.provider_tier}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
          ) : (
            <Alert
              type="warning"
              message="无匹配 Provider"
              description={
                <Space direction="vertical" size={4}>
                  <span>当前没有启用的 Provider 满足此层级需求。可能原因：</span>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    <li>没有已启用的 Provider（请先注册并开启）</li>
                    <li>所有 Provider 的层级 / 能力不符合筛选条件</li>
                  </ul>
                  <Button
                    size="small"
                    icon={<SettingOutlined />}
                    onClick={() => navigate('/providers')}
                    style={{ marginTop: 4 }}
                  >
                    前往模型厂商配置
                  </Button>
                </Space>
              }
              showIcon
            />
          )}
        </Card>
      )}

      <Card title="层级说明" style={{ marginTop: 16 }} size="small">
        <Space direction="vertical" size="small">
          <div><Tag color="green">简单 (simple)</Tag> 短文本问候、简单问答，适用轻量模型</div>
          <div><Tag color="blue">中等 (moderate)</Tag> 常规对话、文档总结，适用通用模型</div>
          <div><Tag color="orange">复杂 (complex)</Tag> 代码生成、架构设计，适用高能力模型</div>
          <div><Tag color="purple">推理 (reasoning)</Tag> 数学证明、逻辑推理，适用推理增强模型</div>
          <div><Tag color="red">多模态 (multimodal)</Tag> 图片分析、视觉理解，适用多模态模型</div>
        </Space>
      </Card>
    </PageContainer>
  );
};

export default CostRouterPage;
