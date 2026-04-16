import { test, expect } from '@playwright/test';
import { ProviderListPage } from './pom/ProviderListPage';
import { ProviderEditPage } from './pom/ProviderEditPage';
import { createProviderMocks } from './mocks/providerMocks';

test.describe('Provider 管理', () => {
  let listPage: ProviderListPage;
  let editPage: ProviderEditPage;

  test.beforeEach(async ({ page }) => {
    listPage = new ProviderListPage(page);
    editPage = new ProviderEditPage(page);
    await createProviderMocks(page);
  });

  /* ---- 1. 列表页渲染 ---- */
  test('列表页渲染 — 表格显示 mock 数据', async () => {
    await listPage.goto();
    // 断言预设的两条 mock 数据在表格中可见
    await listPage.expectProviderInTable('e2e-mock-openai');
    await listPage.expectProviderInTable('e2e-mock-anthropic');
    // 断言 "注册厂商" 按钮存在
    await expect(listPage.page.locator('button').getByText('注册厂商').first()).toBeVisible();
  });

  /* ---- 2. 注册厂商 — 完整创建流程 ---- */
  test('注册厂商 — 完整创建流程', async () => {
    const uniqueName = `e2e-test-${Date.now()}`;
    await listPage.goto();
    await listPage.clickCreate();

    // 等待页面加载
    await editPage.page.waitForURL('**/providers/new');

    // 填写表单
    await editPage.fillName(uniqueName);
    await editPage.selectProviderType('OpenAI');
    await editPage.fillBaseUrl('https://api.openai.com/v1');
    await editPage.fillApiKey('sk-e2e-test-key-12345678');

    // 提交
    await editPage.clickSave();

    // 断言成功提示
    await listPage.waitForSuccessMessage();
    // 断言导航回列表页
    await expect(editPage.page).toHaveURL(/\/providers$/, { timeout: 5_000 });
    // 断言新创建的厂商在表格中
    await listPage.expectProviderInTable(uniqueName);
  });

  /* ---- 3. 注册厂商 — 必填校验 ---- */
  test('注册厂商 — 必填校验', async () => {
    await listPage.goto();
    await listPage.clickCreate();
    await editPage.page.waitForURL('**/providers/new');

    // 不填任何字段，直接提交
    await editPage.clickSave();

    // 断言出现表单验证错误
    await editPage.expectValidationError();
  });

  /* ---- 4. 编辑厂商 — 修改名称和 Base URL ---- */
  test('编辑厂商 — 修改名称和 Base URL', async () => {
    const updatedName = `e2e-updated-${Date.now()}`;
    await listPage.goto();

    // 点击第一条 mock 数据的名称链接进入编辑
    await listPage.clickName('e2e-mock-openai');
    await editPage.page.waitForURL('**/providers/**/edit');

    // 等待表单加载
    await editPage.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });

    // 修改名称
    await editPage.fillName(updatedName);
    // 修改 Base URL
    await editPage.fillBaseUrl('https://api.openai.com/v2');

    // 保存
    await editPage.clickSave();

    // 断言成功提示
    await listPage.waitForSuccessMessage();
    // 断言导航回列表页
    await expect(editPage.page).toHaveURL(/\/providers$/, { timeout: 5_000 });
    // 断言更新后的名称在表格中
    await listPage.expectProviderInTable(updatedName);
  });

  /* ---- 5. 测试连接 — 成功响应 ---- */
  test('测试连接 — 成功响应', async () => {
    await listPage.goto();
    await listPage.clickName('e2e-mock-openai');
    await editPage.page.waitForURL('**/providers/**/edit');

    // 等待表单加载
    await editPage.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });

    // 点击测试连接
    await editPage.clickTestConnection();

    // 断言成功 Modal 出现
    const successModal = editPage.page.locator('.ant-modal-wrap:visible').filter({ hasText: '连接成功' });
    await expect(successModal).toBeVisible({ timeout: 10_000 });
  });

  /* ---- 6. 切换厂商类型自动填充 Base URL ---- */
  test('切换厂商类型自动填充 Base URL', async () => {
    await listPage.goto();
    await listPage.clickCreate();
    await editPage.page.waitForURL('**/providers/new');

    // 等待表单加载
    await editPage.page.locator('#provider_type').waitFor({ state: 'visible', timeout: 5_000 });

    // 切换到 Anthropic 类型
    await editPage.selectProviderType('Anthropic');

    // 断言 Base URL 自动变为 Anthropic 的 URL
    await editPage.expectBaseUrlValue('https://api.anthropic.com/v1');
  });

  /* ---- 7. 启用/禁用厂商 ---- */
  test('启用/禁用厂商', async () => {
    await listPage.goto();

    // 点击第一条 mock 数据的 Switch
    await listPage.clickToggle('e2e-mock-openai');

    // 断言成功提示
    await listPage.waitForSuccessMessage();
  });

  /* ---- 8. 删除厂商 ---- */
  test('删除厂商', async () => {
    await listPage.goto();

    // 删除第一条 mock 数据
    await listPage.clickDelete('e2e-mock-openai');

    // 断言成功提示
    await listPage.waitForSuccessMessage();

    // 断言该厂商不再出现在表格中
    await listPage.expectProviderNotInTable('e2e-mock-openai');
  });

  /* ---- 9. 模型列表加载 ---- */
  test('模型列表加载', async () => {
    await listPage.goto();
    await listPage.clickName('e2e-mock-openai');
    await editPage.page.waitForURL('**/providers/**/edit');

    // 等待表单加载
    await editPage.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });

    // 切换到关联模型 Tab
    await editPage.switchToModelsTab();

    // 断言模型表格可见（表头出现 "模型标识"）
    const modelTable = editPage.page.locator('.ant-table').filter({ hasText: '模型标识' });
    await expect(modelTable).toBeVisible({ timeout: 5_000 });

    // 断言预设模型 gpt-4o 在表格中
    await editPage.expectModelInTable('gpt-4o');
  });

  /* ---- 10. 添加模型 ---- */
  test('添加模型', async () => {
    const modelId = `e2e-model-${Date.now()}`;
    await listPage.goto();
    await listPage.clickName('e2e-mock-openai');
    await editPage.page.waitForURL('**/providers/**/edit');

    // 等待表单加载
    await editPage.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });

    // 切换到关联模型 Tab
    await editPage.switchToModelsTab();

    // 点击添加模型
    await editPage.clickAddModel();

    // 等待弹窗出现
    await editPage.waitForModalOpen();

    // 填写模型信息
    await editPage.fillModelName(modelId);
    await editPage.fillModelDisplayName(`E2E 测试模型`);

    // 确认
    await editPage.confirmModelModal();

    // 断言成功提示
    await listPage.waitForSuccessMessage();
    // 断言新模型在表格中
    await editPage.expectModelInTable(modelId);
  });

  /* ---- 11. 从厂商同步模型 ---- */
  test('从厂商同步模型', async () => {
    await listPage.goto();
    await listPage.clickName('e2e-mock-openai');
    await editPage.page.waitForURL('**/providers/**/edit');

    // 等待表单加载
    await editPage.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });

    // 切换到关联模型 Tab
    await editPage.switchToModelsTab();

    // 点击从厂商同步
    await editPage.clickSyncModels();

    // 断言成功提示（包含同步数量信息）
    await listPage.waitForSuccessMessage();
  });

  /* ---- 12. 返回列表导航 ---- */
  test('返回列表导航', async () => {
    await listPage.goto();
    await listPage.clickName('e2e-mock-openai');
    await editPage.page.waitForURL('**/providers/**/edit');

    // 等待页面加载
    await editPage.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });

    // 点击返回列表
    await editPage.clickBackToList();

    // 断言 URL 变为 /providers
    await expect(editPage.page).toHaveURL(/\/providers$/, { timeout: 5_000 });
  });
});
