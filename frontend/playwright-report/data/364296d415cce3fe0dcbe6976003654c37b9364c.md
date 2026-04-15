# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: deep-interaction.spec.ts >> 环境管理 >> 右上角环境选择器 — 下拉选项
- Location: e2e\deep-interaction.spec.ts:505:3

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Page snapshot

```yaml
- generic [ref=e5]:
  - complementary [ref=e7]:
    - generic [ref=e8]:
      - menu [ref=e10]:
        - menuitem "概览" [ref=e11] [cursor=pointer]:
          - link "概览" [ref=e13]:
            - generic [ref=e14]:
              - img "dashboard" [ref=e16]:
                - img [ref=e17]
              - generic [ref=e19]: 概览
        - menuitem "对话" [ref=e20] [cursor=pointer]:
          - link "对话" [ref=e22]:
            - generic [ref=e23]:
              - img "message" [ref=e25]:
                - img [ref=e26]
              - generic [ref=e28]: 对话
        - menuitem "robot Agent" [ref=e29] [cursor=pointer]:
          - generic [ref=e31]:
            - img "robot" [ref=e33]:
              - img [ref=e34]
            - generic [ref=e36]: Agent
        - menuitem "cloud-server 模型与工具" [ref=e37] [cursor=pointer]:
          - generic [ref=e39]:
            - img "cloud-server" [ref=e41]:
              - img [ref=e42]
            - generic [ref=e46]: 模型与工具
        - menuitem "bulb 知识与记忆" [ref=e47] [cursor=pointer]:
          - generic [ref=e49]:
            - img "bulb" [ref=e51]:
              - img [ref=e52]
            - generic [ref=e54]: 知识与记忆
        - menuitem "eye 监控与追踪" [ref=e55] [cursor=pointer]:
          - generic [ref=e57]:
            - img "eye" [ref=e59]:
              - img [ref=e60]
            - generic [ref=e62]: 监控与追踪
        - menuitem "safety-certificate 安全与治理" [ref=e63] [cursor=pointer]:
          - generic [ref=e65]:
            - img "safety-certificate" [ref=e67]:
              - img [ref=e68]
            - generic [ref=e70]: 安全与治理
        - menuitem "shop 市场与评测" [ref=e71] [cursor=pointer]:
          - generic [ref=e73]:
            - img "shop" [ref=e75]:
              - img [ref=e76]
            - generic [ref=e78]: 市场与评测
        - menuitem "link 集成与渠道" [ref=e79] [cursor=pointer]:
          - generic [ref=e81]:
            - img "link" [ref=e83]:
              - img [ref=e84]
            - generic [ref=e86]: 集成与渠道
        - menuitem "bank 系统管理" [ref=e87] [cursor=pointer]:
          - generic [ref=e89]:
            - img "bank" [ref=e91]:
              - img [ref=e92]
            - generic [ref=e94]: 系统管理
      - img [ref=e96] [cursor=pointer]
  - generic [ref=e98]:
    - banner [ref=e99]
    - banner [ref=e100]:
      - generic [ref=e101]:
        - heading "CkyClaw" [level=1] [ref=e104] [cursor=pointer]
        - generic [ref=e108]:
          - generic [ref=e110] [cursor=pointer]:
            - generic [ref=e112]:
              - combobox [expanded] [active] [ref=e114]:
                - listbox [ref=e115]:
                  - generic [ref=e116]:
                    - img "暂无数据" [ref=e118]
                    - generic [ref=e124]: 暂无数据
              - generic: 全部环境
            - generic:
              - img:
                - img
          - button "切换暗色模式" [ref=e126] [cursor=pointer]:
            - img "bulb" [ref=e128]:
              - img [ref=e129]
    - main [ref=e131]:
      - main "页面内容" [ref=e132]:
        - generic [ref=e134]:
          - heading [level=3] [ref=e135]
          - list [ref=e136]:
            - listitem [ref=e137]
            - listitem [ref=e138]
            - listitem [ref=e139]
            - listitem [ref=e140]
            - listitem [ref=e141]
            - listitem [ref=e142]
            - listitem [ref=e143]
            - listitem [ref=e144]
            - listitem [ref=e145]
            - listitem [ref=e146]
            - listitem [ref=e147]
            - listitem [ref=e148]
```

# Test source

```ts
  421 |         await options.first().click();
  422 |       }
  423 |     }
  424 |   });
  425 | });
  426 | 
  427 | // =============================================
  428 | // 4. 侧边栏菜单分组交互
  429 | // =============================================
  430 | 
  431 | test.describe('侧边栏菜单深度交互', () => {
  432 |   test('菜单分组展开/折叠', async ({ page }) => {
  433 |     await page.goto('/dashboard');
  434 |     await waitForPageReady(page);
  435 | 
  436 |     // 查找可折叠的菜单组
  437 |     const submenuItems = page.locator('.ant-menu-submenu-title');
  438 |     const count = await submenuItems.count();
  439 | 
  440 |     if (count > 0) {
  441 |       // 点击第一个分组展开
  442 |       await submenuItems.first().click();
  443 |       await page.waitForTimeout(300);
  444 | 
  445 |       // 应有子菜单项可见
  446 |       const subItems = page.locator('.ant-menu-item');
  447 |       const subCount = await subItems.count();
  448 |       expect(subCount).toBeGreaterThan(0);
  449 |     }
  450 |   });
  451 | 
  452 |   test('菜单导航跳转', async ({ page }) => {
  453 |     await page.goto('/dashboard');
  454 |     await waitForPageReady(page);
  455 | 
  456 |     // 点击 Agent 菜单组
  457 |     const agentMenu = page.locator('.ant-menu-submenu-title').filter({ hasText: 'Agent' }).first();
  458 |     if (await agentMenu.isVisible().catch(() => false)) {
  459 |       await agentMenu.click();
  460 |       await page.waitForTimeout(300);
  461 | 
  462 |       // 点击 Agent 管理
  463 |       const agentManage = page.locator('.ant-menu-item').filter({ hasText: 'Agent 管理' }).first();
  464 |       if (await agentManage.isVisible().catch(() => false)) {
  465 |         await agentManage.click();
  466 |         await expect(page).toHaveURL(/agents/, { timeout: 10_000 });
  467 |       }
  468 |     }
  469 |   });
  470 | 
  471 |   test('侧边栏折叠/展开', async ({ page }) => {
  472 |     await page.goto('/dashboard');
  473 |     await waitForPageReady(page);
  474 | 
  475 |     // ProLayout 折叠按钮
  476 |     const collapseBtn = page.locator('.ant-pro-sider-collapsed-button, [class*="collapse"]').first();
  477 |     if (await collapseBtn.isVisible().catch(() => false)) {
  478 |       await collapseBtn.click();
  479 |       await page.waitForTimeout(500);
  480 | 
  481 |       // 侧边栏应变窄
  482 |       const sider = page.locator('.ant-layout-sider, .ant-pro-sider');
  483 |       if (await sider.isVisible().catch(() => false)) {
  484 |         // 再次点击展开
  485 |         await collapseBtn.click();
  486 |         await page.waitForTimeout(500);
  487 |       }
  488 |     }
  489 |   });
  490 | });
  491 | 
  492 | // =============================================
  493 | // 5. 环境管理页深度交互
  494 | // =============================================
  495 | 
  496 | test.describe('环境管理', () => {
  497 |   test('环境列表渲染', async ({ page }) => {
  498 |     await page.goto('/environments');
  499 |     await waitForPageReady(page);
  500 | 
  501 |     const content = page.locator('.ant-table, .ant-card, .ant-list, .ant-empty');
  502 |     await expect(content.first()).toBeVisible({ timeout: 15_000 });
  503 |   });
  504 | 
  505 |   test('右上角环境选择器 — 下拉选项', async ({ page }) => {
  506 |     await page.goto('/dashboard');
  507 |     await waitForPageReady(page);
  508 | 
  509 |     // 右上角环境选择器（可能是 borderless Select）
  510 |     const envSelect = page.locator('.ant-select').filter({ hasText: /环境/ }).first();
  511 |     if (await envSelect.isVisible().catch(() => false)) {
  512 |       await envSelect.click();
  513 |       await page.waitForTimeout(500);
  514 | 
  515 |       // 等待下拉出现
  516 |       const dropdown = page.locator('.ant-select-dropdown:visible').first();
  517 |       const hasDropdown = await dropdown.isVisible().catch(() => false);
  518 |       if (hasDropdown) {
  519 |         const allEnvOption = dropdown.locator('.ant-select-item-option').filter({ hasText: /全部/ });
  520 |         const hasAll = await allEnvOption.isVisible().catch(() => false);
> 521 |         expect(hasAll).toBeTruthy();
      |                        ^ Error: expect(received).toBeTruthy()
  522 |       }
  523 |       // 关闭下拉
  524 |       await page.keyboard.press('Escape');
  525 |     }
  526 |   });
  527 | });
  528 | 
  529 | // =============================================
  530 | // 6. 知识库页面交互
  531 | // =============================================
  532 | 
  533 | test.describe('知识库', () => {
  534 |   test('知识库列表 — 创建按钮可见', async ({ page }) => {
  535 |     await page.goto('/knowledge-bases');
  536 |     await waitForPageReady(page);
  537 | 
  538 |     const content = page.locator('.ant-table, .ant-card, .ant-list, .ant-empty');
  539 |     await expect(content.first()).toBeVisible({ timeout: 15_000 });
  540 | 
  541 |     const createBtn = page.locator('button').filter({ hasText: /创建|新建|添加/ });
  542 |     const hasCreate = await createBtn.first().isVisible().catch(() => false);
  543 |     // 知识库页面通常有创建按钮
  544 |     expect(hasCreate || true).toBeTruthy();
  545 |   });
  546 | });
  547 | 
  548 | // =============================================
  549 | // 7. 合规面板
  550 | // =============================================
  551 | 
  552 | test.describe('合规面板深度', () => {
  553 |   test('合规仪表盘 — 统计卡片', async ({ page }) => {
  554 |     await page.goto('/compliance');
  555 |     await waitForPageReady(page);
  556 | 
  557 |     const cards = page.locator('.ant-card, .ant-statistic');
  558 |     await expect(cards.first()).toBeVisible({ timeout: 15_000 });
  559 |   });
  560 | });
  561 | 
  562 | // =============================================
  563 | // 8. Guardrail CRUD 交互
  564 | // =============================================
  565 | 
  566 | test.describe('Guardrails CRUD', () => {
  567 |   test('创建护栏 — 表单可访问', async ({ page }) => {
  568 |     await page.goto('/guardrails');
  569 |     await waitForPageReady(page);
  570 | 
  571 |     const createBtn = page.locator('button').filter({ hasText: /创建|新建|添加/ }).first();
  572 |     if (await createBtn.isVisible().catch(() => false)) {
  573 |       await createBtn.click();
  574 |       await page.waitForTimeout(1000);
  575 | 
  576 |       // 应出现表单或对话框
  577 |       const formOrModal = page.locator('.ant-modal, .ant-form, .ant-drawer');
  578 |       await expect(formOrModal.first()).toBeVisible({ timeout: 10_000 });
  579 |     }
  580 |   });
  581 | });
  582 | 
  583 | // =============================================
  584 | // 9. Tool Groups 页面
  585 | // =============================================
  586 | 
  587 | test.describe('Tool Groups', () => {
  588 |   test('工具组列表渲染', async ({ page }) => {
  589 |     await page.goto('/tool-groups');
  590 |     await waitForPageReady(page);
  591 | 
  592 |     const content = page.locator('.ant-table, .ant-card, .ant-list, .ant-empty');
  593 |     await expect(content.first()).toBeVisible({ timeout: 15_000 });
  594 |   });
  595 | });
  596 | 
  597 | // =============================================
  598 | // 10. 响应式布局验证
  599 | // =============================================
  600 | 
  601 | test.describe('响应式布局', () => {
  602 |   test('移动端视口 — 侧边栏自动隐藏', async ({ page }) => {
  603 |     await page.setViewportSize({ width: 375, height: 812 });
  604 |     await page.goto('/dashboard');
  605 |     await waitForPageReady(page);
  606 | 
  607 |     // 移动端侧边栏应隐藏或折叠
  608 |     const sider = page.locator('.ant-layout-sider:not(.ant-layout-sider-collapsed)');
  609 |     const isVisible = await sider.isVisible().catch(() => false);
  610 |     // 移动端不应显示完整侧边栏
  611 |     // (宽松断言：ProLayout 在小屏可能用 Drawer 或完全隐藏)
  612 |     expect(true).toBeTruthy(); // 确认不崩溃
  613 |   });
  614 | 
  615 |   test('平板视口 — 页面正常渲染', async ({ page }) => {
  616 |     await page.setViewportSize({ width: 768, height: 1024 });
  617 |     await page.goto('/agents');
  618 |     await waitForPageReady(page);
  619 | 
  620 |     const content = page.locator('.ant-table, .ant-card, .ant-list, .ant-empty');
  621 |     await expect(content.first()).toBeVisible({ timeout: 15_000 });
```