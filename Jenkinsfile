// CkyClaw Jenkins Pipeline
// docker run 通过 /var/run/docker.sock 在宿主机执行
// -v 挂载必须使用宿主机路径（HOST_WS），而非 Jenkins 容器内路径

pipeline {
    agent any

    environment {
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        // 宿主机上 Jenkins workspace 的实际路径
        HOST_WS = '/@appdata/1Panel/1panel/apps/jenkins/jenkins/data/workspace/cky-claw'
    }

    stages {
        stage('Lint') {
            parallel {
                stage('Framework Lint') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
                            cd ckyclaw-framework
                            uv sync --extra dev 2>/dev/null
                            uv run ruff check .
                            uv run ruff format --check .
                        ' '''
                    }
                }
                stage('Backend Lint') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
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

        stage('Test') {
            parallel {
                stage('Framework Test') {
                    steps {
                        sh '''docker run --rm -v ${HOST_WS}:/app -w /app python:3.12-slim bash -c '
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
                        sh '''docker run --rm --network host -v ${HOST_WS}:/app -w /app python:3.12-slim bash -c '
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

        stage('Docker Build') {
            steps {
                sh """
                    docker build -t ckyclaw-backend:\${IMAGE_TAG} -t ckyclaw-backend:latest \
                        -f \${HOST_WS}/backend/Dockerfile \${HOST_WS}
                    docker build -t ckyclaw-frontend:\${IMAGE_TAG} -t ckyclaw-frontend:latest \
                        -f \${HOST_WS}/frontend/Dockerfile \${HOST_WS}/frontend/
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
