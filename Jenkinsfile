// Kasaya Jenkins Pipeline
// 使用 --volumes-from jenkins 共享 Jenkins 容器的工作空间

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
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/kasaya python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
                            uv sync --extra dev
                            . .venv/bin/activate
                            ruff check .
                            ruff format --check .
                        ' '''
                    }
                }
                stage('Backend Lint') {
                    steps {
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/backend python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
                            uv sync --extra dev
                            . .venv/bin/activate
                            ruff check .
                            ruff format --check .
                        ' '''
                    }
                }
                stage('Frontend Lint') {
                    steps {
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/frontend node:20-alpine sh -c '
                            corepack enable && corepack prepare pnpm@latest --activate
                            pnpm install --frozen-lockfile
                            pnpm lint 2>&1 || true
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
                        sh '''docker run --rm --volumes-from jenkins -w ${WS}/kasaya python:3.12-slim bash -c '
                            pip install -q uv 2>/dev/null
                            uv sync --extra dev
                            . .venv/bin/activate
                            pytest tests/ \
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
                            uv sync --extra dev
                            . .venv/bin/activate
                            KASAYA_DATABASE_URL=postgresql+asyncpg://admin:Admin888@127.0.0.1:15432/kasaya \
                            pytest tests/ \
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
                    docker build -t kasaya-backend:\${IMAGE_TAG} -t kasaya-backend:latest \
                        -f \${WS}/backend/Dockerfile \${WS}
                    docker build -t kasaya-frontend:\${IMAGE_TAG} -t kasaya-frontend:latest \
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
