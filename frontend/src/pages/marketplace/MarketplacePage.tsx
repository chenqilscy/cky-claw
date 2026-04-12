import { useState } from 'react';
import {
  Card, Row, Col, Tag, Button, Typography, Space, App,
  Empty, Spin, Input, Select, Rate, Modal, List, Form, InputNumber,
} from 'antd';
import {
  ShopOutlined,
  DownloadOutlined,
  StarOutlined,
  SearchOutlined,
  CloudUploadOutlined,
  CloudDownloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { marketplaceService } from '../../services/marketplaceService';
import type { MarketplaceTemplate } from '../../services/marketplaceService';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const categoryLabelMap: Record<string, string> = {
  routing: '路由调度',
  'customer-support': '客户服务',
  research: '调研分析',
  analytics: '数据分析',
  content: '内容创作',
  development: '开发辅助',
  general: '通用',
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

const MarketplacePage: React.FC = () => {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const [sortBy, setSortBy] = useState('downloads');
  const [detailOpen, setDetailOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [installOpen, setInstallOpen] = useState(false);
  const [current, setCurrent] = useState<MarketplaceTemplate | null>(null);
  const [form] = Form.useForm();
  const [installForm] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['marketplace', categoryFilter, searchText, sortBy],
    queryFn: () => marketplaceService.browse({
      category: categoryFilter,
      search: searchText || undefined,
      sort_by: sortBy,
      limit: 100,
    }),
  });

  const templates = data?.data ?? [];

  const { data: reviewsData } = useQuery({
    queryKey: ['marketplace-reviews', current?.id],
    queryFn: () => current ? marketplaceService.listReviews(current.id) : Promise.resolve({ data: [], total: 0 }),
    enabled: !!current && detailOpen,
  });

  const installMutation = useMutation({
    mutationFn: (params: { id: string; name: string }) =>
      marketplaceService.install(params.id, params.name),
    onSuccess: () => {
      message.success('安装成功');
      setInstallOpen(false);
      installForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['marketplace'] });
    },
  });

  const reviewMutation = useMutation({
    mutationFn: (params: { id: string; score: number; comment: string }) =>
      marketplaceService.submitReview(params.id, params.score, params.comment),
    onSuccess: () => {
      message.success('评价已提交');
      setReviewOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['marketplace-reviews', current?.id] });
    },
  });

  const handleInstall = (tpl: MarketplaceTemplate) => {
    setCurrent(tpl);
    setInstallOpen(true);
  };

  const handleDetail = (tpl: MarketplaceTemplate) => {
    setCurrent(tpl);
    setDetailOpen(true);
  };

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={3} style={{ margin: 0 }}>
            <ShopOutlined style={{ marginRight: 8 }} />
            Agent 模板市场
          </Title>
        </div>

        {/* 筛选栏 */}
        <Space wrap>
          <Input
            placeholder="搜索模板..."
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 240 }}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <Select
            placeholder="全部分类"
            allowClear
            style={{ width: 140 }}
            onChange={(v) => setCategoryFilter(v)}
            options={Object.entries(categoryLabelMap).map(([k, v]) => ({ label: v, value: k }))}
          />
          <Select
            value={sortBy}
            style={{ width: 140 }}
            onChange={(v) => setSortBy(v)}
            options={[
              { label: '最多下载', value: 'downloads' },
              { label: '最高评分', value: 'rating' },
              { label: '最新发布', value: 'newest' },
            ]}
          />
        </Space>

        {/* 模板卡片 */}
        {isLoading ? (
          <Spin tip="加载中..." style={{ display: 'block', textAlign: 'center', marginTop: 80 }} />
        ) : templates.length === 0 ? (
          <Empty description="暂无已发布的模板" />
        ) : (
          <Row gutter={[16, 16]}>
            {templates.map((tpl) => (
              <Col key={tpl.id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  hoverable
                  onClick={() => handleDetail(tpl)}
                  actions={[
                    <Button
                      key="install"
                      type="link"
                      icon={<CloudDownloadOutlined />}
                      onClick={(e) => { e.stopPropagation(); handleInstall(tpl); }}
                    >
                      安装
                    </Button>,
                    <Button
                      key="review"
                      type="link"
                      icon={<StarOutlined />}
                      onClick={(e) => { e.stopPropagation(); setCurrent(tpl); setReviewOpen(true); }}
                    >
                      评价
                    </Button>,
                  ]}
                >
                  <Card.Meta
                    title={
                      <Space>
                        {tpl.display_name}
                        {tpl.is_builtin && <Tag color="blue">内置</Tag>}
                      </Space>
                    }
                    description={
                      <div>
                        <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 8 }}>
                          {tpl.description}
                        </Paragraph>
                        <Space size="small" wrap>
                          <Tag color={categoryColorMap[tpl.category] ?? 'default'}>
                            {categoryLabelMap[tpl.category] ?? tpl.category}
                          </Tag>
                          <Text type="secondary">
                            <DownloadOutlined /> {tpl.downloads}
                          </Text>
                          <Text type="secondary">
                            <StarOutlined /> {tpl.rating.toFixed(1)} ({tpl.rating_count})
                          </Text>
                        </Space>
                      </div>
                    }
                  />
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Space>

      {/* 详情弹窗 */}
      <Modal
        title={current?.display_name}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={[
          <Button key="close" onClick={() => setDetailOpen(false)}>关闭</Button>,
          <Button
            key="install"
            type="primary"
            icon={<CloudDownloadOutlined />}
            onClick={() => { setDetailOpen(false); current && handleInstall(current); }}
          >
            安装
          </Button>,
        ]}
        width={640}
      >
        {current && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Paragraph>{current.description}</Paragraph>
            <Space>
              <Tag color={categoryColorMap[current.category] ?? 'default'}>
                {categoryLabelMap[current.category] ?? current.category}
              </Tag>
              <Text><DownloadOutlined /> {current.downloads} 次下载</Text>
              <Text><StarOutlined /> {current.rating.toFixed(1)} ({current.rating_count} 评价)</Text>
            </Space>
            <Title level={5}>评价</Title>
            {reviewsData && reviewsData.data.length > 0 ? (
              <List
                dataSource={reviewsData.data}
                renderItem={(r) => (
                  <List.Item>
                    <List.Item.Meta
                      title={<Rate disabled defaultValue={r.score} style={{ fontSize: 14 }} />}
                      description={r.comment || '（无评论）'}
                    />
                  </List.Item>
                )}
              />
            ) : (
              <Text type="secondary">暂无评价</Text>
            )}
          </Space>
        )}
      </Modal>

      {/* 安装弹窗 */}
      <Modal
        title={<><CloudUploadOutlined /> 安装模板 — {current?.display_name}</>}
        open={installOpen}
        onCancel={() => { setInstallOpen(false); installForm.resetFields(); }}
        onOk={() => installForm.submit()}
        confirmLoading={installMutation.isPending}
        okText="安装"
      >
        <Form
          form={installForm}
          layout="vertical"
          onFinish={(values) => current && installMutation.mutate({ id: current.id, name: values.agent_name })}
        >
          <Form.Item
            name="agent_name"
            label="Agent 名称"
            rules={[
              { required: true, message: '请输入 Agent 名称' },
              { min: 3, max: 64, message: '3-64 个字符' },
            ]}
          >
            <Input placeholder="输入新 Agent 名称" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 评价弹窗 */}
      <Modal
        title={<><StarOutlined /> 评价 — {current?.display_name}</>}
        open={reviewOpen}
        onCancel={() => { setReviewOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={reviewMutation.isPending}
        okText="提交"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => current && reviewMutation.mutate({
            id: current.id,
            score: values.score,
            comment: values.comment ?? '',
          })}
        >
          <Form.Item name="score" label="评分" rules={[{ required: true, message: '请选择评分' }]}>
            <InputNumber min={1} max={5} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="comment" label="评论">
            <TextArea rows={3} maxLength={2000} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default MarketplacePage;
