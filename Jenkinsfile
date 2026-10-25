pipeline {
    agent any
    stages {
        stage('Lint') {
            agent {
                docker { image 'ghcr.io/astral-sh/uv:python3.14-trixie-slim' }
            }
            environment {
                UV_CACHE_DIR = "${env.WORKSPACE}/.uv-cache"
                UV_TOOL_DIR = "${env.WORKSPACE}/.uv-tools"
            }
            steps {
                echo 'Linting..'
                sh 'uvx ruff check .'
                sh 'uvx ruff format --check .'
            }
        }
        stage('Test') {
            agent {
                docker { image 'ghcr.io/astral-sh/uv:python3.14-trixie-slim' }
            }
            environment {
                UV_CACHE_DIR = "${env.WORKSPACE}/.uv-cache"
                UV_TOOL_DIR = "${env.WORKSPACE}/.uv-tools"
            }
            steps {
                echo 'Testing..'
                sh 'uv sync'
                sh 'uv run python -m unittest discover -s tests -p "test_*.py" -v'
            }
        }
        stage('Build') {
            steps {
                echo 'Building....'
            }
        }
    }
    post {
        always {
            cleanWs(
                deleteDirs: true,
                notFailBuild: true,
                patterns: [
                    [pattern: '.uv-cache', type: 'INCLUDE'],
                    [pattern: '.uv-tools', type: 'INCLUDE']
                ]
            )
        }
    }
}
