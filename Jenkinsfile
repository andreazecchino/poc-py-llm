pipeline {
    agent any

    stages {
        stage('Lint') {
            agent {
                docker { image 'ghcr.io/astral-sh/uv:python3.14-trixie-slim' }
            }
            steps {
                echo 'Linting..'
                // sh 'uv python install'
                sh 'uvx ruff check .'
                sh 'uvx ruff format --check .'
            }
        }
        stage('Test') {
            steps {
                echo 'Testing..'
            }
        }
        stage('Build') {
            steps {
                echo 'Building....'
            }
        }
    }
}
