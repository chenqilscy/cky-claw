{{/*
CkyClaw Helm 模板辅助函数
*/}}

{{/*
展开 Chart 全名
*/}}
{{- define "ckyclaw.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart 标签
*/}}
{{- define "ckyclaw.labels" -}}
helm.sh/chart: {{ include "ckyclaw.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: ckyclaw
{{- end }}

{{/*
Chart 名称+版本
*/}}
{{- define "ckyclaw.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Backend 选择器标签
*/}}
{{- define "ckyclaw.backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ckyclaw.fullname" . }}-backend
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend 选择器标签
*/}}
{{- define "ckyclaw.frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ckyclaw.fullname" . }}-frontend
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
PostgreSQL 选择器标签
*/}}
{{- define "ckyclaw.postgresql.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ckyclaw.fullname" . }}-postgresql
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: postgresql
{{- end }}

{{/*
Redis 选择器标签
*/}}
{{- define "ckyclaw.redis.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ckyclaw.fullname" . }}-redis
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: redis
{{- end }}

{{/*
数据库连接 URL
*/}}
{{- define "ckyclaw.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgresql+asyncpg://%s:$(POSTGRES_PASSWORD)@%s-postgresql:5432/%s" .Values.postgresql.auth.username (include "ckyclaw.fullname" .) .Values.postgresql.auth.database }}
{{- else }}
{{- printf "postgresql+asyncpg://%s:$(POSTGRES_PASSWORD)@%s:%d/%s" .Values.externalDatabase.username .Values.externalDatabase.host (int .Values.externalDatabase.port) .Values.externalDatabase.database }}
{{- end }}
{{- end }}

{{/*
Redis 连接 URL
*/}}
{{- define "ckyclaw.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://:%s@%s-redis:6379/0" "$(REDIS_PASSWORD)" (include "ckyclaw.fullname" .) }}
{{- else }}
{{- printf "redis://:%s@%s:%d/0" "$(REDIS_PASSWORD)" .Values.externalRedis.host (int .Values.externalRedis.port) }}
{{- end }}
{{- end }}

{{/*
Secret 名称
*/}}
{{- define "ckyclaw.secretName" -}}
{{- if .Values.secret.existingSecret }}
{{- .Values.secret.existingSecret }}
{{- else }}
{{- include "ckyclaw.fullname" . }}
{{- end }}
{{- end }}

{{/*
PostgreSQL Secret 名称
*/}}
{{- define "ckyclaw.postgresql.secretName" -}}
{{- if .Values.postgresql.auth.existingSecret }}
{{- .Values.postgresql.auth.existingSecret }}
{{- else }}
{{- include "ckyclaw.fullname" . }}-postgresql
{{- end }}
{{- end }}

{{/*
Redis Secret 名称
*/}}
{{- define "ckyclaw.redis.secretName" -}}
{{- if .Values.redis.auth.existingSecret }}
{{- .Values.redis.auth.existingSecret }}
{{- else }}
{{- include "ckyclaw.fullname" . }}-redis
{{- end }}
{{- end }}

{{/*
镜像全名（含 registry 前缀）
*/}}
{{- define "ckyclaw.image" -}}
{{- $registry := .global.imageRegistry | default "" }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry .image.repository .image.tag }}
{{- else }}
{{- printf "%s:%s" .image.repository .image.tag }}
{{- end }}
{{- end }}
