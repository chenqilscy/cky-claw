import { api } from './api';

export interface SystemInfo {
  otel_enabled: boolean;
  otel_service_name: string;
  otel_exporter_endpoint: string;
  jaeger_ui_url: string;
  prometheus_ui_url: string;
}

export const systemService = {
  info: () => api.get<SystemInfo>('/system/info'),
};
