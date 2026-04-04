// CkyClaw Jenkins Pipeline（Docker Agent 模式）
// 前置要求：
//   - Jenkins 插件: Pipeline, Docker Pipeline, Git, Credentials
//   - Jenkins 容器挂载 /var/run/docker.sock
//   - 无需在 Jenkins 内安装 uv/pnpm/node/python，每个阶段用专用 Docker 镜像
// 触发方式: SCM Polling 或 Webhook

pipeline {
    // 顶层 agent none，每个 stage 自行指定
    agent none

    environment {
        // 宿主机上已有 docker-registry 服务，按实际地址修改
        DOCKER_REGISTRY = 'localhost:5000'
        IMAGE_TAG       = "${env.BUILD_NUMBER}"
        // pip/uv 缓存挂载卷，加速重复构建
        PIP_CACHE       = '/tmp/pip-cache'
        PNPM_STORE      = '/tmp/pnpm-store'
    }

    stages {
        // ── 1. 代码检出（在 Jenkins 主容器执行） ──
        stage('Checkout') {
            agent any
            steps {
                checkout scm
                stash name: 'source', includes: '**'
            }
        }

        // ── 2. 并行 Lint & 测试 ──
        stage('Lint & Test') {
            parallel {
                // ── 2a. Framework Lint ──
                stage('Framework Lint') {
                    agent {
                        docker {
                            image 'python:3.12-slim'
                            args '-v $PIP_CACHE:/root/.cache/pip -v uv-cache:/root/.cache/uv'
                        }
                    }
                    steps {
                        unstash 'source'
                        sh '''
                            pip install uv 2>/dev/null
                            cd ckyclaw-framework
                            uv sync --extra dev
                            uv run ruff check .
                            uv run ruff format --check .
                        '''
                    }
                }

                // ── 2b. Backend Lint ──
                stage('Backend Lint') {
                    agent {
                        docker {
                            image 'python:3.12-slim'
                            args '-v $PIP_CACHE:/root/.cache/pip -v uv-cache:/root/.cache/uv'
                        }
                    }
                    steps {
                        unstash 'source'
                        sh '''
                            pip install uv 2>/dev/null
                            cd backend
                            uv sync --extra dev
                            uv run ruff check .
                            uv run ruff format --check .
                        '''
                    }
                }

                // ── 2c. Frontend Lint & Type Check ──
                stage('Frontend Lint') {
                    agent {
                        docker {
                            image 'node:20-alpine'
                            args '-v $PNPM_STORE:/root/.local/share/pnpm/store'
                        }
                    }
                    steps {
                        unstash 'source'
                        sh '''
                            corepack enable && corepack prepare pnpm@latest --activate
                            cd frontend
                            pnpm install --frozen-lockfile
                            pnpm lint
                            npx tsc --noEmit
                        '''
                    }
                }

                // ── 2d. Framework 单元测试 ──
                stage('Framework Test') {
                    agent {
                        docker {
                            image 'python:3.12-slim'
                            args '-v $PIP_CACHE:/root/.cache/pip -v uv-cache:/root/.cache/uv'
                        }
                    }
                    steps {
                        unstash 'source'
                        sh '''
                            pip install uv 2>/dev/null
                            cd ckyclaw-framework
                            uv sync --extra dev
                            uv run pytest tests/ \
                                --ignore=tests/test_integration.py \
                                --ignore=tests/test_e2e_integration.py \
                                --ignore=tests/test_e2e_phase69.py \
                                --ignore=tests/test_mcp_integration.py \
                                -q --tb=short
                        '''
                    }
                }

                // ── 2e. Backend 单元测试 ──
                stage('Backend Test') {
                    agent {
                        docker {
                            image 'python:3.12-slim'
                            // 用 --network host 连接宿主机已有的 PostgreSQL
                            args '--network host -v $PIP_CACHE:/root/.cache/pip -v uv-cache:/root/.cache/uv'
                        }
                    }
                    steps {
                        unstash 'source'
                        sh '''
                            pip install uv 2>/dev/null
                            # 等待宿主机 PostgreSQL 就绪（容器共享宿主机网络）
                            for i in $(seq 1 30); do
                                python3 -c "
import socket, sys
s = socket.socket()
try:
    s.connect(('127.0.0.1', 5432))
    print('PostgreSQL ready')
    sys.exit(0)
except:
    sys.exit(1)
" && break
                                sleep 1
                            done
                            cd backend
                            uv sync --extra dev
                            CKYCLAW_DATABASE_URL=postgresql+asyncpg://ckyclaw:ckyclaw_dev@127.0.0.1:5432/ckyclaw \
                            uv run pytest tests/ \
                                --ignore=tests/test_smoke.py \
                                --ignore=tests/test_performance.py \
                                --ignore=tests/test_e2e_backend.py \
                                --ignore=tests/test_mcp_integration.py \
                                -q --tb=short
                        '''
                    }
                }

                // ── 2f. Frontend 单元测试 ──
                stage('Frontend Test') {
                    agent {
                        docker {
                            image 'node:20-alpine'
                            args '-v $PNPM_STORE:/root/.local/share/pnpm/store'
                        }
                    }
                    steps {
                        unstash 'source'
                        sh '''
                            corepack enable && corepack prepare pnpm@latest --activate
                            cd frontend
                            pnpm install --frozen-lockfile
                            pnpm test -- --run
                        '''
                    }
                }
            }
        }

        // ── 3. 构建前端产物 ──
        stage('Frontend Build') {
            agent {
                docker {
                    image 'node:20-alpine'
                    args '-v $PNPM_STORE:/root/.local/share/pnpm/store'
                }
            }
            steps {
                unstash 'source'
                sh '''
                    corepack enable && corepack prepare pnpm@latest --activate
                    cd frontend
                    pnpm install --frozen-lockfile
                    pnpm build
                '''
            }
            post {
                success {
                    archiveArtifacts artifacts: 'frontend/dist/**', fingerprint: true, allowEmptyArchive: true
                }
            }
        }

        // ── 4. 构建 Docker 镜像（在 Jenkins 主容器，通过 socket 调用宿主机 Docker） ──
        stage('Docker Build') {
            agent any
            steps {
                unstash 'source'
                sh '''
                    docker build -t ckyclaw-backend:${IMAGE_TAG} -t ckyclaw-backend:latest \
                        -f backend/Dockerfile .
                    docker build -t ckyclaw-frontend:${IMAGE_TAG} -t ckyclaw-frontend:latest \
                        -f frontend/Dockerfile frontend/
                '''
            }
        }

        // ── 5. 推送镜像到私有仓库（仅 main/develop） ──
        stage('Docker Push') {
            agent any
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            steps {
                script {
                    def tag = env.BRANCH_NAME == 'main' ? 'latest' : env.BRANCH_NAME
                    sh """
                        docker tag ckyclaw-backend:${IMAGE_TAG} ${DOCKER_REGISTRY}/ckyclaw-backend:${tag}
                        docker tag ckyclaw-backend:${IMAGE_TAG} ${DOCKER_REGISTRY}/ckyclaw-backend:${IMAGE_TAG}
                        docker tag ckyclaw-frontend:${IMAGE_TAG} ${DOCKER_REGISTRY}/ckyclaw-frontend:${tag}
                        docker tag ckyclaw-frontend:${IMAGE_TAG} ${DOCKER_REGISTRY}/ckyclaw-frontend:${IMAGE_TAG}
                        docker push ${DOCKER_REGISTRY}/ckyclaw-backend:${tag}
                        docker push ${DOCKER_REGISTRY}/ckyclaw-backend:${IMAGE_TAG}
                        docker push ${DOCKER_REGISTRY}/ckyclaw-frontend:${tag}
                        docker push ${DOCKER_REGISTRY}/ckyclaw-frontend:${IMAGE_TAG}
                    """
                }
            }
        }

        // ── 6. 部署（仅 main 分支） ──
        stage('Deploy') {
            agent any
            when {
                branch 'main'
            }
            steps {
                echo 'TODO: 添加部署步骤，例如 SSH 到目标服务器执行 docker compose up'
            }
        }
    }

    post {
        failure {
            echo '构建失败，请检查上方日志定位问题'
        }
        success {
            echo "构建成功 #${env.BUILD_NUMBER}"
        }
        cleanup {
            // 清理本构建的临时容器，不影响其他服务
            sh 'docker system prune -f 2>/dev/null || true'
        }
    }
}
