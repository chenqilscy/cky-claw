# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> 认证后页面 >> IM Channels 渠道页可加载
- Location: frontend\e2e\smoke.spec.ts:130:3

# Error details

```
Error: page.goto: net::ERR_HTTP_RESPONSE_CODE_FAILURE at http://fn.cky:3000/im-channels
Call log:
  - navigating to "http://fn.cky:3000/im-channels", waiting until "load"

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
  110 |   test('Workflows 工作流页可加载', async ({ page }) => {
  111 |     await page.goto('/workflows');
  112 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  113 |   });
  114 | 
  115 |   test('Teams 团队页可加载', async ({ page }) => {
  116 |     await page.goto('/teams');
  117 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  118 |   });
  119 | 
  120 |   test('Audit Logs 审计日志页可加载', async ({ page }) => {
  121 |     await page.goto('/audit-logs');
  122 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  123 |   });
  124 | 
  125 |   test('Roles 角色管理页可加载', async ({ page }) => {
  126 |     await page.goto('/roles');
  127 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  128 |   });
  129 | 
  130 |   test('IM Channels 渠道页可加载', async ({ page }) => {
> 131 |     await page.goto('/im-channels');
      |                ^ Error: page.goto: net::ERR_HTTP_RESPONSE_CODE_FAILURE at http://fn.cky:3000/im-channels
  132 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  133 |   });
  134 | 
  135 |   test('Evaluations 评估页可加载', async ({ page }) => {
  136 |     await page.goto('/evaluations');
  137 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  138 |   });
  139 | 
  140 |   test('Evolution 进化页可加载', async ({ page }) => {
  141 |     await page.goto('/evolution');
  142 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  143 |   });
  144 | 
  145 |   test('Organizations 组织页可加载', async ({ page }) => {
  146 |     await page.goto('/organizations');
  147 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  148 |   });
  149 | 
  150 |   test('Scheduled Tasks 定时任务页可加载', async ({ page }) => {
  151 |     await page.goto('/scheduled-tasks');
  152 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  153 |   });
  154 | 
  155 |   test('APM 仪表盘页可加载', async ({ page }) => {
  156 |     await page.goto('/apm');
  157 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  158 |   });
  159 | 
  160 |   test('Cost Router 成本路由页可加载', async ({ page }) => {
  161 |     await page.goto('/cost-router');
  162 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  163 |   });
  164 | 
  165 |   test('Checkpoints 检查点页可加载', async ({ page }) => {
  166 |     await page.goto('/checkpoints');
  167 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  168 |   });
  169 | 
  170 |   test('Intent Detection 意图检测页可加载', async ({ page }) => {
  171 |     await page.goto('/intent');
  172 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  173 |   });
  174 | 
  175 |   test('Supervision 监管页可加载', async ({ page }) => {
  176 |     await page.goto('/supervision');
  177 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  178 |   });
  179 | 
  180 |   test('I18n 国际化设置页可加载', async ({ page }) => {
  181 |     await page.goto('/i18n');
  182 |     await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  183 |   });
  184 | });
  185 | 
```