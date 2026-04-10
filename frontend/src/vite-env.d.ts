/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** OTel 链路追踪开关（'true' 启用） */
  readonly VITE_OTEL_ENABLED?: string;
  /** OTLP HTTP 端点（默认 '/otlp'） */
  readonly VITE_OTEL_ENDPOINT?: string;
  /** 应用版本号 */
  readonly VITE_APP_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
