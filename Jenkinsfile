pipeline {
    agent any
    stages {
        stage('Lint & Unit tests') {
            agent {
                docker { image 'ghcr.io/astral-sh/uv:python3.14-trixie-slim' }
            }
            environment {
                UV_CACHE_DIR = "${env.WORKSPACE}/.uv-cache"
                UV_TOOL_DIR = "${env.WORKSPACE}/.uv-tools"
            }
            steps {
                sh 'uv sync --locked'
                sh 'uv run ruff check .'
                sh 'uv run ruff format --check .'
                sh 'uv run python -m unittest discover -s tests -p "test_*.py" -v'
            }
        }
        stage('Build and Verify Docker Image') {
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
            cleanWs(
                deleteDirs: true,
                notFailBuild: true,
                patterns: [
                    [pattern: '.uv-cache', type: 'EXCLUDE'],
                    [pattern: '.uv-tools', type: 'EXCLUDE']
                ]
            )
        }
    }
}
