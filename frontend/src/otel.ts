/**
 * OpenTelemetry Web SDK 初始化 — 前端链路追踪。
 *
 * 通过 Nginx/Vite 代理发送 OTLP HTTP 到 Jaeger Collector，
 * 路径: /otlp/v1/traces → jaeger:4318/v1/traces
 *
 * 自动采集：
 * - Fetch API 请求（含 trace context 传播到后端）
 * - XMLHttpRequest 请求
 * - 页面导航、路由切换等 performance 条目
 */
import { defaultResource, resourceFromAttributes } from '@opentelemetry/resources';
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } from '@opentelemetry/semantic-conventions';
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request';

/** 是否启用 OTel（通过环境变量控制，默认关闭） */
const OTEL_ENABLED = import.meta.env.VITE_OTEL_ENABLED === 'true';

/** OTLP HTTP 端点（默认同源 /otlp，由 Nginx/Vite proxy 转发到 Jaeger 4318） */
const OTLP_ENDPOINT = import.meta.env.VITE_OTEL_ENDPOINT as string || '/otlp';

/** 只对 API 请求传播 trace context */
const PROPAGATE_URLS = [/\/api\//];

/** 忽略 OTLP 自身的 export 请求，避免无限递归 */
const IGNORE_URLS = [/\/otlp\//, /\/v1\/traces/];

/**
 * 初始化前端 OpenTelemetry 链路追踪。
 * 在 React 渲染前调用，确保所有 fetch 请求都被自动埋点。
 */
export function initOtel(): void {
  if (!OTEL_ENABLED) {
    return;
  }

  try {
    const resource = defaultResource().merge(
      resourceFromAttributes({
        [ATTR_SERVICE_NAME]: 'kasaya-frontend',
        [ATTR_SERVICE_VERSION]: import.meta.env.VITE_APP_VERSION || '0.1.0',
      }),
    );

    const exporter = new OTLPTraceExporter({
      url: `${OTLP_ENDPOINT}/v1/traces`,
    });

    const provider = new WebTracerProvider({
      resource,
      spanProcessors: [new BatchSpanProcessor(exporter)],
    });

    provider.register({
      contextManager: new ZoneContextManager(),
    });

    registerInstrumentations({
      instrumentations: [
        new FetchInstrumentation({
          propagateTraceHeaderCorsUrls: PROPAGATE_URLS,
          applyCustomAttributesOnSpan: (span, _request, result) => {
            if (result instanceof Response) {
              span.setAttribute('http.response.status_code', result.status);
            }
          },
          ignoreUrls: IGNORE_URLS,
        }),
        new XMLHttpRequestInstrumentation({
          propagateTraceHeaderCorsUrls: PROPAGATE_URLS,
          ignoreUrls: IGNORE_URLS,
        }),
      ],
    });

    console.info('[OTel] Frontend tracing initialized → %s/v1/traces', OTLP_ENDPOINT);
  } catch (e) {
    console.warn('[OTel] Failed to initialize frontend tracing:', e);
  }
}
