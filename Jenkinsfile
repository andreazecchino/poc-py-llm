pipeline {
    agent any
    stages {
        stage('Lint & Unit tests') {
            agent {
                docker {
                    image 'ghcr.io/astral-sh/uv:python3.14-trixie-slim'
                    args '''
                        -u 0:0
                        -v uv-cache:/tmp/uv-cache
                        -v uv-tools:/tmp/uv-tools
                    '''
                    reuseNode true
                }
            }
            environment {
                UV_CACHE_DIR = "/tmp/uv-cache"
                UV_TOOL_DIR = "/tmp/uv-tools"
            }
            steps {
                sh 'uv sync --locked'
                sh 'uv run ruff check .'
                sh 'uv run ruff format --check .'
                sh 'uv run python -m unittest discover -s tests -p "test_*.py" -v'
            }
        }
        stage('Security Scan') {
            agent {
                docker {
                    image 'aquasec/trivy:0.76.1'
                    args '''
                        -u 0:0
                        -v trivy-cache:/tmp/trivy-cache
                        --entrypoint=""
                    '''
                    reuseNode true
                }
            }
            environment {
                TRIVY_CACHE_DIR = "/tmp/trivy-cache"
            }
            steps {
                sh '''
                    trivy fs \
                      --cache-dir "$TRIVY_CACHE_DIR" \
                      --severity HIGH,CRITICAL \
                      --scanners vuln,secret,misconfig \
                      --ignore-unfixed \
                      --exit-code 1 \
                      --format json \
                      --output trivy-fs-report.json \
                      "$WORKSPACE"
                '''
            }
        }
        stage('Build & Verify Docker Image') {
            steps {
                script {
                    def img = docker.build("poc-py-llm:${env.BUILD_ID}")
                    img.inside {
                        sh 'python -c "import sys; print(sys.version); print(\'smoke test ok\')"'
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts allowEmptyArchive: true, artifacts: 'trivy-*.json', fingerprint: true, followSymlinks: false
            cleanWs(
                deleteDirs: true,
                notFailBuild: true,
                patterns: [
                    [pattern: 'trivy-*.json', type: 'EXCLUDE'],
                ]
            )
        }
    }
}
