import { useState } from 'react';
import {
  Card, Row, Col, Statistic, Tag, Table, Tabs, Space, App,
  Progress, Button, Modal, Form, Input, Select, InputNumber,
} from 'antd';
import {
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { complianceService } from '../../services/complianceService';
import type { ControlPointItem, RetentionPolicyItem, ErasureRequestItem, ClassificationLabel } from '../../services/complianceService';

const classificationColors: Record<string, string> = {
  public: 'green',
  internal: 'blue',
  sensitive: 'orange',
  pii: 'red',
  phi: 'volcano',
};

const statusColors: Record<string, string> = {
  pending: 'gold',
  processing: 'blue',
  completed: 'green',
  failed: 'red',
  active: 'green',
  expired: 'default',
  deleted: 'red',
};

const CompliancePage: React.FC = () => {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [labelModalOpen, setLabelModalOpen] = useState(false);
  const [policyModalOpen, setPolicyModalOpen] = useState(false);
  const [labelForm] = Form.useForm();
  const [policyForm] = Form.useForm();

  const { data: dashboard } = useQuery({
    queryKey: ['compliance-dashboard'],
    queryFn: () => complianceService.getDashboard(),
  });

  const { data: labelsData, isLoading: labelsLoading } = useQuery({
    queryKey: ['compliance-labels'],
    queryFn: () => complianceService.listLabels({ limit: 100 }),
  });

  const { data: policiesData } = useQuery({
    queryKey: ['compliance-policies'],
    queryFn: () => complianceService.listRetentionPolicies(),
  });

  const { data: erasuresData } = useQuery({
    queryKey: ['compliance-erasures'],
    queryFn: () => complianceService.listErasureRequests(),
  });

  const { data: controlsData } = useQuery({
    queryKey: ['compliance-controls'],
    queryFn: () => complianceService.listControlPoints(),
  });

  const createLabelMutation = useMutation({
    mutationFn: (body: { resource_type: string; resource_id: string; classification: string; reason?: string }) =>
      complianceService.createLabel(body),
    onSuccess: () => { message.success('标签已创建'); setLabelModalOpen(false); labelForm.resetFields(); queryClient.invalidateQueries({ queryKey: ['compliance-labels'] }); },
  });

  const createPolicyMutation = useMutation({
    mutationFn: (body: { resource_type: string; classification: string; retention_days: number }) =>
      complianceService.createRetentionPolicy(body),
    onSuccess: () => { message.success('策略已创建'); setPolicyModalOpen(false); policyForm.resetFields(); queryClient.invalidateQueries({ queryKey: ['compliance-policies'] }); },
  });

  const labelColumns = [
    { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type' },
    { title: '资源 ID', dataIndex: 'resource_id', key: 'resource_id', ellipsis: true },
    {
      title: '分类', dataIndex: 'classification', key: 'classification',
      render: (v: string) => <Tag color={classificationColors[v] ?? 'default'}>{v.toUpperCase()}</Tag>,
    },
    { title: '自动检测', dataIndex: 'auto_detected', key: 'auto_detected', render: (v: boolean) => v ? '是' : '否' },
    { title: '原因', dataIndex: 'reason', key: 'reason', ellipsis: true },
  ];

  const policyColumns = [
    { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type' },
    {
      title: '分类', dataIndex: 'classification', key: 'classification',
      render: (v: string) => <Tag color={classificationColors[v] ?? 'default'}>{v.toUpperCase()}</Tag>,
    },
    { title: '保留天数', dataIndex: 'retention_days', key: 'retention_days' },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (v: string) => <Tag color={statusColors[v] ?? 'default'}>{v}</Tag>,
    },
  ];

  const erasureColumns = [
    { title: '目标用户', dataIndex: 'target_user_id', key: 'target_user_id', ellipsis: true },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (v: string) => <Tag color={statusColors[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '已扫描', dataIndex: 'scanned_resources', key: 'scanned_resources' },
    { title: '已删除', dataIndex: 'deleted_resources', key: 'deleted_resources' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
  ];

  const controlColumns = [
    { title: '编号', dataIndex: 'control_id', key: 'control_id' },
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '状态', dataIndex: 'is_satisfied', key: 'is_satisfied',
      render: (v: boolean) => v
        ? <Tag icon={<CheckCircleOutlined />} color="success">已满足</Tag>
        : <Tag icon={<ClockCircleOutlined />} color="warning">未满足</Tag>,
    },
  ];

  const tabItems = [
    {
      key: 'labels',
      label: '数据分类标签',
      children: (
        <>
          <Button icon={<PlusOutlined />} style={{ marginBottom: 16 }} onClick={() => setLabelModalOpen(true)}>新建标签</Button>
          <Table<ClassificationLabel> columns={labelColumns} dataSource={labelsData?.data ?? []} rowKey="id" loading={labelsLoading} size="small" />
        </>
      ),
    },
    {
      key: 'policies',
      label: '保留策略',
      children: (
        <>
          <Button icon={<PlusOutlined />} style={{ marginBottom: 16 }} onClick={() => setPolicyModalOpen(true)}>新建策略</Button>
          <Table<RetentionPolicyItem> columns={policyColumns} dataSource={policiesData?.data ?? []} rowKey="id" size="small" />
        </>
      ),
    },
    {
      key: 'erasures',
      label: '删除请求',
      children: <Table<ErasureRequestItem> columns={erasureColumns} dataSource={erasuresData?.data ?? []} rowKey="id" size="small" />,
    },
    {
      key: 'controls',
      label: 'SOC2 控制点',
      children: <Table<ControlPointItem> columns={controlColumns} dataSource={controlsData?.data ?? []} rowKey="id" size="small" />,
    },
  ];

  return (
    <PageContainer
      title="合规管理"
      icon={<SafetyCertificateOutlined />}
      description="数据分类、保留策略、SOC2 控制点与 Right-to-Erasure"
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 仪表盘概览 */}
        <Row gutter={16}>
          <Col span={6}>
            <Card>
              <Statistic title="控制点完成率" value={dashboard ? (dashboard.satisfaction_rate * 100) : 0} suffix="%" precision={0} />
              <Progress percent={dashboard ? dashboard.satisfaction_rate * 100 : 0} showInfo={false} size="small" />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="控制点"
                value={dashboard?.satisfied_control_points ?? 0}
                suffix={`/ ${dashboard?.total_control_points ?? 0}`}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="活跃保留策略" value={dashboard?.active_retention_policies ?? 0} prefix={<ClockCircleOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="待处理删除请求" value={dashboard?.pending_erasure_requests ?? 0} prefix={<DeleteOutlined />} />
            </Card>
          </Col>
        </Row>

        {/* Tabs */}
        <Card>
          <Tabs items={tabItems} />
        </Card>
      </Space>

      {/* 新建标签弹窗 */}
      <Modal
        title="新建数据分类标签"
        open={labelModalOpen}
        onCancel={() => { setLabelModalOpen(false); labelForm.resetFields(); }}
        onOk={() => labelForm.submit()}
        confirmLoading={createLabelMutation.isPending}
      >
        <Form form={labelForm} layout="vertical" onFinish={(v) => createLabelMutation.mutate(v)}>
          <Form.Item name="resource_type" label="资源类型" rules={[{ required: true }]}>
            <Select options={['trace', 'session', 'audit_log', 'agent'].map(v => ({ label: v, value: v }))} />
          </Form.Item>
          <Form.Item name="resource_id" label="资源 ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="classification" label="分类等级" rules={[{ required: true }]}>
            <Select options={['public', 'internal', 'sensitive', 'pii', 'phi'].map(v => ({ label: v.toUpperCase(), value: v }))} />
          </Form.Item>
          <Form.Item name="reason" label="原因">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新建策略弹窗 */}
      <Modal
        title="新建保留策略"
        open={policyModalOpen}
        onCancel={() => { setPolicyModalOpen(false); policyForm.resetFields(); }}
        onOk={() => policyForm.submit()}
        confirmLoading={createPolicyMutation.isPending}
      >
        <Form form={policyForm} layout="vertical" onFinish={(v) => createPolicyMutation.mutate(v)}>
          <Form.Item name="resource_type" label="资源类型" rules={[{ required: true }]}>
            <Select options={['trace', 'session', 'audit_log'].map(v => ({ label: v, value: v }))} />
          </Form.Item>
          <Form.Item name="classification" label="分类等级" rules={[{ required: true }]}>
            <Select options={['public', 'internal', 'sensitive', 'pii', 'phi'].map(v => ({ label: v.toUpperCase(), value: v }))} />
          </Form.Item>
          <Form.Item name="retention_days" label="保留天数" rules={[{ required: true }]}>
            <InputNumber min={1} max={3650} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default CompliancePage;
