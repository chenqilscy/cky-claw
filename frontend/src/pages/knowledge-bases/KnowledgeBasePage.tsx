import { useEffect, useMemo, useState } from 'react';
import { App, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Tag, Typography, Upload, Progress } from 'antd';
import { DatabaseOutlined, PlusOutlined, SearchOutlined, UploadOutlined, BuildOutlined, DeleteOutlined, ApartmentOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import KnowledgeGraphView from '../../components/KnowledgeGraphView';
import type { ColumnsType } from 'antd/es/table';
import {
  knowledgeBaseService,
  type KnowledgeBaseItem,
  type KnowledgeDocumentItem,
  type KnowledgeSearchResultItem,
  type GraphEntityItem,
  type GraphCommunityItem,
  type GraphSearchResultItem,
  type GraphBuildStatus,
} from '../../services/knowledgeBaseService';

const { Text } = Typography;

const KnowledgeBasePage: React.FC = () => {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<KnowledgeBaseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<KnowledgeBaseItem | null>(null);
  const [form] = Form.useForm();

  const [detailOpen, setDetailOpen] = useState(false);
  const [activeKB, setActiveKB] = useState<KnowledgeBaseItem | null>(null);
  const [activeTab, setActiveTab] = useState('documents');
  const [documents, setDocuments] = useState<KnowledgeDocumentItem[]>([]);
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResultItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchForm] = Form.useForm();

  // Graph state
  const [buildStatus, setBuildStatus] = useState<GraphBuildStatus | null>(null);
  const [building, setBuilding] = useState(false);
  const [entities, setEntities] = useState<GraphEntityItem[]>([]);
  const [entityTotal, setEntityTotal] = useState(0);
  const [communities, setCommunities] = useState<GraphCommunityItem[]>([]);
  const [graphSearchResults, setGraphSearchResults] = useState<GraphSearchResultItem[]>([]);
  const [graphSearching, setGraphSearching] = useState(false);
  const [graphSearchForm] = Form.useForm();

  const fetchList = async () => {
    setLoading(true);
    try {
      const res = await knowledgeBaseService.list({
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setItems(res.data);
      setTotal(res.total);
    } catch {
      message.error('加载知识库失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, [page, pageSize]);

  const columns: ColumnsType<KnowledgeBaseItem> = useMemo(() => [
    { title: '名称', dataIndex: 'name', key: 'name', width: 200 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      width: 80,
      render: (v: string) => {
        const color = v === 'graph' ? 'blue' : v === 'hybrid' ? 'purple' : 'default';
        return <Tag color={color}>{v || 'vector'}</Tag>;
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => openDetail(record)}>详情</Button>
          <Button size="small" onClick={() => openEdit(record)}>编辑</Button>
          <Button size="small" danger onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      ),
    },
  ], []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ embedding_model: 'hash-embedding-v1', chunk_size: 512, overlap: 64, mode: 'vector' });
    setModalOpen(true);
  };

  const openEdit = (record: KnowledgeBaseItem) => {
    setEditing(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      embedding_model: record.embedding_model,
      chunk_size: Number((record.chunk_strategy as Record<string, unknown>)?.chunk_size ?? 512),
      overlap: Number((record.chunk_strategy as Record<string, unknown>)?.overlap ?? 64),
      mode: record.mode || 'vector',
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        name: values.name,
        description: values.description,
        embedding_model: values.embedding_model,
        chunk_strategy: {
          chunk_size: values.chunk_size,
          overlap: values.overlap,
        },
        mode: values.mode,
      };

      if (editing) {
        await knowledgeBaseService.update(editing.id, payload);
      } else {
        await knowledgeBaseService.create(payload);
      }
      message.success(editing ? '更新成功' : '创建成功');
      setModalOpen(false);
      fetchList();
    } catch {
      // validation or api error
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await knowledgeBaseService.remove(id);
      message.success('删除成功');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const openDetail = async (record: KnowledgeBaseItem) => {
    setActiveKB(record);
    setDetailOpen(true);
    setActiveTab('documents');
    setSearchResults([]);
    setBuildStatus(null);
    setGraphSearchResults([]);
    try {
      const docs = await knowledgeBaseService.listDocuments(record.id);
      setDocuments(docs);
    } catch {
      message.error('加载文档失败');
    }
  };

  const handleUpload = async (file: File) => {
    if (!activeKB) return false;
    try {
      await knowledgeBaseService.uploadDocument(activeKB.id, file);
      message.success('上传并索引完成');
      const docs = await knowledgeBaseService.listDocuments(activeKB.id);
      setDocuments(docs);
    } catch {
      message.error('上传失败');
    }
    return false;
  };

  const handleSearch = async () => {
    if (!activeKB) return;
    try {
      const values = await searchForm.validateFields();
      setSearching(true);
      const res = await knowledgeBaseService.search(activeKB.id, {
        query: values.query,
        top_k: values.top_k,
        min_score: values.min_score,
      });
      setSearchResults(res.results);
    } catch {
      // validation or api error
    } finally {
      setSearching(false);
    }
  };

  // --- Graph handlers ---

  const handleBuildGraph = async () => {
    if (!activeKB) return;
    setBuilding(true);
    try {
      const res = await knowledgeBaseService.buildGraph(activeKB.id, {
        extract_model: 'gpt-4o-mini',
        chunk_size: 1024,
        overlap: 128,
      });
      message.info(`图谱构建已启动 (task: ${res.task_id})`);
      pollBuildStatus(res.task_id);
    } catch {
      message.error('构建图谱失败');
      setBuilding(false);
    }
  };

  const pollBuildStatus = async (taskId: string) => {
    if (!activeKB) return;
    const poll = async () => {
      try {
        const status = await knowledgeBaseService.getGraphStatus(activeKB!.id, taskId);
        setBuildStatus(status);
        if (status.status === 'completed') {
          message.success(`图谱构建完成：${status.entity_count} 实体, ${status.relation_count} 关系`);
          setBuilding(false);
          loadEntities();
          loadCommunities();
          return;
        }
        if (status.status === 'failed') {
          message.error(`图谱构建失败: ${status.error}`);
          setBuilding(false);
          return;
        }
        // 继续轮询
        setTimeout(poll, 2000);
      } catch {
        setBuilding(false);
      }
    };
    poll();
  };

  const loadEntities = async () => {
    if (!activeKB) return;
    try {
      const res = await knowledgeBaseService.listEntities(activeKB.id, { limit: 50 });
      setEntities(res.data);
      setEntityTotal(res.total);
    } catch {
      // ignore
    }
  };

  const loadCommunities = async () => {
    if (!activeKB) return;
    try {
      const res = await knowledgeBaseService.listCommunities(activeKB.id, { limit: 50 });
      setCommunities(res.data);
    } catch {
      // ignore
    }
  };

  const handleGraphSearch = async () => {
    if (!activeKB) return;
    try {
      const values = await graphSearchForm.validateFields();
      setGraphSearching(true);
      const res = await knowledgeBaseService.graphSearch(activeKB.id, {
        query: values.query,
        top_k: values.top_k || 10,
        max_depth: values.max_depth || 2,
        search_mode: values.search_mode || 'hybrid',
      });
      setGraphSearchResults(res.results);
    } catch {
      // validation or api error
    } finally {
      setGraphSearching(false);
    }
  };

  const handleDeleteGraph = async () => {
    if (!activeKB) return;
    try {
      await knowledgeBaseService.deleteGraph(activeKB.id);
      message.success('图谱数据已清空');
      setEntities([]);
      setEntityTotal(0);
      setCommunities([]);
      setBuildStatus(null);
    } catch {
      message.error('清空图谱失败');
    }
  };

  // Tab 切换时加载数据
  const handleTabChange = (key: string) => {
    setActiveTab(key);
    if (key === 'graph') {
      // 图谱可视化不需要额外加载，KnowledgeGraphView 自管理
    } else if (key === 'entities') {
      loadEntities();
    } else if (key === 'communities') {
      loadCommunities();
    }
  };

  const isGraphMode = activeKB?.mode === 'graph' || activeKB?.mode === 'hybrid';

  const detailTabs = useMemo(() => {
    const tabs: { key: string; label: string; icon?: React.ReactNode; children: React.ReactNode }[] = [
      {
        key: 'documents',
        label: '文档',
        children: (
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Upload beforeUpload={handleUpload} showUploadList={false}>
              <Button icon={<UploadOutlined />}>上传文档并索引</Button>
            </Upload>
            <Table<KnowledgeDocumentItem>
              rowKey="id"
              size="small"
              dataSource={documents}
              pagination={false}
              columns={[
                { title: '文件名', dataIndex: 'filename' },
                { title: '类型', dataIndex: 'media_type', width: 140 },
                { title: '大小', dataIndex: 'size_bytes', width: 100, render: (v: number) => `${Math.round(v / 1024)} KB` },
                { title: '状态', dataIndex: 'status', width: 90, render: (v: string) => <Tag color={v === 'indexed' ? 'green' : 'processing'}>{v}</Tag> },
                { title: '分块数', dataIndex: 'chunk_count', width: 80 },
              ]}
            />
          </Space>
        ),
      },
    ];

    if (isGraphMode) {
      tabs.push(
        {
          key: 'graph',
          label: '图谱',
          icon: <ApartmentOutlined />,
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Space>
                <Button
                  type="primary"
                  icon={<BuildOutlined />}
                  loading={building}
                  onClick={handleBuildGraph}
                >
                  构建图谱
                </Button>
                <Button
                  icon={<DeleteOutlined />}
                  danger
                  onClick={handleDeleteGraph}
                >
                  清空图谱
                </Button>
              </Space>
              {buildStatus && building && (
                <Progress
                  percent={Math.round(buildStatus.progress * 100)}
                  status={buildStatus.status === 'failed' ? 'exception' : 'active'}
                  format={() => `${buildStatus.entity_count} 实体 / ${buildStatus.relation_count} 关系`}
                />
              )}
              {activeKB && <KnowledgeGraphView kbId={activeKB.id} />}
            </Space>
          ),
        },
        {
          key: 'entities',
          label: '实体',
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Text type="secondary">共 {entityTotal} 个实体</Text>
              <Table<GraphEntityItem>
                rowKey="id"
                size="small"
                dataSource={entities}
                pagination={{ pageSize: 10 }}
                columns={[
                  { title: '名称', dataIndex: 'name', width: 180 },
                  { title: '类型', dataIndex: 'entity_type', width: 120, render: (v: string) => <Tag>{v}</Tag> },
                  { title: '描述', dataIndex: 'description', ellipsis: true },
                  { title: '置信度', dataIndex: 'confidence', width: 80, render: (v: number) => <Text>{(v * 100).toFixed(0)}%</Text> },
                  { title: '标签', dataIndex: 'confidence_label', width: 100, render: (v: string) => {
                    const color = v === 'extracted' ? 'green' : v === 'inferred' ? 'blue' : 'orange';
                    return <Tag color={color}>{v}</Tag>;
                  }},
                ]}
              />
            </Space>
          ),
        },
        {
          key: 'communities',
          label: '社区',
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              {communities.length === 0 && <Text type="secondary">暂无社区数据</Text>}
              {communities.map((c) => (
                <Card key={c.id} size="small" title={c.name} extra={<Tag>Level {c.level}</Tag>}>
                  <Text>{c.summary}</Text>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">包含 {c.entity_count} 个实体</Text>
                  </div>
                </Card>
              ))}
            </Space>
          ),
        },
        {
          key: 'graph-search',
          label: '图谱搜索',
          icon: <SearchOutlined />,
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Form form={graphSearchForm} layout="inline" initialValues={{ top_k: 10, max_depth: 2, search_mode: 'hybrid' }}>
                <Form.Item name="query" rules={[{ required: true, message: '请输入查询' }]} style={{ flex: 1 }}>
                  <Input placeholder="输入查询，例如：Agent 如何调用工具？" />
                </Form.Item>
                <Form.Item name="search_mode">
                  <Select style={{ width: 100 }} options={[
                    { label: '混合', value: 'hybrid' },
                    { label: '实体', value: 'entity' },
                    { label: '遍历', value: 'traverse' },
                    { label: '社区', value: 'community' },
                  ]} />
                </Form.Item>
                <Button type="primary" icon={<SearchOutlined />} loading={graphSearching} onClick={handleGraphSearch}>搜索</Button>
              </Form>
              <div>
                {graphSearchResults.map((item, idx) => (
                  <Card key={idx} size="small" style={{ marginBottom: 8 }}>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Space>
                        <Tag color={item.source === 'entity_match' ? 'blue' : item.source === 'relation_traverse' ? 'green' : 'purple'}>
                          {item.source}
                        </Tag>
                        <Text type="secondary">score={item.score.toFixed(3)}</Text>
                      </Space>
                      {item.entity && (
                        <Text><strong>{item.entity.name}</strong> ({item.entity.entity_type}): {item.entity.description}</Text>
                      )}
                      {item.relation && (
                        <Text>关系: {item.relation.relation_type} — {item.relation.description}</Text>
                      )}
                      {item.community && (
                        <Text>社区 <strong>{item.community.name}</strong>: {item.community.summary}</Text>
                      )}
                    </Space>
                  </Card>
                ))}
                {graphSearchResults.length === 0 && <Text type="secondary">暂无搜索结果</Text>}
              </div>
            </Space>
          ),
        },
      );
    } else {
      tabs.push({
        key: 'search',
        label: '搜索',
        icon: <SearchOutlined />,
        children: (
          <Card size="small" title="向量搜索测试">
            <Space.Compact style={{ width: '100%' }}>
              <Form form={searchForm} layout="inline" style={{ width: '100%' }} initialValues={{ top_k: 5, min_score: 0 }}>
                <Form.Item name="query" rules={[{ required: true, message: '请输入搜索问题' }]} style={{ flex: 1 }}>
                  <Input placeholder="输入问题，例如：如何配置 Agent？" />
                </Form.Item>
                <Form.Item name="top_k">
                  <InputNumber min={1} max={20} />
                </Form.Item>
                <Form.Item name="min_score">
                  <InputNumber min={-1} max={1} step={0.1} />
                </Form.Item>
                <Button type="primary" icon={<SearchOutlined />} loading={searching} onClick={handleSearch}>搜索</Button>
              </Form>
            </Space.Compact>
            <div style={{ marginTop: 12 }}>
              {searchResults.map((item, idx) => (
                <Card key={item.chunk_id} size="small" style={{ marginBottom: 8 }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text type="secondary">#{idx + 1} · score={item.score.toFixed(3)}</Text>
                    <Text>{item.content}</Text>
                  </Space>
                </Card>
              ))}
              {searchResults.length === 0 && <Text type="secondary">暂无搜索结果</Text>}
            </div>
          </Card>
        ),
      });
    }

    return tabs;
  }, [isGraphMode, documents, building, buildStatus, activeKB, entities, entityTotal, communities, graphSearchForm, graphSearching, graphSearchResults, searchForm, searching, searchResults, handleUpload, handleBuildGraph, handleDeleteGraph, handleGraphSearch, handleSearch]);

  return (
    <PageContainer
      title="知识库管理"
      icon={<DatabaseOutlined />}
      description="RAG 知识库的创建、文档上传与语义检索"
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建知识库</Button>}
    >
      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />

      {/* 创建/编辑 Modal */}
      <Modal
        title={editing ? '编辑知识库' : '新建知识库'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="mode" label="知识库模式">
            <Select
              options={[
                { label: '向量检索 (vector)', value: 'vector' },
                { label: '图谱检索 (graph)', value: 'graph' },
                { label: '混合模式 (hybrid)', value: 'hybrid' },
              ]}
            />
          </Form.Item>
          <Form.Item name="embedding_model" label="Embedding 模型" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space style={{ width: '100%' }}>
            <Form.Item name="chunk_size" label="Chunk Size" rules={[{ required: true }]}>
              <InputNumber min={64} max={4096} />
            </Form.Item>
            <Form.Item name="overlap" label="Overlap" rules={[{ required: true }]}>
              <InputNumber min={0} max={1024} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      {/* 详情 Modal（带 Tab） */}
      <Modal
        title={activeKB ? `知识库详情 · ${activeKB.name}` : '知识库详情'}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={1100}
      >
        <Tabs activeKey={activeTab} onChange={handleTabChange} items={detailTabs} />
      </Modal>
    </PageContainer>
  );
};

export default KnowledgeBasePage;
