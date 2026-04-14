import { useState } from 'react';
import {
  Form, Input, Tag, Modal, Descriptions,
} from 'antd';
import {
  BankOutlined, EyeOutlined,
} from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import type { FormInstance } from 'antd';
import type { OrganizationItem, OrganizationCreateParams, OrganizationUpdateParams } from '../../services/organizationService';
import {
  useOrganizationList,
  useCreateOrganization,
  useUpdateOrganization,
  useDeleteOrganization,
} from '../../hooks/useOrganizationQueries';
import { CrudTable, PageContainer, buildActionColumn, createJsonValidatorRule, JsonEditor } from '../../components';
import type { CrudTableActions } from '../../components';

const { TextArea } = Input;

/* ---- 列定义 ---- */

const buildColumns = (
  actions: CrudTableActions<OrganizationItem>,
  setDetailRecord: (r: OrganizationItem) => void,
): ProColumns<OrganizationItem>[] => [
  {
    title: '名称',
    dataIndex: 'name',
    width: 160,
    render: (_, record) => <strong>{record.name}</strong>,
  },
  {
    title: 'Slug',
    dataIndex: 'slug',
    width: 120,
    render: (_, record) => <Tag color="blue">{record.slug}</Tag>,
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    width: 80,
    render: (_, record) => (
      <Tag color={record.is_active ? 'green' : 'default'}>{record.is_active ? '启用' : '停用'}</Tag>
    ),
  },
  {
    title: '描述',
    dataIndex: 'description',
    ellipsis: true,
    width: 200,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 180,
    render: (_, record) => new Date(record.created_at).toLocaleString(),
  },
  buildActionColumn<OrganizationItem>(actions, {
    extraItems: (record) => [
      {
        key: 'detail',
        label: '详情',
        icon: <EyeOutlined />,
        onClick: () => setDetailRecord(record),
      },
    ],
  }),
];

/* ---- 表单渲染 ---- */

const renderForm = (_form: FormInstance, editing: OrganizationItem | null) => (
  <>
    <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入组织名称' }]}>
      <Input placeholder="CkyClaw Tech" />
    </Form.Item>
    <Form.Item name="slug" label="Slug" rules={[{ required: !editing, message: '请输入唯一标识' }]}>
      <Input placeholder="ckyclaw-tech" disabled={!!editing} />
    </Form.Item>
    <Form.Item name="description" label="描述">
      <TextArea rows={2} placeholder="组织描述" />
    </Form.Item>
    <Form.Item name="settings" label="设置 (JSON)" rules={[createJsonValidatorRule()]}>
      <JsonEditor height={100} placeholder="{}" />
    </Form.Item>
    <Form.Item name="quota" label="配额 (JSON)" rules={[createJsonValidatorRule()]}>
      <JsonEditor height={100} placeholder='{"max_agents": 50, "max_tokens_per_day": 1000000}' />
    </Form.Item>
  </>
);

/* ---- 页面组件 ---- */

const OrganizationPage: React.FC = () => {
  const [detailRecord, setDetailRecord] = useState<OrganizationItem | null>(null);

  const queryResult = useOrganizationList({ limit: 200 });
  const createMutation = useCreateOrganization();
  const updateMutation = useUpdateOrganization();
  const deleteMutation = useDeleteOrganization();

  return (
    <PageContainer
      title="组织管理"
      icon={<BankOutlined />}
      description="管理组织信息、配额与设置"
    >
      <CrudTable<
        OrganizationItem,
        OrganizationCreateParams,
        { id: string; data: OrganizationUpdateParams }
      >
        hideTitle
        mobileHiddenColumns={['description', 'created_at']}
        title="组织管理"
        queryResult={queryResult}
        createMutation={createMutation}
        updateMutation={updateMutation}
        deleteMutation={deleteMutation}
        createButtonText="新建组织"
        modalTitle={(editing) => (editing ? '编辑组织' : '新建组织')}
        modalWidth={560}
        columns={(actions) => buildColumns(actions, setDetailRecord)}
        renderForm={renderForm}
        toFormValues={(record) => ({
          name: record.name,
          slug: record.slug,
          description: record.description,
          settings: JSON.stringify(record.settings, null, 2),
          quota: JSON.stringify(record.quota, null, 2),
        })}
        toCreatePayload={(values) => ({
          name: values.name as string,
          slug: values.slug as string,
          description: (values.description as string) || '',
          settings: values.settings ? JSON.parse(values.settings as string) : {},
          quota: values.quota ? JSON.parse(values.quota as string) : {},
        })}
        toUpdatePayload={(values, record) => ({
          id: record.id,
          data: {
            name: values.name as string,
            description: (values.description as string) || '',
            settings: values.settings ? JSON.parse(values.settings as string) : {},
            quota: values.quota ? JSON.parse(values.quota as string) : {},
          },
        })}
        showRefresh
      />

      {/* 详情弹窗 */}
      <Modal
        title="组织详情"
        open={!!detailRecord}
        onCancel={() => setDetailRecord(null)}
        footer={null}
        width={600}
      >
        {detailRecord && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="ID">{detailRecord.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{detailRecord.name}</Descriptions.Item>
            <Descriptions.Item label="Slug">{detailRecord.slug}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={detailRecord.is_active ? 'green' : 'default'}>
                {detailRecord.is_active ? '启用' : '停用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述">{detailRecord.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="设置">
              <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(detailRecord.settings, null, 2)}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="配额">
              <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(detailRecord.quota, null, 2)}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{new Date(detailRecord.created_at).toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{new Date(detailRecord.updated_at).toLocaleString()}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </PageContainer>
  );
};

export default OrganizationPage;
