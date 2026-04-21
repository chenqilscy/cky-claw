# Kasaya Kubernetes 部署指南

## 概述

Kasaya 提供 Helm Chart 实现 Kubernetes 一键部署，支持以下能力：

- **四服务编排**：Backend + Frontend + PostgreSQL + Redis
- **三环境 Overlay**：dev / staging / prod 差异化配置
- **弹性伸缩**：HPA（基于 CPU/内存自动扩缩）
- **高可用**：PDB（Pod Disruption Budget，升级不中断）
- **TLS + Ingress**：Nginx Ingress + cert-manager 自动证书
- **数据库迁移**：Helm pre-install/pre-upgrade Hook 自动执行 Alembic
- **Secret 管理**：支持 existingSecret 引用外部密钥

## 目录结构

```
deploy/helm/kasaya/
├── Chart.yaml                    # Chart 元数据（v0.1.0）
├── values.yaml                   # 默认配置
├── overlays/
│   ├── dev.yaml                  # 开发环境（单副本、无 HPA）
│   ├── staging.yaml              # 预发布（2 副本、HPA、TLS）
│   └── prod.yaml                 # 生产（3+ 副本、外部 DB、Anti-Affinity）
└── templates/
    ├── _helpers.tpl              # 模板辅助函数
    ├── NOTES.txt                 # 安装后提示
    ├── secret.yaml               # JWT / PostgreSQL / Redis Secret
    ├── configmap.yaml            # Backend 环境变量 ConfigMap
    ├── backend-deployment.yaml   # Backend Deployment + Service
    ├── frontend-deployment.yaml  # Frontend Deployment + Service
    ├── postgresql.yaml           # PostgreSQL StatefulSet + Service + Init SQL
    ├── redis.yaml                # Redis StatefulSet + Service
    ├── migration-job.yaml        # Alembic 迁移 Job（Helm Hook）
    ├── ingress.yaml              # Ingress 资源
    ├── hpa.yaml                  # HorizontalPodAutoscaler
    └── pdb.yaml                  # PodDisruptionBudget
```

## 前置要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Kubernetes | 1.27+ | 需要 `autoscaling/v2` API |
| Helm | 3.12+ | Chart apiVersion: v2 |
| kubectl | 1.27+ | 与集群版本匹配 |
| Ingress Controller | — | 推荐 nginx-ingress |
| cert-manager | 1.12+（可选） | 自动 TLS 证书 |

## 快速开始

### 1. 构建镜像

```bash
# Backend 镜像
docker build -t kasaya/backend:latest -f backend/Dockerfile .

# Frontend 镜像
docker build -t kasaya/frontend:latest -f frontend/Dockerfile frontend/
```

### 2. 开发环境部署

```bash
# 创建命名空间
kubectl create namespace kasaya-dev

# 安装（使用开发配置）
helm install kasaya deploy/helm/kasaya \
  -n kasaya-dev \
  -f deploy/helm/kasaya/overlays/dev.yaml \
  --set postgresql.auth.password=dev-password \
  --set redis.auth.password=dev-password
```

### 3. Staging 环境部署

```bash
kubectl create namespace kasaya-staging

helm install kasaya deploy/helm/kasaya \
  -n kasaya-staging \
  -f deploy/helm/kasaya/overlays/staging.yaml \
  --set postgresql.auth.password=$(openssl rand -base64 32) \
  --set redis.auth.password=$(openssl rand -base64 32) \
  --set secret.jwtSecretKey=$(openssl rand -base64 64)
```

### 4. 生产环境部署

```bash
# 先创建外部 Secret
kubectl create namespace kasaya

kubectl create secret generic kasaya-db-secret \
  -n kasaya \
  --from-literal=postgresql-password='<RDS密码>'

kubectl create secret generic kasaya-redis-secret \
  -n kasaya \
  --from-literal=redis-password='<Redis密码>'

kubectl create secret generic kasaya-app-secret \
  -n kasaya \
  --from-literal=jwt-secret-key="$(openssl rand -base64 64)"

# 安装
helm install kasaya deploy/helm/kasaya \
  -n kasaya \
  -f deploy/helm/kasaya/overlays/prod.yaml \
  --set externalDatabase.host=your-rds.amazonaws.com \
  --set externalRedis.host=your-redis.cache.amazonaws.com
```

## 升级

```bash
# 修改镜像版本或配置后升级
helm upgrade kasaya deploy/helm/kasaya \
  -n kasaya \
  -f deploy/helm/kasaya/overlays/prod.yaml

# 迁移 Job 会自动在 upgrade 前执行
```

## 回滚

```bash
# 查看发布历史
helm history kasaya -n kasaya

# 回滚到上一版本
helm rollback kasaya -n kasaya

# 回滚到指定版本
helm rollback kasaya 3 -n kasaya
```

## 配置说明

### 核心配置项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `backend.replicaCount` | 2 | Backend 副本数 |
| `backend.autoscaling.enabled` | true | 启用 HPA |
| `backend.autoscaling.maxReplicas` | 10 | 最大副本数 |
| `frontend.replicaCount` | 2 | Frontend 副本数 |
| `postgresql.enabled` | true | 启用内置 PostgreSQL |
| `redis.enabled` | true | 启用内置 Redis |
| `ingress.enabled` | true | 启用 Ingress |
| `ingress.className` | nginx | Ingress Class |

### 外部数据库

生产环境建议使用托管的 PostgreSQL（如 AWS RDS、阿里云 RDS）：

```yaml
postgresql:
  enabled: false

externalDatabase:
  host: "your-rds-endpoint"
  port: 5432
  database: kasaya
  username: kasaya
  existingSecret: "kasaya-db-secret"
```

### TLS 配置

使用 cert-manager 自动管理证书：

```yaml
ingress:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  tls:
    - secretName: kasaya-tls
      hosts:
        - kasaya.example.com
```

### 私有镜像仓库

```yaml
global:
  imageRegistry: "harbor.example.com/kasaya"
  imagePullSecrets:
    - name: harbor-pull-secret
```

## 运维操作

### 查看状态

```bash
# Pod 状态
kubectl get pods -n kasaya -l app.kubernetes.io/part-of=kasaya

# HPA 状态
kubectl get hpa -n kasaya

# PDB 状态
kubectl get pdb -n kasaya
```

### 查看日志

```bash
# Backend 日志
kubectl logs -n kasaya -l app.kubernetes.io/component=backend --tail=100 -f

# 迁移 Job 日志
kubectl logs -n kasaya -l app.kubernetes.io/component=migration
```

### 手动扩缩

```bash
kubectl scale deployment kasaya-backend -n kasaya --replicas=5
```

### 端口转发（调试）

```bash
# 访问 Backend API
kubectl port-forward -n kasaya svc/kasaya-backend 8000:8000

# 访问 Frontend
kubectl port-forward -n kasaya svc/kasaya-frontend 3000:3000
```

## 健康检查

Backend 提供三级健康检查探针：

| 探针 | 端点 | 间隔 | 说明 |
|------|------|------|------|
| Startup | `/health` | 5s × 12 次 | 启动时等待应用就绪 |
| Readiness | `/health` | 5s | 就绪后接收流量 |
| Liveness | `/health` | 10s | 存活检测，失败重启 |

## 架构图

```
                    ┌─────────────┐
                    │   Ingress   │
                    │ (nginx/tls) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │ /api/*     │ /*         │
              ▼            │            ▼
    ┌─────────────────┐    │   ┌─────────────────┐
    │ Backend Service │    │   │ Frontend Service│
    │   (ClusterIP)   │    │   │   (ClusterIP)   │
    └────────┬────────┘    │   └────────┬────────┘
             │             │            │
    ┌────────▼────────┐    │   ┌────────▼────────┐
    │  Backend Pods   │    │   │ Frontend Pods   │
    │  (2-10, HPA)    │    │   │  (2-5, HPA)     │
    └────────┬────────┘    │   └─────────────────┘
             │             │
    ┌────────┼────────┐    │
    │        │        │    │
    ▼        ▼        │    │
┌───────┐ ┌───────┐   │   │
│  PG   │ │ Redis │   │   │
│(SS/1) │ │(SS/1) │   │   │
└───────┘ └───────┘   │   │
                       │   │
              ┌────────▼───┘
              │  Migration
              │  Job (Hook)
              └────────────
```
