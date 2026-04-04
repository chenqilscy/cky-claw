// CkyClaw Jenkins Pipeline
// 前置：Jenkins 容器挂载 /var/run/docker.sock
// 注意：docker run 通过 socket 在宿主机执行，-v 必须用宿主机路径

pipeline {
    agent any

    environment {
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        // Jenkins 容器内 workspace 路径 → 宿主机实际路径映射
        // 容器内: /var/jenkins_home → 宿主机: /@appdata/1Panel/1panel/apps/jenkins/jenkins/data
        HOST_WS = '/@appdata/1Panel/1panel/apps/jenkins/jenkins/data/workspace/cky-claw'
    }

    stages {
        // ── 0. 调试：检查 workspace ──
        stage('Debug') {
            steps {
                sh 'echo "PWD=$PWD"'
                sh 'echo "HOST_WS=$HOST_WS"'
                sh 'ls -la'
                sh 'ls -la frontend/ || echo "NO frontend/"'
                sh 'ls -la backend/ || echo "NO backend/"'
                sh 'ls -la ckyclaw-framework/ || echo "NO ckyclaw-framework/"'
                // 也检查宿主机路径
                sh 'docker run --rm -v ${HOST_WS}:/mnt -w /mnt alpine ls -la || echo "Host path mount failed"'
            }
        }

        // ── 1. 并行 Lint ──
        stage('Lint') {
            parallel {
                stage('Framework Lint') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app python:3.12-slim sh -c '
                            pip install -q uv ruff 2>/dev/null
                            cd ckyclaw-framework
                            uv sync --extra dev 2>/dev/null
                            uv run ruff check .
                            uv run ruff format --check .
                        ' '''
                    }
                }
                stage('Backend Lint') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app python:3.12-slim sh -c '
                            pip install -q uv ruff 2>/dev/null
                            cd backend
                            uv sync --extra dev 2>/dev/null
                            uv run ruff check .
                            uv run ruff format --check .
                        ' '''
                    }
                }
                stage('Frontend Lint') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app node:20-alpine sh -c '
                            corepack enable && corepack prepare pnpm@latest --activate
                            cd frontend
                            pnpm install --frozen-lockfile
                            pnpm lint
                            npx tsc --noEmit
                        ' '''
                    }
                }
            }
        }

        // ── 2. 并行测试 ──
        stage('Test') {
            parallel {
                stage('Framework Test') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app python:3.12-slim sh -c '
                            pip install -q uv 2>/dev/null
                            cd ckyclaw-framework
                            uv sync --extra dev 2>/dev/null
                            uv run pytest tests/ \
                                --ignore=tests/test_integration.py \
                                --ignore=tests/test_e2e_integration.py \
                                --ignore=tests/test_e2e_phase69.py \
                                --ignore=tests/test_mcp_integration.py \
                                -q --tb=short
                        ' '''
                    }
                }
                stage('Backend Test') {
                    steps {
                        // --network host 连接宿主机 PostgreSQL (15432)
                        sh '''docker run --rm --network host -v ${HOST_WS}:/app -w /app python:3.12-slim sh -c '
                            pip install -q uv 2>/dev/null
                            cd backend
                            uv sync --extra dev 2>/dev/null
                            CKYCLAW_DATABASE_URL=postgresql+asyncpg://admin:Admin888@127.0.0.1:15432/ckyclaw \
                            uv run pytest tests/ \
                                --ignore=tests/test_smoke.py \
                                --ignore=tests/test_performance.py \
                                --ignore=tests/test_e2e_backend.py \
                                --ignore=tests/test_mcp_integration.py \
                                -q --tb=short
                        ' '''
                    }
                }
                stage('Frontend Test') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app node:20-alpine sh -c '
                            corepack enable && corepack prepare pnpm@latest --activate
                            cd frontend
                            pnpm install --frozen-lockfile
                            pnpm test -- --run
                        ' '''
                    }
                }
            }
        }

        // ── 3. 前端构建 ──
        stage('Frontend Build') {
            steps {
                sh '''docker run --rm -v ${HOST_WS}:/app -w /app node:20-alpine sh -c '
                    corepack enable && corepack prepare pnpm@latest --activate
                    cd frontend
                    pnpm install --frozen-lockfile
                    pnpm build
                ' '''
            }
        }

        // ── 4. Docker 镜像构建 ──
        stage('Docker Build') {
            steps {
                // docker build 在宿主机执行，-f 路径用 HOST_WS
                sh """
                    docker build -t ckyclaw-backend:\${IMAGE_TAG} -t ckyclaw-backend:latest \
                        -f backend/Dockerfile \${HOST_WS}
                    docker build -t ckyclaw-frontend:\${IMAGE_TAG} -t ckyclaw-frontend:latest \
                        -f frontend/Dockerfile \${HOST_WS}/frontend/
                """
            }
        }
    }

    post {
        failure {
            echo '构建失败，请检查日志'
        }
        success {
            echo "构建成功 #${env.BUILD_NUMBER}"
        }
    }
}
