import { useState } from 'react';
import {
  Card, Row, Col, Tag, Button, Modal, Typography, Space, App,
  Empty, Spin, Input, Select, Form, theme,
} from 'antd';
import {
  RobotOutlined,
  BranchesOutlined,
  QuestionCircleOutlined,
  SearchOutlined,
  BarChartOutlined,
  FileTextOutlined,
  CodeOutlined,
  TranslationOutlined,
  CustomerServiceOutlined,
  FileSearchOutlined,
  ClusterOutlined,
  PlusOutlined,
  SyncOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type {
  AgentTemplateItem,
  TemplateInstantiateResult,
} from '../../services/agentTemplateService';
import { agentService } from '../../services/agentService';
import {
  useTemplateList,
  useSeedBuiltinTemplates,
  useInstantiateTemplate,
} from '../../hooks/useTemplateQueries';

const { Title, Paragraph, Text } = Typography;

const iconMap: Record<string, React.ReactNode> = {
  RobotOutlined: <RobotOutlined />,
  BranchesOutlined: <BranchesOutlined />,
  QuestionCircleOutlined: <QuestionCircleOutlined />,
  SearchOutlined: <SearchOutlined />,
  BarChartOutlined: <BarChartOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  CodeOutlined: <CodeOutlined />,
  TranslationOutlined: <TranslationOutlined />,
  CustomerServiceOutlined: <CustomerServiceOutlined />,
  FileSearchOutlined: <FileSearchOutlined />,
  ClusterOutlined: <ClusterOutlined />,
};

const categoryColorMap: Record<string, string> = {
  routing: 'magenta',
  'customer-support': 'orange',
  research: 'cyan',
  analytics: 'blue',
  content: 'green',
  development: 'purple',
  general: 'default',
};

const categoryLabelMap: Record<string, string> = {
  routing: '路由调度',
  'customer-support': '客户服务',
  research: '调研分析',
  analytics: '数据分析',
  content: '内容创作',
  development: '开发辅助',
  general: '通用',
};

const TemplatePage: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [currentTemplate, setCurrentTemplate] = useState<AgentTemplateItem | null>(null);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);

  // TanStack Query
  const { data: listData, isLoading: loading } = useTemplateList({ category: categoryFilter, limit: 100 });
  const templates = listData?.data ?? [];

  const seedMutation = useSeedBuiltinTemplates();
  const instantiateMutation = useInstantiateTemplate();

  /* 导入向导状态 */
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardTemplate, setWizardTemplate] = useState<AgentTemplateItem | null>(null);
  const [wizardPreview, setWizardPreview] = useState<TemplateInstantiateResult | null>(null);
  const [wizardLoading, setWizardLoading] = useState(false);
  const [form] = Form.useForm();

  const handleSeed = async () => {
    const result = await seedMutation.mutateAsync();
    if (result.created > 0) {
      message.success(`已初始化 ${result.created} 个内置模板`);
    } else {
      message.info('内置模板已是最新');
    }
  };

  /* 打开导入向导 */
  const openWizard = async (tpl: AgentTemplateItem) => {
    setWizardTemplate(tpl);
    setWizardOpen(true);
    setWizardLoading(true);
    try {
      const preview = await instantiateMutation.mutateAsync({ id: tpl.id });
      setWizardPreview(preview);
      form.setFieldsValue({
        name: `${tpl.name}-${Date.now().toString(36)}`,
        description: tpl.description,
        instructions: (preview.config.instructions as string) ?? '',
      });
    } finally {
      setWizardLoading(false);
    }
  };

  /* 确认创建 Agent */
  const handleCreateFromTemplate = async () => {
    if (!wizardTemplate || !wizardPreview) return;
    try {
      const values = await form.validateFields();
      const config = { ...wizardPreview.config };
      if (values.instructions) config.instructions = values.instructions;

      await agentService.create({
        name: values.name,
        description: values.description || wizardTemplate.description,
        instructions: (config.instructions as string) ?? '',
        tool_groups: (config.tools as string[]) ?? [],
        handoffs: (config.handoffs as string[]) ?? [],
      });
      message.success(`Agent "${values.name}" 创建成功`);
      setWizardOpen(false);
      form.resetFields();
      navigate('/agents');
    } catch (err) {
      if (err instanceof Error) message.error(err.message);
    }
  };

  const filteredTemplates = templates.filter((t) => {
    if (!searchText) return true;
    const q = searchText.toLowerCase();
    return (
      t.name.toLowerCase().includes(q) ||
      t.display_name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q)
    );
  });

  const categories = [...new Set(templates.map((t) => t.category))].sort();

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>Agent 模板市场</Title>
        <Space>
          <Input.Search
            placeholder="搜索模板..."
            allowClear
            style={{ width: 250 }}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <Select
            placeholder="全部分类"
            allowClear
            style={{ width: 140 }}
            onChange={(v) => setCategoryFilter(v)}
            options={categories.map((c) => ({ label: categoryLabelMap[c] ?? c, value: c }))}
          />
          <Button icon={<SyncOutlined />} onClick={handleSeed}>
            同步内置模板
          </Button>
        </Space>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
      ) : filteredTemplates.length === 0 ? (
        <Empty description="暂无模板">
          <Button type="primary" icon={<SyncOutlined />} onClick={handleSeed}>
            初始化内置模板
          </Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {filteredTemplates.map((tpl) => (
            <Col key={tpl.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                style={{ height: '100%' }}
                actions={[
                  <span key="preview" onClick={() => { setCurrentTemplate(tpl); setPreviewOpen(true); }}>
                    <EyeOutlined /> 查看
                  </span>,
                  <span key="create" onClick={() => openWizard(tpl)}>
                    <PlusOutlined /> 使用
                  </span>,
                ]}
              >
                <Card.Meta
                  avatar={
                    <div style={{ fontSize: 32, color: token.colorPrimary }}>
                      {iconMap[tpl.icon] ?? <RobotOutlined />}
                    </div>
                  }
                  title={
                    <Space>
                      {tpl.display_name}
                      {tpl.is_builtin && <Tag color="gold">内置</Tag>}
                    </Space>
                  }
                  description={
                    <div>
                      <Tag color={categoryColorMap[tpl.category] ?? 'default'}>
                        {categoryLabelMap[tpl.category] ?? tpl.category}
                      </Tag>
                      <Paragraph
                        ellipsis={{ rows: 2 }}
                        style={{ marginTop: 8, marginBottom: 0, color: token.colorTextSecondary }}
                      >
                        {tpl.description || '暂无描述'}
                      </Paragraph>
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* 详情弹窗 */}
      <Modal
        title={currentTemplate?.display_name || '模板详情'}
        open={previewOpen}
        onCancel={() => { setPreviewOpen(false); setCurrentTemplate(null); }}
        footer={[
          <Button key="close" onClick={() => setPreviewOpen(false)}>关闭</Button>,
          <Button
            key="use"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => { setPreviewOpen(false); if (currentTemplate) openWizard(currentTemplate); }}
          >
            使用此模板
          </Button>,
        ]}
        width={700}
      >
        {currentTemplate && (
          <div>
            <Space style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 36, color: token.colorPrimary }}>
                {iconMap[currentTemplate.icon] ?? <RobotOutlined />}
              </div>
              <div>
                <Text strong style={{ fontSize: 18 }}>{currentTemplate.display_name}</Text>
                <br />
                <Text type="secondary">{currentTemplate.name}</Text>
              </div>
              {currentTemplate.is_builtin && <Tag color="gold">内置</Tag>}
              <Tag color={categoryColorMap[currentTemplate.category] ?? 'default'}>
                {categoryLabelMap[currentTemplate.category] ?? currentTemplate.category}
              </Tag>
            </Space>
            <Paragraph>{currentTemplate.description}</Paragraph>
            <Title level={5}>Agent 配置</Title>
            <pre style={{
              background: token.colorFillQuaternary,
              padding: 16,
              borderRadius: 8,
              maxHeight: 400,
              overflow: 'auto',
              fontSize: 13,
            }}>
              {JSON.stringify(currentTemplate.config, null, 2)}
            </pre>
          </div>
        )}
      </Modal>

      {/* 导入向导弹窗 */}
      <Modal
        title={`从模板创建 Agent — ${wizardTemplate?.display_name ?? ''}`}
        open={wizardOpen}
        onCancel={() => { setWizardOpen(false); form.resetFields(); }}
        onOk={handleCreateFromTemplate}
        okText="创建 Agent"
        confirmLoading={wizardLoading}
        width={640}
      >
        <Spin spinning={wizardLoading}>
          <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
            <Form.Item
              name="name"
              label="Agent 名称"
              rules={[
                { required: true, message: '请输入 Agent 名称' },
                { min: 3, max: 64, message: '名称长度 3-64 字符' },
              ]}
            >
              <Input placeholder="输入唯一名称" />
            </Form.Item>
            <Form.Item name="description" label="描述">
              <Input.TextArea rows={2} placeholder="Agent 描述" />
            </Form.Item>
            <Form.Item name="instructions" label="指令（可自定义）">
              <Input.TextArea rows={4} placeholder="Agent 行为指令" />
            </Form.Item>
          </Form>
          {wizardPreview && (
            <div>
              <Title level={5}>模板配置预览</Title>
              <pre style={{
                background: token.colorFillQuaternary,
                padding: 12,
                borderRadius: 8,
                maxHeight: 200,
                overflow: 'auto',
                fontSize: 12,
              }}>
                {JSON.stringify(wizardPreview.config, null, 2)}
              </pre>
            </div>
          )}
        </Spin>
      </Modal>
    </div>
  );
};

export default TemplatePage;
