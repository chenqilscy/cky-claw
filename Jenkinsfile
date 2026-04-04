// CkyClaw Jenkins Pipeline
// 使用 --volumes-from jenkins 共享 Jenkins 容器的工作空间
// docker run 通过 /var/run/docker.sock 在宿主机执行

pipeline {
    agent any

    environment {
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        WS = '/var/jenkins_home/workspace/cky-claw'
    }

    stages {
        stage('Lint') {
            parallel {
                stage('Framework Lint') {
                    steps {
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/ckyclaw-framework python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
                            uv sync --extra dev 2>/dev/null
                            uv run ruff check .
                            uv run ruff format --check .
                        ' '''
                    }
                }
                stage('Backend Lint') {
                    steps {
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/backend python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
                            uv sync --extra dev 2>/dev/null
                            uv run ruff check .
                            uv run ruff format --check .
                        ' '''
                    }
                }
                stage('Frontend Lint') {
                    steps {
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/frontend node:20-alpine sh -c '
                            corepack enable && corepack prepare pnpm@latest --activate
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
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/ckyclaw-framework python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
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
                        sh '''docker run --rm --network host --volumes-from jenkins -w ${WS}/backend python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
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
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/frontend node:20-alpine sh -c '
                            corepack enable && corepack prepare pnpm@latest --activate
                            pnpm install --frozen-lockfile
                            pnpm test -- --run
                        ' '''
                    }
                }
            }
        }

        stage('Frontend Build') {
            steps {
                sh '''docker run --rm --volumes-from jenkins -w ${WS}/frontend node:20-alpine sh -c '
                    corepack enable && corepack prepare pnpm@latest --activate
                    pnpm install --frozen-lockfile
                    pnpm build
                ' '''
            }
        }

        stage('Docker Build') {
            steps {
                sh """
                    docker build -t ckyclaw-backend:\${IMAGE_TAG} -t ckyclaw-backend:latest \
                        -f \${WS}/backend/Dockerfile \${WS}
                    docker build -t ckyclaw-frontend:\${IMAGE_TAG} -t ckyclaw-frontend:latest \
                        -f \${WS}/frontend/Dockerfile \${WS}/frontend/
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
