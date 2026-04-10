# CkyClaw Frontend Dockerfile
FROM node:22-alpine AS build

WORKDIR /app

# 启用 pnpm（使用淘宝镜像加速）
ENV COREPACK_NPM_REGISTRY=https://registry.npmmirror.com
RUN corepack enable && corepack prepare pnpm@latest --activate

# npm 镜像
RUN npm config set registry https://registry.npmmirror.com

# 先复制依赖文件
COPY package.json pnpm-lock.yaml ./
ENV NODE_ENV=development
RUN echo "node-linker=hoisted" > .npmrc && pnpm install

# 复制源码并构建（Docker 中跳过 tsc 检查，仅 vite 构建）
COPY . .
ARG VITE_OTEL_ENABLED=true
ENV VITE_OTEL_ENABLED=${VITE_OTEL_ENABLED}
RUN pnpm exec vite build

# 清理 node_modules 以最小化 COPY 层（实际只用 dist）

# 生产阶段 — Nginx 静态服务
FROM nginx:alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
