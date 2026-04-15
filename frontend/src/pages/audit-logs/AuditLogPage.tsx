import React, { useState } from 'react';
import { Table, Card, Tag, Input, Select, Space, Tooltip } from 'antd';
import { AuditOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import type { ColumnsType } from 'antd/es/table';
import type { AuditLog } from '../../services/auditLogService';
import { useAuditLogList } from '../../hooks/useAuditLogQueries';

const { Search } = Input;

const ACTION_COLORS: Record<string, string> = {
  CREATE: 'green',
  UPDATE: 'blue',
  DELETE: 'red',
};

const AuditLogPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [actionFilter, setActionFilter] = useState<string | undefined>();
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string | undefined>();
  const [resourceIdFilter, setResourceIdFilter] = useState<string | undefined>();

  const { data: listData, isLoading: loading } = useAuditLogList({
    limit: pageSize,
    offset: (page - 1) * pageSize,
    action: actionFilter,
    resource_type: resourceTypeFilter,
    resource_id: resourceIdFilter,
  });
  const data = listData?.data ?? [];
  const total = listData?.total ?? 0;

  const columns: ColumnsType<AuditLog> = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 100,
      render: (v: string) => <Tag color={ACTION_COLORS[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '资源类型',
      dataIndex: 'resource_type',
      key: 'resource_type',
      width: 140,
    },
    {
      title: '资源 ID',
      dataIndex: 'resource_id',
      key: 'resource_id',
      width: 220,
      ellipsis: true,
      render: (v: string | null) => v ?? '-',
    },
    {
      title: '用户',
      dataIndex: 'user_id',
      key: 'user_id',
      width: 120,
      render: (v: string | null) => v ?? <Tag>匿名</Tag>,
    },
    {
      title: 'IP 地址',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 140,
      render: (v: string | null) => v ?? '-',
    },
    {
      title: '状态码',
      dataIndex: 'status_code',
      key: 'status_code',
      width: 80,
      render: (v: number | null) => {
        if (v === null) return '-';
        const color = v < 300 ? 'green' : v < 400 ? 'blue' : 'red';
        return <Tag color={color}>{v}</Tag>;
      },
    },
    {
      title: 'Request ID',
      dataIndex: 'request_id',
      key: 'request_id',
      width: 200,
      ellipsis: true,
      render: (v: string | null) => v ? <Tooltip title={v}><span>{v}</span></Tooltip> : '-',
    },
  ];

  return (
    <PageContainer
      title="审计日志"
      icon={<AuditOutlined />}
      description="查看系统操作审计日志"
    >
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="操作类型"
            allowClear
            style={{ width: 120 }}
            value={actionFilter}
            onChange={(v) => { setActionFilter(v); setPage(1); }}
            options={[
              { label: 'CREATE', value: 'CREATE' },
              { label: 'UPDATE', value: 'UPDATE' },
              { label: 'DELETE', value: 'DELETE' },
            ]}
          />
          <Search
            placeholder="资源类型"
            allowClear
            style={{ width: 160 }}
            onSearch={(v) => { setResourceTypeFilter(v || undefined); setPage(1); }}
          />
          <Search
            placeholder="资源 ID"
            allowClear
            style={{ width: 220 }}
            onSearch={(v) => { setResourceIdFilter(v || undefined); setPage(1); }}
          />
        </Space>
        <Table<AuditLog>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, s) => { setPage(p); setPageSize(s); },
          }}
          size="small"
          scroll={{ x: 1200 }}
        />
      </Card>
    </PageContainer>
  );
};

export default AuditLogPage;
