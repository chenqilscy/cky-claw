# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> 关键页面加载 >> 登录页可访问
- Location: frontend\e2e\smoke.spec.ts:8:3

# Error details

```
Error: page.goto: net::ERR_HTTP_RESPONSE_CODE_FAILURE at http://fn.cky:3000/login
Call log:
  - navigating to "http://fn.cky:3000/login", waiting until "load"

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e6]:
    - heading "该网页无法正常运作" [level=1] [ref=e7]
    - paragraph [ref=e8]:
      - strong [ref=e9]: fn.cky
      - text: 目前无法处理此请求。
    - generic [ref=e10]: HTTP ERROR 502
  - button "重新加载" [ref=e13] [cursor=pointer]
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | 
  3   | /**
  4   |  * CkyClaw 前端 E2E 烟雾测试 — 验证关键页面可加载。
  5   |  */
  6   | 
  7   | test.describe('关键页面加载', () => {
  8   |   test('登录页可访问', async ({ page }) => {
> 9   |     await page.goto('/login');
      |                ^ Error: page.goto: net::ERR_HTTP_RESPONSE_CODE_FAILURE at http://fn.cky:3000/login
  10  |     await expect(page.locator('body')).toBeVisible();
  11  |     // 登录页应包含登录按钮或输入框
  12  |     const loginInput = page.locator('input[type="text"], input[type="email"], input[id="username"]');
  13  |     await expect(loginInput.first()).toBeVisible({ timeout: 10_000 });
  14  |   });
  15  | 
  16  |   test('未认证用户重定向到登录页', async ({ page }) => {
  17  |     await page.goto('/dashboard');
  18  |     // 应被重定向到登录页
  19  |     await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  20  |   });
  21  | 
  22  |   test('404 页面显示未找到提示', async ({ page }) => {
  23  |     await page.goto('/nonexistent-page-xyz');
  24  |     await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  25  |   });
  26  | });
  27  | 
  28  | test.describe('认证后页面', () => {
  29  |   test.beforeEach(async ({ page }) => {
  30  |     // 模拟已认证状态 — 注入 JWT token
  31  |     await page.addInitScript(() => {
  32  |       localStorage.setItem(
  33  |         'ckyclaw_token',
  34  |         'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjozMjUxODA0ODAwfQ.fake'
  35  |       );
  36  |     });
  37  |   });
  38  | 
  39  |   test('Dashboard 页面渲染标题', async ({ page }) => {
  40  |     await page.goto('/dashboard');
  41  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  42  |   });
  43  | 
  44  |   test('Agent 列表页可加载', async ({ page }) => {
  45  |     await page.goto('/agents');
  46  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  47  |   });
  48  | 
  49  |   test('A/B 测试页可加载', async ({ page }) => {
  50  |     await page.goto('/ab-test');
  51  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  52  |     await expect(page.locator('text=A/B').first()).toBeVisible({ timeout: 10_000 });
  53  |   });
  54  | 
  55  |   test('Traces 页可加载', async ({ page }) => {
  56  |     await page.goto('/traces');
  57  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  58  |   });
  59  | 
  60  |   test('Chat 对话页可加载', async ({ page }) => {
  61  |     await page.goto('/chat');
  62  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  63  |   });
  64  | 
  65  |   test('Runs 运行列表页可加载', async ({ page }) => {
  66  |     await page.goto('/runs');
  67  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  68  |   });
  69  | 
  70  |   test('Providers 模型提供商页可加载', async ({ page }) => {
  71  |     await page.goto('/providers');
  72  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  73  |   });
  74  | 
  75  |   test('Guardrails 护栏页可加载', async ({ page }) => {
  76  |     await page.goto('/guardrails');
  77  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  78  |   });
  79  | 
  80  |   test('Approvals 审批页可加载', async ({ page }) => {
  81  |     await page.goto('/approvals');
  82  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  83  |   });
  84  | 
  85  |   test('MCP Servers 页可加载', async ({ page }) => {
  86  |     await page.goto('/mcp-servers');
  87  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  88  |   });
  89  | 
  90  |   test('Tool Groups 工具组页可加载', async ({ page }) => {
  91  |     await page.goto('/tool-groups');
  92  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  93  |   });
  94  | 
  95  |   test('Memories 记忆页可加载', async ({ page }) => {
  96  |     await page.goto('/memories');
  97  |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  98  |   });
  99  | 
  100 |   test('Skills 技能页可加载', async ({ page }) => {
  101 |     await page.goto('/skills');
  102 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  103 |   });
  104 | 
  105 |   test('Templates 模板页可加载', async ({ page }) => {
  106 |     await page.goto('/templates');
  107 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  108 |   });
  109 | 
```