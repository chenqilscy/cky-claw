import { useState, useCallback } from 'react';
import { App, Button, Card, Col, Descriptions, Drawer, Empty, Input, Modal, Row, Select, Space, Spin, Tag, Typography } from 'antd';
import {
  BugOutlined,
  CaretRightOutlined,
  PauseCircleOutlined,
  StepForwardOutlined,
  StopOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { debugService } from '../../services/debugService';
import type { DebugSession, DebugContext } from '../../services/debugService';
import { agentService } from '../../services/agentService';
import type { AgentConfig } from '../../services/agentService';

const { Text, Title } = Typography;
const { TextArea } = Input;

const stateColor: Record<string, string> = {
  idle: 'default',
  running: 'processing',
  paused: 'warning',
  completed: 'success',
  failed: 'error',
  timeout: 'error',
};

const stateLabel: Record<string, string> = {
  idle: '空闲',
  running: '运行中',
  paused: '已暂停',
  completed: '已完成',
  failed: '已失败',
  timeout: '超时',
};

const modeLabel: Record<string, string> = {
  step_turn: '按轮步进',
  step_tool: '按工具步进',
  continue: '连续运行',
};

const DebugPage: React.FC = () => {
  const { message } = App.useApp();

  // 列表状态
  const [sessions, setSessions] = useState<DebugSession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [stateFilter, setStateFilter] = useState<string | undefined>();

  // 创建对话框
  const [createOpen, setCreateOpen] = useState(false);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [createForm, setCreateForm] = useState({ agent_id: '', input_message: '', mode: 'step_turn' });
  const [creating, setCreating] = useState(false);

  // 详情抽屉
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeSession, setActiveSession] = useState<DebugSession | null>(null);
  const [context, setContext] = useState<DebugContext | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  /** 加载会话列表 */
  const fetchSessions = useCallback(async (params?: { state?: string }) => {
    setLoading(true);
    try {
      const res = await debugService.list({ state: params?.state, limit: 50 });
      setSessions(res.items);
      setTotal(res.total);
    } catch {
      message.error('加载调试会话失败');
    } finally {
      setLoading(false);
    }
  }, [message]);

  /** 加载 Agent 列表（创建时） */
  const fetchAgents = useCallback(async () => {
    setAgentsLoading(true);
    try {
      const res = await agentService.list({ limit: 200 });
      setAgents(res.items);
    } catch {
      message.error('加载 Agent 列表失败');
    } finally {
      setAgentsLoading(false);
    }
  }, [message]);

  /** 创建调试会话 */
  const handleCreate = async () => {
    if (!createForm.agent_id || !createForm.input_message.trim()) {
      message.warning('请选择 Agent 并输入消息');
      return;
    }
    setCreating(true);
    try {
      const session = await debugService.create({
        agent_id: createForm.agent_id,
        input_message: createForm.input_message.trim(),
        mode: createForm.mode,
      });
      message.success('调试会话已创建');
      setCreateOpen(false);
      setCreateForm({ agent_id: '', input_message: '', mode: 'step_turn' });
      setSessions((prev) => [session, ...prev]);
      setTotal((prev) => prev + 1);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败');
    } finally {
      setCreating(false);
    }
  };

  /** 打开详情抽屉 */
  const openDrawer = async (session: DebugSession) => {
    setActiveSession(session);
    setDrawerOpen(true);
    setContext(null);
    if (session.state === 'paused') {
      await fetchContext(session.id);
    }
  };

  /** 获取暂停上下文 */
  const fetchContext = async (id: string) => {
    setContextLoading(true);
    try {
      const ctx = await debugService.getContext(id);
      setContext(ctx);
    } catch {
      setContext(null);
    } finally {
      setContextLoading(false);
    }
  };

  /** 刷新当前会话 */
  const refreshActiveSession = async (id: string) => {
    try {
      const s = await debugService.get(id);
      setActiveSession(s);
      setSessions((prev) => prev.map((x) => (x.id === id ? s : x)));
      if (s.state === 'paused') {
        await fetchContext(id);
      } else {
        setContext(null);
      }
    } catch {
      message.error('刷新失败');
    }
  };

  /** 单步执行 */
  const handleStep = async () => {
    if (!activeSession) return;
    setActionLoading(true);
    try {
      await debugService.step(activeSession.id);
      message.success('已发送 Step 指令');
      await refreshActiveSession(activeSession.id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '步进失败');
    } finally {
      setActionLoading(false);
    }
  };

  /** 继续执行 */
  const handleContinue = async () => {
    if (!activeSession) return;
    setActionLoading(true);
    try {
      await debugService.continue(activeSession.id);
      message.success('已发送 Continue 指令');
      await refreshActiveSession(activeSession.id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '继续失败');
    } finally {
      setActionLoading(false);
    }
  };

  /** 终止会话 */
  const handleStop = async () => {
    if (!activeSession) return;
    setActionLoading(true);
    try {
      await debugService.stop(activeSession.id);
      message.success('调试会话已终止');
      await refreshActiveSession(activeSession.id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '终止失败');
    } finally {
      setActionLoading(false);
    }
  };

  const columns: ProColumns<DebugSession>[] = [
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 160,
      render: (_, r) => <Text strong>{r.agent_name}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'state',
      width: 100,
      render: (_, r) => <Tag color={stateColor[r.state] || 'default'}>{stateLabel[r.state] || r.state}</Tag>,
    },
    {
      title: '模式',
      dataIndex: 'mode',
      width: 120,
      render: (_, r) => modeLabel[r.mode] || r.mode,
    },
    {
      title: '轮次',
      dataIndex: 'current_turn',
      width: 80,
      render: (_, r) => <Tag color="blue">{r.current_turn}</Tag>,
    },
    {
      title: '当前 Agent',
      dataIndex: 'current_agent_name',
      width: 140,
    },
    {
      title: '输入消息',
      dataIndex: 'input_message',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (_, r) => new Date(r.created_at).toLocaleString(),
    },
    {
      title: '操作',
      width: 100,
      render: (_, r) => (
        <Button type="link" size="small" icon={<BugOutlined />} onClick={() => openDrawer(r)}>
          调试
        </Button>
      ),
    },
  ];

  return (
    <>
      <Card
        title={<><BugOutlined style={{ marginRight: 8 }} />Agent 调试器</>}
        extra={
          <Space>
            <Select
              allowClear
              placeholder="按状态筛选"
              style={{ width: 140 }}
              value={stateFilter}
              onChange={(v) => { setStateFilter(v); fetchSessions({ state: v }); }}
              options={Object.entries(stateLabel).map(([k, v]) => ({ value: k, label: v }))}
            />
            <Button icon={<ReloadOutlined />} onClick={() => fetchSessions({ state: stateFilter })}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => { setCreateOpen(true); fetchAgents(); }}
            >
              新建调试
            </Button>
          </Space>
        }
      >
        <ProTable<DebugSession>
          rowKey="id"
          search={false}
          options={false}
          loading={loading}
          dataSource={sessions}
          columns={columns}
          pagination={{ total, pageSize: 20, showSizeChanger: false }}
          request={async () => {
            await fetchSessions({ state: stateFilter });
            return { data: sessions, total, success: true };
          }}
        />
      </Card>

      {/* 创建调试会话 */}
      <Modal
        title="新建调试会话"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        confirmLoading={creating}
        okText="创建"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>选择 Agent</Text>
            <Select
              showSearch
              loading={agentsLoading}
              placeholder="搜索并选择 Agent"
              style={{ width: '100%', marginTop: 4 }}
              value={createForm.agent_id || undefined}
              onChange={(v) => setCreateForm((p) => ({ ...p, agent_id: v }))}
              optionFilterProp="label"
              options={agents.map((a) => ({ value: a.id, label: a.name }))}
            />
          </div>
          <div>
            <Text strong>调试模式</Text>
            <Select
              style={{ width: '100%', marginTop: 4 }}
              value={createForm.mode}
              onChange={(v) => setCreateForm((p) => ({ ...p, mode: v }))}
              options={Object.entries(modeLabel).map(([k, v]) => ({ value: k, label: v }))}
            />
          </div>
          <div>
            <Text strong>输入消息</Text>
            <TextArea
              rows={3}
              maxLength={4096}
              showCount
              placeholder="输入要发送给 Agent 的消息"
              style={{ marginTop: 4 }}
              value={createForm.input_message}
              onChange={(e) => setCreateForm((p) => ({ ...p, input_message: e.target.value }))}
            />
          </div>
        </Space>
      </Modal>

      {/* 调试详情抽屉 */}
      <Drawer
        title={activeSession ? `调试 · ${activeSession.agent_name}` : '调试详情'}
        width={640}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setActiveSession(null); setContext(null); }}
        extra={
          activeSession && (
            <Space>
              <Button
                icon={<StepForwardOutlined />}
                loading={actionLoading}
                disabled={activeSession.state !== 'paused'}
                onClick={handleStep}
              >
                Step
              </Button>
              <Button
                icon={<CaretRightOutlined />}
                loading={actionLoading}
                disabled={activeSession.state !== 'paused'}
                onClick={handleContinue}
              >
                Continue
              </Button>
              <Button
                danger
                icon={<StopOutlined />}
                loading={actionLoading}
                disabled={activeSession.state === 'completed' || activeSession.state === 'failed'}
                onClick={handleStop}
              >
                Stop
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => activeSession && refreshActiveSession(activeSession.id)}
              >
                刷新
              </Button>
            </Space>
          )
        }
      >
        {activeSession && (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="状态">
                <Tag color={stateColor[activeSession.state] || 'default'}>
                  {stateLabel[activeSession.state] || activeSession.state}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="模式">{modeLabel[activeSession.mode] || activeSession.mode}</Descriptions.Item>
              <Descriptions.Item label="当前轮次">{activeSession.current_turn}</Descriptions.Item>
              <Descriptions.Item label="当前 Agent">{activeSession.current_agent_name}</Descriptions.Item>
              <Descriptions.Item label="输入消息" span={2}>
                <Text style={{ whiteSpace: 'pre-wrap' }}>{activeSession.input_message}</Text>
              </Descriptions.Item>
              {activeSession.result && (
                <Descriptions.Item label="结果" span={2}>
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{activeSession.result}</Text>
                </Descriptions.Item>
              )}
              {activeSession.error && (
                <Descriptions.Item label="错误" span={2}>
                  <Text type="danger">{activeSession.error}</Text>
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* 暂停上下文 */}
            {contextLoading ? (
              <Card><Spin /></Card>
            ) : context ? (
              <Card title={<><PauseCircleOutlined style={{ marginRight: 8 }} />暂停上下文</>} size="small">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="暂停原因">
                    <Tag>{context.reason}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="轮次">{context.turn}</Descriptions.Item>
                  <Descriptions.Item label="Agent">{context.agent_name}</Descriptions.Item>
                  <Descriptions.Item label="暂停时间">{context.paused_at || '-'}</Descriptions.Item>
                </Descriptions>

                {context.token_usage && Object.keys(context.token_usage).length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Title level={5}>Token 用量</Title>
                    <Row gutter={16}>
                      {Object.entries(context.token_usage).map(([k, v]) => (
                        <Col key={k} span={8}>
                          <Text type="secondary">{k}:</Text> <Text strong>{v}</Text>
                        </Col>
                      ))}
                    </Row>
                  </div>
                )}

                {context.last_llm_response && (
                  <div style={{ marginTop: 12 }}>
                    <Title level={5}>LLM 响应</Title>
                    <pre style={{ fontSize: 12, maxHeight: 200, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                      {JSON.stringify(context.last_llm_response, null, 2)}
                    </pre>
                  </div>
                )}

                {context.last_tool_calls && context.last_tool_calls.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Title level={5}>工具调用</Title>
                    <pre style={{ fontSize: 12, maxHeight: 200, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                      {JSON.stringify(context.last_tool_calls, null, 2)}
                    </pre>
                  </div>
                )}

                {context.recent_messages.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Title level={5}>最近消息 ({context.recent_messages.length})</Title>
                    <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                      {JSON.stringify(context.recent_messages, null, 2)}
                    </pre>
                  </div>
                )}
              </Card>
            ) : activeSession.state === 'paused' ? (
              <Empty description="暂无上下文数据" />
            ) : null}
          </Space>
        )}
      </Drawer>
    </>
  );
};

export default DebugPage;
