import { useState } from 'react';
import type { ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { Button, Modal, Form, Input, Select, Tag, App, Space, Popconfirm } from 'antd';
import { SearchOutlined, DeleteOutlined, EditOutlined, EyeOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { SkillItem, SkillCreateParams, SkillUpdateParams } from '../../services/skillService';
import {
  useSkillList,
  useCreateSkill,
  useUpdateSkill,
  useDeleteSkill,
  useSearchSkill,
} from '../../hooks/useSkillQueries';
import { CrudTable } from '../../components';
import type { CrudTableActions } from '../../components';

const categoryOptions = [
  { label: '公共', value: 'public' },
  { label: '自定义', value: 'custom' },
];

const categoryColorMap: Record<string, string> = {
  public: 'blue',
  custom: 'green',
};

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<SkillItem>,
  onPreview: (record: SkillItem) => void,
): ProColumns<SkillItem>[] => [
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
  },
  {
    title: '作者',
    dataIndex: 'author',
    width: 100,
  },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    width: 180,
    render: (_, record) => new Date(record.updated_at).toLocaleString('zh-CN'),
  },
  {
    title: '操作',
    width: 180,
    render: (_, record) => (
      <Space>
        <a onClick={() => onPreview(record)}>
          <EyeOutlined /> 查看
        </a>
        <a onClick={() => actions.openEdit(record)}>
          <EditOutlined /> 编辑
        </a>
        <Popconfirm title="确认删除此技能？" onConfirm={() => actions.handleDelete(record.id)}>
          <a style={{ color: '#ff4d4f' }}><DeleteOutlined /> 删除</a>
        </Popconfirm>
      </Space>
    ),
  },
];

/* ---- 搜索结果列 ---- */

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

/* ---- 表单 ---- */

const renderForm = (_form: FormInstance, editing: SkillItem | null) => (
  <>
    {!editing && (
      <Form.Item name="name" label="名称" rules={[{ required: true, pattern: /^[a-z0-9][a-z0-9-]*$/, message: '仅限小写字母、数字、连字符' }]}>
        <Input placeholder="my-skill" />
      </Form.Item>
    )}
    <Form.Item name="version" label="版本">
      <Input />
    </Form.Item>
    <Form.Item name="description" label="描述">
      <Input.TextArea rows={2} />
    </Form.Item>
    <Form.Item name="content" label="SKILL.md 内容" rules={[{ required: true, message: '请输入技能知识内容' }]}>
      <Input.TextArea rows={10} placeholder="# 技能知识内容..." />
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
  </>
);

/* ---- 页面组件 ---- */

const SkillPage: React.FC = () => {
  const { message: _msg } = App.useApp();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [currentSkill, setCurrentSkill] = useState<SkillItem | null>(null);
  const [searchResults, setSearchResults] = useState<SkillItem[]>([]);
  const [searchForm] = Form.useForm();

  const queryResult = useSkillList({
    limit: pagination.pageSize,
    offset: (pagination.current - 1) * pagination.pageSize,
  });
  const createMutation = useCreateSkill();
  const updateMutation = useUpdateSkill();
  const deleteMutation = useDeleteSkill();
  const searchMutation = useSearchSkill();

  const handlePreview = (record: SkillItem) => {
    setCurrentSkill(record);
    setPreviewModalOpen(true);
  };

  const handleSearch = async (values: { query: string; category?: string }) => {
    const results = await searchMutation.mutateAsync({
      query: values.query,
      category: values.category,
      limit: 50,
    });
    setSearchResults(results);
  };

  return (
    <>
      <CrudTable<
        SkillItem,
        SkillCreateParams,
        { id: string; data: SkillUpdateParams }
      >
        title="技能管理"
        queryResult={queryResult}
        createMutation={createMutation}
        updateMutation={updateMutation}
        deleteMutation={deleteMutation}
        createButtonText="新建技能"
        modalTitle={(editing) => (editing ? '编辑技能' : '新建技能')}
        modalWidth={720}
        columns={(actions) => buildColumns(actions, handlePreview)}
        renderForm={renderForm}
        createDefaults={{ version: '1.0.0', category: 'custom' }}
        toFormValues={(record) => ({
          name: record.name,
          version: record.version,
          description: record.description,
          content: record.content,
          category: record.category,
          tags: record.tags,
          applicable_agents: record.applicable_agents,
          author: record.author,
        })}
        toCreatePayload={(values) => ({
          name: values.name as string,
          version: values.version as string | undefined,
          description: values.description as string | undefined,
          content: values.content as string,
          category: values.category as string | undefined,
          tags: values.tags as string[] | undefined,
          applicable_agents: values.applicable_agents as string[] | undefined,
          author: values.author as string | undefined,
        })}
        toUpdatePayload={(values, record) => ({
          id: record.id,
          data: {
            version: values.version as string | undefined,
            description: values.description as string | undefined,
            content: values.content as string | undefined,
            category: values.category as string | undefined,
            tags: values.tags as string[] | undefined,
            applicable_agents: values.applicable_agents as string[] | undefined,
            author: values.author as string | undefined,
          },
        })}
        extraToolbar={
          <Button icon={<SearchOutlined />} onClick={() => setSearchModalOpen(true)}>
            搜索技能
          </Button>
        }
        pagination={pagination}
        onPaginationChange={(current, pageSize) => setPagination({ current, pageSize })}
        showRefresh
      />

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
    </>
  );
};

export default SkillPage;
