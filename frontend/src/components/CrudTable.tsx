/**
 * CrudTable — 泛型 CRUD 表格组件。
 *
 * 封装 ProTable + Modal + Form 的通用 CRUD 骨架：
 * - 分页、加载状态
 * - 新建 / 编辑 Modal（共享同一个 Modal）
 * - 删除确认
 * - message.success / error 统一处理
 *
 * 每个页面只需提供 columns、renderForm 和 query hooks 即可。
 */
import { useState, useCallback } from 'react';
import { App, Button, Card, Form, Modal, Space } from 'antd';
import type { FormInstance } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import type { ReactNode } from 'react';
import type {
  UseQueryResult,
  UseMutationResult,
} from '@tanstack/react-query';

/* ---------- 通用分页响应结构 ---------- */

export interface PagedResult<T> {
  data: T[];
  total: number;
}

/* ---------- 分页参数 ---------- */

export interface ListParams {
  limit: number;
  offset: number;
  [key: string]: unknown;
}

/* ---------- Props ---------- */

/** CrudTable 暴露给 columns / extraToolbar 的操作方法 */
export interface CrudTableActions<T extends object> {
  openEdit: (record: T) => void;
  openCreate: () => void;
  handleDelete: (id: string) => Promise<void>;
}

export interface CrudTableProps<
  T extends object,
  TCreate = unknown,
  TUpdate = unknown,
> {
  /** 卡片标题 */
  title: ReactNode;
  /** 标题左侧图标 */
  icon?: ReactNode;

  /**
   * 列定义。可以是静态数组，也可以传工厂函数以获取 actions（openEdit / handleDelete）。
   */
  columns: ProColumns<T>[] | ((actions: CrudTableActions<T>) => ProColumns<T>[]);

  /**
   * 列表查询 hook 的返回值。
   * 调用方在外部调用 hook 并把结果传入，以便保留筛选参数的控制权。
   */
  queryResult: UseQueryResult<PagedResult<T>>;

  /** Modal 中的表单内容 */
  renderForm: (form: FormInstance, editing: T | null) => ReactNode;

  /* ---- Mutation hooks（可选，缺省则隐藏对应功能）---- */

  /** 创建 mutation。缺失时隐藏新建按钮。 */
  createMutation?: UseMutationResult<unknown, Error, TCreate>;
  /** 更新 mutation。缺失时隐藏编辑按钮（由页面自行渲染列操作）。 */
  updateMutation?: UseMutationResult<unknown, Error, TUpdate>;
  /** 删除 mutation。缺失时隐藏删除确认。 */
  deleteMutation?: UseMutationResult<unknown, Error, string>;

  /* ---- 表单值 ↔ 接口 payload 转换 ---- */

  /** record → form 初始值。默认将 record 浅拷贝。 */
  toFormValues?: (record: T) => Record<string, unknown>;
  /** form values → create payload */
  toCreatePayload?: (values: Record<string, unknown>) => TCreate;
  /** form values → update payload */
  toUpdatePayload?: (values: Record<string, unknown>, record: T) => TUpdate;

  /* ---- 外观 & 行为 ---- */

  /** 表格 rowKey，默认 "id" */
  rowKey?: string;
  /** 默认分页大小，默认 20 */
  defaultPageSize?: number;
  /** 新建按钮文字，默认 "新建" */
  createButtonText?: string;
  /** Modal 宽度，默认 640 */
  modalWidth?: number;
  /** Modal 标题。默认根据 editing 是否为 null 展示 "新建"/"编辑"。 */
  modalTitle?: (editing: T | null) => string;
  /** 新建表单默认值 */
  createDefaults?: Record<string, unknown>;

  /* ---- 扩展插槽 ---- */

  /** Card extra 区域额外元素（筛选控件等），渲染在新建按钮左侧 */
  extraToolbar?: ReactNode;
  /** Card 与表格之间的自定义内容（筛选栏等） */
  beforeTable?: ReactNode;
  /** 是否显示刷新按钮，默认 false */
  showRefresh?: boolean;
  /**
   * 自定义"新建"行为。
   * - 传 `false` 隐藏新建按钮
   * - 传函数则点击时调用该函数而非打开 Modal
   */
  onCreateClick?: false | (() => void);

  /* ---- 分页控制（外部管理筛选参数时需要）---- */

  /** 受控分页 */
  pagination?: { current: number; pageSize: number };
  /** 分页变化回调 */
  onPaginationChange?: (current: number, pageSize: number) => void;
  /** 数据总数覆盖（默认从 queryResult 读取） */
  total?: number;
}

/* ---------- 组件实现 ---------- */

export function CrudTable<
  T extends object,
  TCreate = unknown,
  TUpdate = unknown,
>(props: CrudTableProps<T, TCreate, TUpdate>) {
  const {
    title,
    icon,
    columns,
    queryResult,
    renderForm,
    createMutation,
    updateMutation,
    deleteMutation,
    toFormValues,
    toCreatePayload,
    toUpdatePayload,
    rowKey = 'id',
    defaultPageSize = 20,
    createButtonText = '新建',
    modalWidth = 640,
    modalTitle,
    createDefaults,
    beforeTable,
    extraToolbar,
    showRefresh,
    onCreateClick,
    pagination: controlledPagination,
    onPaginationChange,
    total: totalOverride,
  } = props;

  const { message } = App.useApp();

  /* ---- 内部分页（仅当未外部受控时使用）---- */
  const [internalPagination, setInternalPagination] = useState({
    current: 1,
    pageSize: defaultPageSize,
  });
  const pagination = controlledPagination ?? internalPagination;
  const handlePageChange = useCallback(
    (page: number, pageSize: number) => {
      if (onPaginationChange) {
        onPaginationChange(page, pageSize);
      } else {
        setInternalPagination({ current: page, pageSize });
      }
    },
    [onPaginationChange],
  );

  /* ---- Modal & Form ---- */
  const [modalVisible, setModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState<T | null>(null);
  const [form] = Form.useForm();

  const openCreate = useCallback(() => {
    setEditingItem(null);
    form.resetFields();
    if (createDefaults) {
      form.setFieldsValue(createDefaults);
    }
    setModalVisible(true);
  }, [form, createDefaults]);

  /** 供外部 columns 的操作列调用 */
  const openEdit = useCallback(
    (record: T) => {
      setEditingItem(record);
      const values = toFormValues ? toFormValues(record) : { ...record };
      form.setFieldsValue(values);
      setModalVisible(true);
    },
    [form, toFormValues],
  );

  const handleSubmit = useCallback(async () => {
    try {
      const values = await form.validateFields();

      if (editingItem) {
        if (!updateMutation) return;
        const payload = toUpdatePayload
          ? toUpdatePayload(values as Record<string, unknown>, editingItem)
          : (values as TUpdate);
        await updateMutation.mutateAsync(payload);
        message.success('更新成功');
      } else {
        if (!createMutation) return;
        const payload = toCreatePayload
          ? toCreatePayload(values as Record<string, unknown>)
          : (values as TCreate);
        await createMutation.mutateAsync(payload);
        message.success('创建成功');
      }
      setModalVisible(false);
    } catch (err) {
      // payload 构建函数抛出的 Error 显示自定义消息，表单校验失败则静默
      if (err instanceof Error) {
        message.error(err.message || '操作失败');
      }
    }
  }, [form, editingItem, createMutation, updateMutation, toCreatePayload, toUpdatePayload, message]);

  const handleDelete = useCallback(
    async (id: string) => {
      if (!deleteMutation) return;
      try {
        await deleteMutation.mutateAsync(id);
        message.success('删除成功');
      } catch {
        message.error('删除失败');
      }
    },
    [deleteMutation, message],
  );

  /* ---- 数据 ---- */
  const listData = queryResult.data;
  const data = listData?.data ?? [];
  const total = totalOverride ?? listData?.total ?? 0;
  const loading = queryResult.isLoading;

  /* ---- Actions 对象（传入 columnsFactory）---- */
  const actions: CrudTableActions<T> = { openEdit, openCreate, handleDelete };
  const resolvedColumns = typeof columns === 'function' ? columns(actions) : columns;

  /* ---- 渲染 ---- */
  const showCreateButton = onCreateClick !== false && (onCreateClick || createMutation);

  const resolvedTitle = modalTitle
    ? modalTitle(editingItem)
    : editingItem
      ? '编辑'
      : createButtonText;

  return (
    <>
      <Card
        title={
          icon ? (
            <Space>
              {icon}
              {title}
            </Space>
          ) : (
            title
          )
        }
        extra={
          <Space>
            {extraToolbar}
            {showRefresh && (
              <Button
                icon={<ReloadOutlined />}
                onClick={() => void queryResult.refetch()}
              >
                刷新
              </Button>
            )}
            {showCreateButton && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={typeof onCreateClick === 'function' ? onCreateClick : openCreate}
              >
                {createButtonText}
              </Button>
            )}
          </Space>
        }
      >
        {beforeTable}
        <ProTable<T>
          rowKey={rowKey}
          columns={resolvedColumns}
          dataSource={data}
          loading={loading}
          search={false}
          toolBarRender={false}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: handlePageChange,
          }}
        />
      </Card>

      <Modal
        title={resolvedTitle}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        confirmLoading={
          (createMutation?.isPending ?? false) || (updateMutation?.isPending ?? false)
        }
        width={modalWidth}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          {renderForm(form, editingItem)}
        </Form>
      </Modal>
    </>
  );
}

/* ---- 暴露 helper 类型 ---- */
export type { FormInstance };
