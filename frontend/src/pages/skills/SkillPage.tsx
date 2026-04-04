import { useState, useCallback, useEffect } from 'react';
import { ProTable, type ProColumns } from '@ant-design/pro-components';
import { Button, Modal, Form, Input, Select, Tag, message, Space, Popconfirm } from 'antd';
import { PlusOutlined, SearchOutlined, DeleteOutlined, EditOutlined, EyeOutlined } from '@ant-design/icons';
import { skillService, type SkillItem, type SkillCreateParams, type SkillUpdateParams } from '../../services/skillService';

const categoryOptions = [
  { label: '公共', value: 'public' },
  { label: '自定义', value: 'custom' },
];

const categoryColorMap: Record<string, string> = {
  public: 'blue',
  custom: 'green',
};

const SkillPage: React.FC = () => {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [currentSkill, setCurrentSkill] = useState<SkillItem | null>(null);
  const [searchResults, setSearchResults] = useState<SkillItem[]>([]);
  const [tableKey, setTableKey] = useState(0);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [searchForm] = Form.useForm();

  const reload = useCallback(() => setTableKey((k) => k + 1), []);

  useEffect(() => {
    if (editModalOpen && currentSkill) {
      editForm.setFieldsValue({
        version: currentSkill.version,
        description: currentSkill.description,
        content: currentSkill.content,
        category: currentSkill.category,
        tags: currentSkill.tags,
        applicable_agents: currentSkill.applicable_agents,
        author: currentSkill.author,
      });
    }
  }, [editModalOpen, currentSkill, editForm]);

  const handleCreate = async (values: SkillCreateParams) => {
    await skillService.create(values);
    message.success('技能创建成功');
    setCreateModalOpen(false);
    createForm.resetFields();
    reload();
  };

  const handleEdit = async (values: SkillUpdateParams) => {
    if (!currentSkill) return;
    await skillService.update(currentSkill.id, values);
    message.success('技能更新成功');
    setEditModalOpen(false);
    editForm.resetFields();
    setCurrentSkill(null);
    reload();
  };

  const handleDelete = async (id: string) => {
    await skillService.delete(id);
    message.success('技能已删除');
    reload();
  };

  const handleSearch = async (values: { query: string; category?: string }) => {
    const results = await skillService.search({
      query: values.query,
      category: values.category,
      limit: 50,
    });
    setSearchResults(results);
  };

  const columns: ProColumns<SkillItem>[] = [
    {
      title: '名称',
      dataIndex: 'name',
      copyable: true,
      width: 160,
    },
    {
      title: '版本',
      dataIndex: 'version',
      width: 100,
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 100,
      render: (_, record) => (
        <Tag color={categoryColorMap[record.category] ?? 'default'}>{record.category}</Tag>
      ),
      filters: true,
      valueEnum: { public: { text: '公共' }, custom: { text: '自定义' } },
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      width: 200,
      render: (_, record) =>
        record.tags.map((t) => <Tag key={t}>{t}</Tag>),
      search: false,
    },
    {
      title: '作者',
      dataIndex: 'author',
      width: 100,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      valueType: 'dateTime',
      width: 180,
      sorter: true,
      search: false,
    },
    {
      title: '操作',
      valueType: 'option',
      width: 180,
      render: (_, record) => (
        <Space>
          <a onClick={() => { setCurrentSkill(record); setPreviewModalOpen(true); }}>
            <EyeOutlined /> 查看
          </a>
          <a onClick={() => { setCurrentSkill(record); setEditModalOpen(true); }}>
            <EditOutlined /> 编辑
          </a>
          <Popconfirm title="确认删除此技能？" onConfirm={() => handleDelete(record.id)}>
            <a style={{ color: '#ff4d4f' }}><DeleteOutlined /> 删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const searchResultColumns: ProColumns<SkillItem>[] = [
    { title: '名称', dataIndex: 'name', width: 160 },
    { title: '版本', dataIndex: 'version', width: 80 },
    {
      title: '分类',
      dataIndex: 'category',
      width: 80,
      render: (_, r) => <Tag color={categoryColorMap[r.category] ?? 'default'}>{r.category}</Tag>,
    },
    { title: '描述', dataIndex: 'description', ellipsis: true },
  ];

  return (
    <div>
      <ProTable<SkillItem>
        key={tableKey}
        columns={columns}
        request={async (params) => {
          const res = await skillService.list({
            category: params.category,
            limit: params.pageSize,
            offset: ((params.current ?? 1) - 1) * (params.pageSize ?? 20),
          });
          return { data: res.items, total: res.total, success: true };
        }}
        rowKey="id"
        headerTitle="技能管理"
        pagination={{ defaultPageSize: 20 }}
        search={{ labelWidth: 'auto' }}
        toolBarRender={() => [
          <Button key="search" icon={<SearchOutlined />} onClick={() => setSearchModalOpen(true)}>
            搜索技能
          </Button>,
          <Button key="create" type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            新建技能
          </Button>,
        ]}
      />

      {/* 创建弹窗 */}
      <Modal
        title="新建技能"
        open={createModalOpen}
        onCancel={() => { setCreateModalOpen(false); createForm.resetFields(); }}
        onOk={() => createForm.submit()}
        width={720}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="名称" rules={[{ required: true, pattern: /^[a-z0-9][a-z0-9-]*$/, message: '仅限小写字母、数字、连字符' }]}>
            <Input placeholder="my-skill" />
          </Form.Item>
          <Form.Item name="version" label="版本" initialValue="1.0.0">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="content" label="SKILL.md 内容" rules={[{ required: true, message: '请输入技能知识内容' }]}>
            <Input.TextArea rows={10} placeholder="# 技能知识内容..." />
          </Form.Item>
          <Form.Item name="category" label="分类" initialValue="custom">
            <Select options={categoryOptions} />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
          <Form.Item name="applicable_agents" label="适用 Agent">
            <Select mode="tags" placeholder="留空表示适用所有 Agent" />
          </Form.Item>
          <Form.Item name="author" label="作者">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        title="编辑技能"
        open={editModalOpen}
        onCancel={() => { setEditModalOpen(false); editForm.resetFields(); setCurrentSkill(null); }}
        onOk={() => editForm.submit()}
        width={720}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          <Form.Item name="version" label="版本">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="content" label="SKILL.md 内容" rules={[{ required: true, message: '请输入技能知识内容' }]}>
            <Input.TextArea rows={10} />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select options={categoryOptions} />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
          <Form.Item name="applicable_agents" label="适用 Agent">
            <Select mode="tags" placeholder="留空表示适用所有 Agent" />
          </Form.Item>
          <Form.Item name="author" label="作者">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 预览弹窗 */}
      <Modal
        title={currentSkill ? `${currentSkill.name} (v${currentSkill.version})` : '技能详情'}
        open={previewModalOpen}
        onCancel={() => { setPreviewModalOpen(false); setCurrentSkill(null); }}
        footer={null}
        width={800}
      >
        {currentSkill && (
          <div>
            <p><strong>分类：</strong><Tag color={categoryColorMap[currentSkill.category] ?? 'default'}>{currentSkill.category}</Tag></p>
            <p><strong>描述：</strong>{currentSkill.description || '—'}</p>
            <p><strong>作者：</strong>{currentSkill.author || '—'}</p>
            <p><strong>标签：</strong>{currentSkill.tags.length > 0 ? currentSkill.tags.map((t) => <Tag key={t}>{t}</Tag>) : '—'}</p>
            <p><strong>适用 Agent：</strong>{currentSkill.applicable_agents.length > 0 ? currentSkill.applicable_agents.join(', ') : '所有 Agent'}</p>
            <div style={{ marginTop: 16 }}>
              <strong>SKILL.md 内容：</strong>
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                {currentSkill.content}
              </pre>
            </div>
          </div>
        )}
      </Modal>

      {/* 搜索弹窗 */}
      <Modal
        title="搜索技能"
        open={searchModalOpen}
        onCancel={() => { setSearchModalOpen(false); searchForm.resetFields(); setSearchResults([]); }}
        footer={null}
        width={800}
      >
        <Form form={searchForm} layout="inline" onFinish={handleSearch} style={{ marginBottom: 16 }}>
          <Form.Item name="query" rules={[{ required: true, message: '请输入搜索关键词' }]}>
            <Input placeholder="关键词" style={{ width: 300 }} />
          </Form.Item>
          <Form.Item name="category">
            <Select placeholder="分类" options={categoryOptions} allowClear style={{ width: 120 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>搜索</Button>
          </Form.Item>
        </Form>
        <ProTable<SkillItem>
          columns={searchResultColumns}
          dataSource={searchResults}
          rowKey="id"
          search={false}
          pagination={false}
          toolBarRender={false}
        />
      </Modal>
    </div>
  );
};

export default SkillPage;
