import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Descriptions,
  message,
  Modal,
  Popconfirm,
  Space,
  Tag,
  Input,
} from 'antd';
import { ArrowLeftOutlined, DiffOutlined, RollbackOutlined } from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { agentVersionService } from '../../services/agentVersionService';
import type { AgentVersion, AgentVersionDiffResponse } from '../../services/agentVersionService';

const AgentVersionPage: React.FC = () => {
  const navigate = useNavigate();
  const { agentId } = useParams<{ agentId: string }>();
  const [data, setData] = useState<AgentVersion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // Snapshot detail modal
  const [detailVersion, setDetailVersion] = useState<AgentVersion | null>(null);

  // Diff modal
  const [diffData, setDiffData] = useState<AgentVersionDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [selectedRows, setSelectedRows] = useState<AgentVersion[]>([]);

  const fetchVersions = useCallback(async () => {
    if (!agentId) return;
    setLoading(true);
    try {
      const offset = (pagination.current - 1) * pagination.pageSize;
      const res = await agentVersionService.list(agentId, {
        limit: pagination.pageSize,
        offset,
      });
      setData(res.data);
      setTotal(res.total);
    } catch {
      message.error('获取版本列表失败');
    } finally {
      setLoading(false);
    }
  }, [agentId, pagination]);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  const handleRollback = async (version: number) => {
    if (!agentId) return;
    try {
      await agentVersionService.rollback(agentId, version);
      message.success(`已回滚至 v${version}`);
      fetchVersions();
    } catch {
      message.error('回滚失败');
    }
  };

  const handleDiff = async () => {
    if (!agentId || selectedRows.length !== 2) return;
    const sorted = [...selectedRows].sort((a, b) => a.version - b.version);
    setDiffLoading(true);
    try {
      const res = await agentVersionService.diff(agentId, sorted[0]!.version, sorted[1]!.version);
      setDiffData(res);
    } catch {
      message.error('版本对比失败');
    } finally {
      setDiffLoading(false);
    }
  };

  // Compute diff keys
  const diffKeys = useMemo(() => {
    if (!diffData) return [];
    const allKeys = new Set([
      ...Object.keys(diffData.snapshot_a),
      ...Object.keys(diffData.snapshot_b),
    ]);
    return Array.from(allKeys).sort();
  }, [diffData]);

  const columns: ProColumns<AgentVersion>[] = [
    {
      title: '版本',
      dataIndex: 'version',
      width: 80,
      render: (_, record) => <Tag color="blue">v{record.version}</Tag>,
    },
    {
      title: '变更说明',
      dataIndex: 'change_summary',
      ellipsis: true,
      render: (_, record) => record.change_summary || '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 200,
      render: (_, record) => new Date(record.created_at).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 200,
      render: (_, record) => (
        <Space>
          <a onClick={() => setDetailVersion(record)}>快照</a>
          <Popconfirm
            title={`确认回滚至 v${record.version}？`}
            description="将恢复该版本的所有配置字段，并创建新版本记录。"
            onConfirm={() => handleRollback(record.version)}
          >
            <a><RollbackOutlined /> 回滚</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/agents')}>
          返回 Agent 列表
        </Button>
        {selectedRows.length === 2 && (
          <Button
            icon={<DiffOutlined />}
            loading={diffLoading}
            onClick={handleDiff}
          >
            对比 v{Math.min(selectedRows[0]!.version, selectedRows[1]!.version)} ↔ v{Math.max(selectedRows[0]!.version, selectedRows[1]!.version)}
          </Button>
        )}
      </Space>

      <ProTable<AgentVersion>
        headerTitle="版本历史"
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        search={false}
        rowSelection={{
          type: 'checkbox',
          selectedRowKeys: selectedRows.map((r) => r.id),
          onChange: (_, rows) => {
            if (rows.length <= 2) {
              setSelectedRows(rows);
            } else {
              message.warning('最多选择 2 个版本进行对比');
            }
          },
        }}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total,
          onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
        }}
        tableAlertRender={({ selectedRowKeys }) =>
          selectedRowKeys.length > 0
            ? `已选择 ${selectedRowKeys.length} 个版本${selectedRowKeys.length === 2 ? '，可进行对比' : ''}`
            : false
        }
      />

      {/* 快照详情弹窗 */}
      <Modal
        title={detailVersion ? `v${detailVersion.version} 配置快照` : ''}
        open={!!detailVersion}
        onCancel={() => setDetailVersion(null)}
        footer={null}
        width={720}
      >
        {detailVersion && (
          <div>
            <Descriptions column={2} bordered size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="版本">v{detailVersion.version}</Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(detailVersion.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="变更说明" span={2}>
                {detailVersion.change_summary || '-'}
              </Descriptions.Item>
            </Descriptions>
            <Card size="small" title="完整快照">
              <Input.TextArea
                value={JSON.stringify(detailVersion.snapshot, null, 2)}
                autoSize={{ minRows: 8, maxRows: 24 }}
                readOnly
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Card>
          </div>
        )}
      </Modal>

      {/* 版本对比弹窗 */}
      <Modal
        title={diffData ? `v${diffData.version_a} ↔ v${diffData.version_b} 配置对比` : ''}
        open={!!diffData}
        onCancel={() => setDiffData(null)}
        footer={null}
        width={960}
      >
        {diffData && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#fafafa' }}>
                  <th style={{ border: '1px solid #f0f0f0', padding: '8px 12px', textAlign: 'left', width: 160 }}>字段</th>
                  <th style={{ border: '1px solid #f0f0f0', padding: '8px 12px', textAlign: 'left' }}>v{diffData.version_a}</th>
                  <th style={{ border: '1px solid #f0f0f0', padding: '8px 12px', textAlign: 'left' }}>v{diffData.version_b}</th>
                </tr>
              </thead>
              <tbody>
                {diffKeys.map((key) => {
                  const valA = JSON.stringify(diffData.snapshot_a[key] ?? null);
                  const valB = JSON.stringify(diffData.snapshot_b[key] ?? null);
                  const changed = valA !== valB;
                  return (
                    <tr key={key} style={{ background: changed ? '#fff7e6' : 'transparent' }}>
                      <td style={{ border: '1px solid #f0f0f0', padding: '6px 12px', fontWeight: changed ? 600 : 400 }}>
                        {key}
                        {changed && <Tag color="orange" style={{ marginLeft: 4 }}>变更</Tag>}
                      </td>
                      <td style={{ border: '1px solid #f0f0f0', padding: '6px 12px', fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                        {valA}
                      </td>
                      <td style={{ border: '1px solid #f0f0f0', padding: '6px 12px', fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                        {valB}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default AgentVersionPage;
