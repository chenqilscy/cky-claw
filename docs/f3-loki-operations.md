# F3 Loki 日志聚合操作手册

更新时间：2026-04-11

## 1. 架构说明

- Backend 输出结构化日志（JSON）
- Promtail 从 Docker 日志流采集并打标签
- Loki 存储与查询日志
- Grafana 作为日志检索与可视化入口
- Alertmanager 接收 Loki ruler 告警

## 2. 启动方式

在项目根目录执行：

```powershell
docker compose --profile loki --profile otel --profile jaeger up -d --build backend loki promtail grafana alertmanager prometheus jaeger
```

最小日志栈（不含指标与追踪）：

```powershell
docker compose --profile loki up -d loki promtail grafana alertmanager
```

## 3. 访问地址

- Grafana: http://fn.cky:3001
- Loki API: http://fn.cky:3100
- Alertmanager UI: http://fn.cky:19093
- Prometheus UI: http://fn.cky:19090
- Jaeger UI: http://fn.cky:16686

## 4. 预置内容

- 数据源: Loki, Jaeger, Prometheus
- 仪表盘: Kasaya Logs Overview
- Loki 规则: KasayaBackendHighErrorRate, KasayaBackendHasFatal

## 5. 常用 LogQL

1) 最近后端日志：

```logql
{job="backend"}
```

2) 按级别统计近 5 分钟：

```logql
sum by (level) (count_over_time({job="backend"}[5m]))
```

3) 近 5 分钟 ERROR 数：

```logql
sum(count_over_time({job="backend", level="ERROR"}[5m]))
```

4) 近 10 分钟 traceback：

```logql
{job="backend"} |= "Traceback"
```

## 6. 快速验收

执行脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/f3-loki-verify.ps1
```

预期：

- 3 个查询均返回 status=success
- Labels contains 'job': True

## 7. 常见故障排查

1) Loki 重启循环（权限）
- 现象：permission denied /tmp/loki/rules
- 处理：确认 compose 中 loki 以 user 0:0 运行，并挂载 lokidata

2) Grafana 无日志
- 检查 Promtail 状态与日志：
  - docker logs kasaya-promtail
- 检查 Loki ready：
  - http://fn.cky:3100/ready

3) 告警不触发
- 检查 Loki 规则加载：
  - GET /loki/api/v1/rules
- 检查 Alertmanager 状态：
  - http://fn.cky:19093
