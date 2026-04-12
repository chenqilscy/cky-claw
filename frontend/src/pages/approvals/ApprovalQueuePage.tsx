import { useState, useCallback } from 'react';
import { Tag, Button, Space, Modal, Input, App, Popconfirm, Badge, theme, Dropdown } from 'antd';
import { CheckOutlined, CloseOutlined, ReloadOutlined, WifiOutlined, MoreOutlined } from '@ant-design/icons';
import type { ProColumns, ActionType } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { useRef } from 'react';
import { approvalService } from '../../services/approvalService';
import { useApprovalWs } from '../../hooks/useApprovalWs';
import type { ApprovalItem } from '../../services/approvalService';
import { useResponsive } from '../../hooks/useResponsive';

const statusColorMap: Record<string, string> = {
  pending: 'orange',
  approved: 'green',
  rejected: 'red',
  timeout: 'default',
};

const triggerLabelMap: Record<string, string> = {
  tool_call: '工具调用',
  output: '输出审批',
  handoff: 'Handoff 审批',
};

const ApprovalQueuePage: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const { isMobile } = useResponsive();
  const actionRef = useRef<ActionType>(null);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectingId, setRejectingId] = useState<string>('');
  const [rejectComment, setRejectComment] = useState('');
  const [wsConnected, setWsConnected] = useState(false);

  // WebSocket 实时审批事件
  useApprovalWs({
    onEvent: (event) => {
      setWsConnected(true);
      if (event.type === 'approval_created') {
        message.info(`新审批请求: ${(event.data.agent_name as string) || 'Agent'}`);
        actionRef.current?.reload();
      } else if (event.type === 'approval_resolved') {
        actionRef.current?.reload();
      }
    },
  });
  const handleApprove = useCallback(async (id: string) => {
    try {
      await approvalService.resolve(id, { action: 'approve', comment: '批准' });
      message.success('已批准');
      actionRef.current?.reload();
    } catch {
      message.error('操作失败');
    }
  }, [message]);

  const handleRejectConfirm = useCallback(async () => {
    if (!rejectingId) return;
    try {
      await approvalService.resolve(rejectingId, {
        action: 'reject',
        comment: rejectComment || '拒绝',
      });
      message.success('已拒绝');
      setRejectModalOpen(false);
      setRejectingId('');
      setRejectComment('');
      actionRef.current?.reload();
    } catch {
      message.error('操作失败');
    }
  }, [rejectingId, rejectComment, message]);

  const columns: ProColumns<ApprovalItem>[] = [
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 140,
      render: (_, record) => <strong>{record.agent_name}</strong>,
    },
    {
      title: '触发类型',
      dataIndex: 'trigger',
      width: 110,
      render: (_, record) => (
        <Tag>{triggerLabelMap[record.trigger] || record.trigger}</Tag>
      ),
      valueType: 'select',
      valueEnum: {
        tool_call: { text: '工具调用' },
      },
    },
    {
      title: '请求内容',
      dataIndex: 'content',
      ellipsis: true,
      width: 260,
      search: false,
      hideInTable: isMobile,
      render: (_, record) => {
        const content = record.content as Record<string, unknown>;
        const toolName = content.tool_name as string | undefined;
        return toolName ? (
          <span>
            <Tag color="blue">{toolName}</Tag>
            <span style={{ color: token.colorTextTertiary, fontSize: 12 }}>
              {JSON.stringify(content.arguments || {}).slice(0, 80)}
            </span>
          </span>
        ) : (
          <span style={{ color: token.colorTextTertiary }}>{JSON.stringify(content).slice(0, 100)}</span>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      valueType: 'select',
      valueEnum: {
        pending: { text: '等待审批', status: 'Warning' },
        approved: { text: '已批准', status: 'Success' },
        rejected: { text: '已拒绝', status: 'Error' },
        timeout: { text: '已超时', status: 'Default' },
      },
      render: (_, record) => (
        <Tag color={statusColorMap[record.status] || 'default'}>
          {record.status === 'pending' ? '等待审批' :
           record.status === 'approved' ? '已批准' :
           record.status === 'rejected' ? '已拒绝' : '已超时'}
        </Tag>
      ),
    },
    {
      title: '审批意见',
      dataIndex: 'comment',
      width: 150,
      ellipsis: true,
      search: false,
      hideInTable: isMobile,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      valueType: 'dateTime',
      search: false,
      sorter: true,
      hideInTable: isMobile,
    },
    {
      title: '操作',
      key: 'action',
      width: isMobile ? 60 : 160,
      search: false,
      render: (_, record) => {
        if (record.status !== 'pending') return <span style={{ color: token.colorTextQuaternary }}>—</span>;
        if (isMobile) {
          return (
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'approve',
                    label: '批准',
                    icon: <CheckOutlined />,
                    onClick: () => {
                      Modal.confirm({
                        title: '确认批准此请求？',
                        onOk: () => handleApprove(record.id),
                      });
                    },
                  },
                  {
                    key: 'reject',
                    label: '拒绝',
                    icon: <CloseOutlined />,
                    danger: true,
                    onClick: () => {
                      setRejectingId(record.id);
                      setRejectComment('');
                      setRejectModalOpen(true);
                    },
                  },
                ],
              }}
              trigger={['click']}
            >
              <Button type="text" icon={<MoreOutlined />} style={{ minWidth: 44, minHeight: 44 }} />
            </Dropdown>
          );
        }
        return (
          <Space>
            <Popconfirm
              title="确认批准此请求？"
              onConfirm={() => handleApprove(record.id)}
            >
              <Button
                type="primary"
                size="small"
                icon={<CheckOutlined />}
              >
                批准
              </Button>
            </Popconfirm>
            <Button
              danger
              size="small"
              icon={<CloseOutlined />}
              onClick={() => {
                setRejectingId(record.id);
                setRejectComment('');
                setRejectModalOpen(true);
              }}
            >
              拒绝
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <>
      <ProTable<ApprovalItem>
        headerTitle="审批队列"
        actionRef={actionRef}
        rowKey="id"
        columns={columns}
        request={async (params) => {
          const { current, pageSize, status, ...rest } = params;
          const resp = await approvalService.list({
            status: status as string | undefined,
            limit: pageSize || 20,
            offset: ((current || 1) - 1) * (pageSize || 20),
            ...rest,
          });
          return {
            data: resp.data,
            total: resp.total,
            success: true,
          };
        }}
        pagination={{ defaultPageSize: 20 }}
        toolBarRender={() => [
          <Badge
            key="ws-status"
            status={wsConnected ? 'success' : 'default'}
            text={
              <span style={{ fontSize: 12, color: wsConnected ? token.colorSuccess : token.colorTextQuaternary }}>
                <WifiOutlined style={{ marginRight: 4 }} />
                {wsConnected ? '实时连接' : '未连接'}
              </span>
            }
          />,
          <Button
            key="refresh"
            icon={<ReloadOutlined />}
            onClick={() => actionRef.current?.reload()}
          >
            刷新
          </Button>,
        ]}
        search={{
          labelWidth: 'auto',
          defaultCollapsed: isMobile,
        }}
      />
      <Modal
        title="拒绝审批"
        open={rejectModalOpen}
        onOk={handleRejectConfirm}
        onCancel={() => {
          setRejectModalOpen(false);
          setRejectingId('');
          setRejectComment('');
        }}
        okText="确认拒绝"
        okButtonProps={{ danger: true }}
      >
        <p>请输入拒绝原因（可选）：</p>
        <Input.TextArea
          rows={3}
          value={rejectComment}
          onChange={(e) => setRejectComment(e.target.value)}
          placeholder="拒绝原因..."
        />
      </Modal>
    </>
  );
};

export default ApprovalQueuePage;
