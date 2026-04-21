# Kasaya 品牌更名实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将整个代码库从 CkyClaw 品牌更名为 Kasaya（芥子纳须弥——胸中自有天地万物）

**Architecture:** 纯批量文本替换 + 目录重命名。分 8 个阶段执行：目录结构 → Framework 包 → Backend → CLI → Frontend → 基础设施配置 → 文档 → 验证

**Tech Stack:** Python/uv (framework + backend + CLI), TypeScript/pnpm (frontend), Docker Compose, GitHub Actions

---

## 更名映射表

| 旧值 | 新值 | 说明 |
|------|------|------|
| `CkyClaw` | `Kasaya` | 品牌名（标题/注释/文档） |
| `ckyclaw_framework` | `kasaya` | Python 包名/模块名 |
| `ckyclaw-framework` | `kasaya` | pip 包名 |
| `ckyclaw-framework/` | `kasaya/` | 顶层目录 |
| `ckyclaw-framework/ckyclaw_framework/` | `kasaya/kasaya/` | Python 包目录 |
| `ckyclaw-cli` | `kasaya-cli` | CLI pip 包名/目录 |
| `ckyclaw_cli` | `kasaya_cli` | CLI Python 模块名 |
| `CKYCLAW_` | `KASAYA_` | 环境变量前缀 |
| `ckyclaw-backend` | `kasaya-backend` | Backend pip 包名 |
| `ckyclaw_token` | `kasaya_token` | 前端 localStorage key |
| `ckyclaw` (小写独立词) | `kasaya` | 数据库用户名/容器名等 |
| `CkyClawClient` | `KasayaClient` | CLI 客户端类名 |
| `CkyClaw Chat` | `Kasaya Chat` | CLI 界面标题 |

**替换顺序关键**：先替换长模式再替换短模式，避免部分匹配。顺序：
1. `ckyclaw_framework` → `kasaya`（最长，先处理）
2. `ckyclaw-framework` → `kasaya`
3. `ckyclaw-cli` → `kasaya-cli`
4. `ckyclaw_cli` → `kasaya_cli`
5. `ckyclaw-backend` → `kasaya-backend`
6. `CKYCLAW_` → `KASAYA_`
7. `CkyClaw` → `Kasaya`
8. `ckyclaw` → `kasaya`（最短，最后处理，仅替换作为独立词出现的）

---

### Task 1: 重命名顶层目录结构

**Files:**
- Rename: `ckyclaw-framework/` → `kasaya/`
- Rename: `ckyclaw-framework/ckyclaw_framework/` → `kasaya/kasaya/`
- Rename: `ckyclaw-cli/` → `kasaya-cli/`
- Rename: `ckyclaw-cli/ckyclaw_cli/` → `kasaya-cli/kasaya_cli/`

- [ ] **Step 1: 用 git mv 重命名 framework 顶层目录**

```bash
git mv ckyclaw-framework kasaya
```

- [ ] **Step 2: 重命名 framework 内的 Python 包目录**

```bash
git mv kasaya/ckyclaw_framework kasaya/kasaya
```

- [ ] **Step 3: 重命名 CLI 顶层目录**

```bash
git mv ckyclaw-cli kasaya-cli
```

- [ ] **Step 4: 重命名 CLI 内的 Python 模块目录**

```bash
git mv kasaya-cli/ckyclaw_cli kasaya-cli/kasaya_cli
```

- [ ] **Step 5: 验证目录结构正确**

```bash
ls -d kasaya/kasaya/ kasaya-cli/kasaya_cli/
```

Expected: 两个目录均存在

---

### Task 2: Framework 包内容替换

**Scope:** `kasaya/` 目录下所有 Python 文件和 pyproject.toml

- [ ] **Step 1: 替换 pyproject.toml 中的品牌名**

在 `kasaya/pyproject.toml` 中：
- `name = "ckyclaw-framework"` → `name = "kasaya"`
- `description` 中的 `CkyClaw Framework` → `Kasaya`
- `authors` 中的 `CkyClaw Team` → `Kasaya Team`

- [ ] **Step 2: 批量替换所有 Python 源文件中的 import 路径**

对 `kasaya/kasaya/` 下所有 `.py` 文件执行：
- `ckyclaw_framework` → `kasaya`（所有 import 和 patch 路径）

- [ ] **Step 3: 批量替换所有测试文件中的 import 路径**

对 `kasaya/tests/` 下所有 `.py` 文件执行：
- `ckyclaw_framework` → `kasaya`（所有 import 和 patch 路径）
- `CkyClaw` → `Kasaya`（所有注释和断言文本）

- [ ] **Step 4: 替换 examples 目录**

对 `kasaya/examples/` 下所有 `.py` 文件执行：
- `ckyclaw_framework` → `kasaya`

- [ ] **Step 5: 替换 README.md**

在 `kasaya/README.md` 中：
- `CkyClaw` → `Kasaya`
- `ckyclaw_framework` → `kasaya`
- `ckyclaw-framework` → `kasaya`

---

### Task 3: Backend 包内容替换

**Scope:** `backend/` 目录下所有文件

- [ ] **Step 1: 替换 pyproject.toml**

在 `backend/pyproject.toml` 中：
- `name = "ckyclaw-backend"` → `name = "kasaya-backend"`
- `description` 中的 `CkyClaw` → `Kasaya`
- `ckyclaw-framework` → `kasaya`（依赖声明）

- [ ] **Step 2: 批量替换 backend/app/ 下所有 Python 源文件**

对 `backend/app/` 下所有 `.py` 文件执行（按顺序）：
1. `ckyclaw_framework` → `kasaya`
2. `CKYCLAW_` → `KASAYA_`
3. `CkyClaw` → `Kasaya`
4. `ckyclaw` → `kasaya`

- [ ] **Step 3: 批量替换 backend/tests/ 下所有测试文件**

对 `backend/tests/` 下所有 `.py` 文件执行同样的 4 步替换。

- [ ] **Step 4: 替换 backend/scripts/ 下的文件**

- [ ] **Step 5: 替换 backend/Dockerfile**

在 `backend/Dockerfile` 中：
- `ckyclaw-framework` → `kasaya`
- `ckyclaw_framework` → `kasaya`

- [ ] **Step 6: 替换 backend/alembic 相关文件**（如有 ckyclaw 引用）

---

### Task 4: CLI 包内容替换

**Scope:** `kasaya-cli/` 目录下所有文件

- [ ] **Step 1: 替换 pyproject.toml**

在 `kasaya-cli/pyproject.toml` 中：
- `name = "ckyclaw-cli"` → `name = "kasaya-cli"`
- `description` 中的 `CkyClaw` → `Kasaya`
- `CkyClaw Team` → `Kasaya Team`
- `ckyclaw_cli` → `kasaya_cli`

- [ ] **Step 2: 替换所有 Python 源文件**

对 `kasaya-cli/kasaya_cli/` 下所有 `.py` 文件执行：
- `ckyclaw_framework` → `kasaya`
- `CkyClawClient` → `KasayaClient`
- `CkyClaw Chat` → `Kasaya Chat`
- `CkyClaw` → `Kasaya`
- `ckyclaw_cli` → `kasaya_cli`
- `ckyclaw` → `kasaya`

- [ ] **Step 3: 替换 README.md**

在 `kasaya-cli/README.md` 中执行同样的品牌名替换。

---

### Task 5: Frontend 内容替换

**Scope:** `frontend/` 目录下所有文件

- [ ] **Step 1: 替换 package.json**

在 `frontend/package.json` 中替换所有 `ckyclaw` / `CkyClaw` 引用。

- [ ] **Step 2: 批量替换 src/ 下所有 TypeScript/TSX 文件**

对 `frontend/src/` 下所有 `.ts` 和 `.tsx` 文件执行：
- `ckyclaw_token` → `kasaya_token`（localStorage key）
- `CkyClaw` → `Kasaya`（UI 文本）
- `ckyclaw` → `kasaya`

- [ ] **Step 3: 替换 index.html**

- [ ] **Step 4: 替换 E2E 测试文件**

对 `frontend/e2e/` 下所有 `.ts` 文件和 `frontend/test-results/` 下的 JSON 执行替换。

- [ ] **Step 5: 替换配置文件**

- `frontend/playwright.config.ts`
- `frontend/playwright.e2e.config.ts`
- `frontend/playwright.local.config.ts`

---

### Task 6: 基础设施配置替换

**Scope:** 根目录配置文件

- [ ] **Step 1: 替换 .env.example**

将所有 `CKYCLAW_` 前缀 → `KASAYA_`，`ckyclaw` 小写 → `kasaya`，`CkyClaw` → `Kasaya`。

- [ ] **Step 2: 替换 docker-compose.yml**

- `container_name: ckyclaw-*` → `container_name: kasaya-*`
- `CKYCLAW_*` 环境变量 → `KASAYA_*`
- `CkyClaw` 注释 → `Kasaya`
- `ckyclaw` 数据库用户/库名 → `kasaya`

- [ ] **Step 3: 替换 .github/workflows/ci.yml**

所有 `ckyclaw-framework` → `kasaya`，`ckyclaw_framework` → `kasaya`。

- [ ] **Step 4: 替换 Jenkinsfile**

- [ ] **Step 5: 替换 entrypoint.sh**（如果存在）

---

### Task 7: 文档和项目元数据替换

**Scope:** 根目录和 docs/ 下的所有 Markdown 文件

- [ ] **Step 1: 替换 CLAUDE.md**

将所有 CkyClaw 品牌引用更改为 Kasaya。更新包名、路径和命令示例。

- [ ] **Step 2: 替换 AGENTS.md**

- [ ] **Step 3: 替换 README.md**（根目录）

- [ ] **Step 4: 替换 docs/ 下所有 .md 文件**

对 `docs/` 下所有 `.md` 文件执行批量替换。包括重命名含 `CkyClaw` 的文件名：
- `docs/ckyclaw-cli-guide.md` → `docs/kasaya-cli-guide.md`
- `docs/compare-report/NextCrab vs CkyClaw 架构对比分析.md` → `docs/compare-report/NextCrab vs Kasaya 架构对比分析.md`
- `docs/spec/CkyClaw*.md` → `docs/spec/Kasaya*.md`（所有文件）

- [ ] **Step 5: 替换 backend/app/core/config.py 中的 Settings 前缀**

确认 `env_prefix = "CKYCLAW_"` → `env_prefix = "KASAYA_"`

---

### Task 8: uv.lock 文件重新生成

**Scope:** 各包的 lock 文件

- [ ] **Step 1: 重新生成 framework lock 文件**

```bash
cd kasaya && uv lock
```

- [ ] **Step 2: 重新生成 backend lock 文件**

```bash
cd backend && uv lock
```

- [ ] **Step 3: 重新生成 CLI lock 文件**

```bash
cd kasaya-cli && uv lock
```

---

### Task 9: 验证

- [ ] **Step 1: 全局搜索确认无残留**

```bash
grep -ri "ckyclaw\|CkyClaw\|CKYCLAW" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.toml" --include="*.yml" --include="*.md" --include="*.html" --include="*.json" --include="*.env*" --include="Dockerfile" --include="Jenkinsfile" --include="*.sh" . | grep -v ".git/" | grep -v "node_modules/" | grep -v "__pycache__/" | grep -v "uv.lock"
```

Expected: 0 matches

- [ ] **Step 2: 验证 Python 包可以正常导入**

```bash
cd kasaya && uv sync && uv run python -c "import kasaya; print(kasaya.__version__)" 2>/dev/null || uv run python -c "import kasaya; print('OK')"
```

- [ ] **Step 3: 验证 backend 可以正常启动**

```bash
cd backend && uv sync && uv run python -c "from app.main import create_app; print('OK')"
```

- [ ] **Step 4: 验证前端构建**

```bash
cd frontend && pnpm build
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: 品牌更名 CkyClaw → Kasaya（芥子纳须弥）"
```
