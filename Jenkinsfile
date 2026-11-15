pipeline {
    agent any
    environment {
        REPOSITORY = 'https://github.com/andreazecchino/poc-py-llm'
        BRANCH = 'develop'
        REGISTRY = 'registry.local'
        IMAGE = 'poc-py-llm'
        REF = "${REGISTRY}/${IMAGE}"
    }
    options {
        buildDiscarder logRotator(
            artifactDaysToKeepStr: '',
            artifactNumToKeepStr: '3',
            daysToKeepStr: '',
            numToKeepStr: '3')
        disableConcurrentBuilds abortPrevious: true
        disableResume()
        timeout(time: 30, unit: 'MINUTES')
    }
    stages {
        stage('Checkout SCM') {
            steps {
                checkout scmGit(
                    branches: [[name: "$BRANCH"]],
                    extensions: [],
                    userRemoteConfigs: [[url: "$REPOSITORY"]]
                )
                script {
                    env.TAG = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                }
            }
        }
        stage('Lint & Unit tests') {
            agent {
                docker {
                    image 'ghcr.io/astral-sh/uv:python3.14-trixie-slim'
                    reuseNode true
                }
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
        stage('Security Scan: Filesystem') {
            agent {
                docker {
                    image 'aquasec/trivy:0.76.1'
                    args '--entrypoint=""'
                    reuseNode true
                }
            }
            environment {
                TRIVY_CACHE_DIR = "${env.WORKSPACE}/.trivy-cache"
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
        stage('Build Docker Image') {
            steps {
                script {
                    docker.build("${REF}:${TAG}")
                    sh 'docker image save -o image.tar "${REF}:${TAG}"'
                }
            }
        }
        stage('Smoke Test') {
            steps {
                script {
                    docker.image("${REF}:${TAG}").inside {
                        sh 'python -c "import sys; print(sys.version)"'
                    }
                }
            }
        }
        stage('Security Scan: Image') {
            agent {
                docker {
                    image 'aquasec/trivy:0.76.1'
                    args '--entrypoint=""'
                    reuseNode true
                }
            }
            environment {
                TRIVY_CACHE_DIR = "${env.WORKSPACE}/.trivy-cache"
            }
            steps {
                sh '''
                    trivy image \
                      --input image.tar \
                      --cache-dir "$TRIVY_CACHE_DIR" \
                      --severity HIGH,CRITICAL \
                      --scanners vuln,secret,misconfig \
                      --format json \
                      --output trivy-image-report.json \
                      --ignore-unfixed
                '''
            }
        }
        stage('Push Docker Image') {
            steps {
                script {
                    def img = docker.image("${REF}:${TAG}")
                    docker.withRegistry("https://${REGISTRY}") {
                        img.push("${env.BUILD_ID}")
                        img.push("${TAG}")
                        img.push('latest')
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
                    [pattern: '.trivy-cache/', type: 'EXCLUDE'],
                    [pattern: '.uv-cache/', type: 'EXCLUDE'],
                    [pattern: '.uv-tools/', type: 'EXCLUDE'],
                ]
            )
            sh returnStatus: true, script: """
                docker image rm -f ${REF}:latest || true
                docker image rm -f ${REF}:${TAG} || true
                docker image rm -f ${REF}:${env.BUILD_ID} || true
            """
        }
    }
}
