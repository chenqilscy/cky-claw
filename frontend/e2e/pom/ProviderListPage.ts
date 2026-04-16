import { expect, type Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * ProviderListPage — 模型厂商列表页（/providers）的 Page Object。
 */
export class ProviderListPage extends BasePage {
  /* ---- 导航 ---- */

  /** 导航到厂商列表页 */
  async goto() {
    await this.navigateTo('/providers');
  }

  /* ---- 操作按钮 ---- */

  /** 点击 "注册厂商" 按钮 */
  async clickCreate() {
    await this.page.locator('button').getByText('注册厂商').first().click();
  }

  /** 点击表格中指定名称的编辑链接 */
  async clickEdit(name: string) {
    const row = this.getTableRow(name);
    await row.locator('a').getByText('编辑').first().click();
  }

  /** 点击表格中指定名称的链接（名称列） */
  async clickName(name: string) {
    const row = this.getTableRow(name);
    await row.locator('a').first().click();
  }

  /** 点击表格中指定名称行的删除链接，并确认 Popconfirm */
  async clickDelete(name: string) {
    const row = this.getTableRow(name);
    await row.locator('a').filter({ hasText: '删除' }).first().click();
    await this.confirmPopconfirm();
  }

  /** 点击表格中指定名称行的测试链接 */
  async clickTest(name: string) {
    const row = this.getTableRow(name);
    await row.locator('a').filter({ hasText: '测试' }).first().click();
  }

  /** 点击表格中指定名称行的 Switch 切换启用/禁用 */
  async clickToggle(name: string) {
    const row = this.getTableRow(name);
    const sw = row.locator('.ant-switch').first();
    await sw.click();
  }

  /* ---- 断言 ---- */

  /** 断言表格中存在指定名称的 Provider */
  async expectProviderInTable(name: string) {
    const row = this.getTableRow(name);
    await expect(row).toBeVisible({ timeout: 5_000 });
  }

  /** 断言表格中不存在指定名称的 Provider */
  async expectProviderNotInTable(name: string) {
    const count = await this.page.getByRole('row', { name: new RegExp(name) }).count();
    if (count > 0) {
      throw new Error(`预期表格中不包含 "${name}"，但找到了`);
    }
  }

  /* ---- 辅助 ---- */

  /** 获取包含指定名称的表格行 Locator */
  getTableRow(name: string): Locator {
    return this.page.getByRole('row', { name: new RegExp(`\\b${escapeRegExp(name)}\\b`) }).first();
  }
}

/** 转义正则特殊字符 */
function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
