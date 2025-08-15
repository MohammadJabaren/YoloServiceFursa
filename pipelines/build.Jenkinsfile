pipeline {
    agent {
        label 'general'
    }

    triggers {
        githubPush()
    }

    environment {
        DOCKER_USERNAME = credentials('dockerhub-username') // ID from Jenkins credentials
        DOCKER_PASSWORD = credentials('dockerhub-token')     // ID from Jenkins credentials
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Login to DockerHub') {
            steps {
                sh '''
                    echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
                '''
            }
        }

        stage('Build & Push Image') {
            steps {
                script {
                    def tag = "${DOCKER_USERNAME}/yolo-prod:${BUILD_NUMBER}"
                    env.IMAGE_TAG = tag
                    sh """
                        docker build -t $IMAGE_TAG .
                        docker push $IMAGE_TAG
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Docker image pushed: ${env.IMAGE_TAG}"
        }
        failure {
            echo "❌ Build failed"
        }
    }
}
