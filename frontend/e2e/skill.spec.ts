import { test, expect } from '@playwright/test';
import { SkillPage } from './pom/SkillPage';
import { registerMocks } from './mocks/index';
import { skillMocks, skillStore } from './mocks/skillMocks';

/**
 * CkyClaw 技能管理 E2E 测试。
 *
 * 使用 API Mock 拦截所有 /api/v1/skills/** 请求，不依赖真实后端。
 */
test.describe('技能管理', () => {
  let skillPage: SkillPage;

  test.beforeEach(async ({ page }) => {
    // 注册 mock 拦截
    await registerMocks(page, [skillMocks]);
    skillPage = new SkillPage(page);

    // 模拟已登录状态
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('ckyclaw_token', 'mock-e2e-token');
    });
  });

  // 1. 列表页渲染
  test('列表页渲染 — 表格显示 mock 数据', async ({ page }) => {
    await skillPage.goto();

    // 表格应可见
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 });

    // 应显示预设的两条 mock 技能
    await skillPage.expectInTable('e2e-mock-skill-hello');
    await skillPage.expectInTable('e2e-mock-skill-world');
  });

  // 2. 新建技能完整流程
  test('新建技能完整流程', async ({ page }) => {
    await skillPage.goto();

    const skillName = `e2e-test-skill-${Date.now()}`;
    await skillPage.clickCreate();
    await skillPage.fillCreateForm({
      name: skillName,
      content: '# 测试',
    });
    await skillPage.confirmCreate();

    // 等待成功提示
    await skillPage.waitForSuccessMessage();

    // 新技能应出现在列表中
    await skillPage.expectInTable(skillName);
  });

  // 3. 新建技能必填校验
  test('新建技能必填校验 — 空名称', async ({ page }) => {
    await skillPage.goto();

    await skillPage.clickCreate();
    // 不填写名称，直接填 content（必填字段）后点确认触发校验
    await skillPage.fillCreateForm({
      content: '# 测试内容',
    });
    // 清空名称以触发 required 校验
    const nameInput = page.locator('#name');
    await nameInput.clear();
    await skillPage.confirmCreate();

    // 应出现校验错误
    const errorMsg = page.locator('.ant-form-item-explain-error');
    await expect(errorMsg.first()).toBeVisible({ timeout: 5_000 });
  });

  // 4. 新建技能名称格式校验
  test('新建技能名称格式校验 — 仅限小写字母', async ({ page }) => {
    await skillPage.goto();

    await skillPage.clickCreate();
    await skillPage.fillCreateForm({
      name: 'UPPERCASE-NAME',
      content: '# 测试内容',
    });
    await skillPage.confirmCreate();

    // 应出现"仅限小写字母"的校验错误
    const errorMsg = page.locator('.ant-form-item-explain-error');
    await expect(errorMsg.first()).toBeVisible({ timeout: 5_000 });
    await expect(errorMsg.first()).toContainText('仅限小写字母');
  });

  // 5. 编辑技能
  test('编辑技能 — 修改描述', async ({ page }) => {
    await skillPage.goto();

    // 点击第一条 mock 技能的编辑按钮
    await skillPage.clickEdit('e2e-mock-skill-hello');

    // 修改描述
    const newDesc = `更新后的描述 ${Date.now()}`;
    await skillPage.fillEditForm({ description: newDesc });
    await skillPage.confirmCreate();

    // 等待成功提示
    await skillPage.waitForSuccessMessage();
  });

  // 6. 删除技能
  test('删除技能 — 确认后不再出现', async ({ page }) => {
    await skillPage.goto();

    // 删除第一条 mock 技能
    await skillPage.clickDelete('e2e-mock-skill-hello');

    // 等待成功提示
    await skillPage.waitForSuccessMessage();

    // 该技能不应再出现在列表中
    await skillPage.expectNotInTable('e2e-mock-skill-hello');
  });

  // 7. 查看技能详情
  test('查看技能详情 — 预览 Modal 打开', async ({ page }) => {
    await skillPage.goto();

    // 点击查看按钮
    await skillPage.clickPreview('e2e-mock-skill-hello');

    // 预览 Modal 应打开，包含技能内容
    await skillPage.expectPreviewContent('e2e-mock-skill-hello');
    await skillPage.expectPreviewContent('这是一个测试技能');
  });

  // 8. 搜索技能
  test('搜索技能 — 关键词搜索', async ({ page }) => {
    await skillPage.goto();

    // 打开搜索弹窗
    await skillPage.clickSearch();

    // 搜索"hello"关键词
    await skillPage.fillSearchForm('hello');
    await skillPage.confirmSearch();

    // 应有搜索结果（匹配 e2e-mock-skill-hello）
    await skillPage.expectSearchResults(1);
  });

  // 9. 标签选择
  test('标签选择 — 创建时输入标签，列表中显示', async ({ page }) => {
    await skillPage.goto();

    const skillName = `e2e-tag-skill-${Date.now()}`;
    await skillPage.clickCreate();
    await skillPage.fillCreateForm({
      name: skillName,
      content: '# 标签测试',
      tags: ['custom-tag-1', 'custom-tag-2'],
    });
    await skillPage.confirmCreate();

    // 等待成功提示
    await skillPage.waitForSuccessMessage();

    // 新技能应出现在列表中，并显示标签
    await skillPage.expectInTable(skillName);

    // 表格中应显示标签 Tag
    const row = page.locator('.ant-table-row').filter({ hasText: skillName }).first();
    await expect(row.locator('.ant-tag').getByText('custom-tag-1')).toBeVisible({ timeout: 5_000 });
    await expect(row.locator('.ant-tag').getByText('custom-tag-2')).toBeVisible({ timeout: 5_000 });
  });
});
