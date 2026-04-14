import { useEffect, useMemo, useState } from 'react';
import { App, Button, Card, Form, Input, InputNumber, Modal, Space, Table, Tag, Typography, Upload } from 'antd';
import { DatabaseOutlined, PlusOutlined, SearchOutlined, UploadOutlined } from '@ant-design/icons';
import { PageContainer } from '../../components/PageContainer';
import type { ColumnsType } from 'antd/es/table';
import { knowledgeBaseService, type KnowledgeBaseItem, type KnowledgeDocumentItem, type KnowledgeSearchResultItem } from '../../services/knowledgeBaseService';

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
  const [documents, setDocuments] = useState<KnowledgeDocumentItem[]>([]);
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResultItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchForm] = Form.useForm();

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
    { title: '名称', dataIndex: 'name', key: 'name', width: 220 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: 'Embedding', dataIndex: 'embedding_model', key: 'embedding_model', width: 160 },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
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
    form.setFieldsValue({ embedding_model: 'hash-embedding-v1', chunk_size: 512, overlap: 64 });
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
    setSearchResults([]);
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

      <Modal
        title={activeKB ? `知识库详情 · ${activeKB.name}` : '知识库详情'}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={980}
      >
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
              { title: '类型', dataIndex: 'media_type', width: 160 },
              { title: '大小', dataIndex: 'size_bytes', width: 120, render: (v: number) => `${Math.round(v / 1024)} KB` },
              { title: '状态', dataIndex: 'status', width: 100, render: (v: string) => <Tag color={v === 'indexed' ? 'green' : 'processing'}>{v}</Tag> },
              { title: '分块数', dataIndex: 'chunk_count', width: 100 },
            ]}
          />

          <Card size="small" title="搜索测试">
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
        </Space>
      </Modal>
    </PageContainer>
  );
};

export default KnowledgeBasePage;
