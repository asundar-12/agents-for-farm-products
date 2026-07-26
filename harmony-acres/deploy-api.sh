#!/usr/bin/env bash
# Build the FastAPI backend image and push it to ECR. AWS App Runner is then
# pointed at this ECR repo (once, in the console) and redeploys automatically
# whenever a new image lands on the tag it watches.
#
# Usage:  ./deploy-api.sh
# Requires: AWS_PROFILE set (defaults to Arjun), Docker running.
#
# First-time setup (do these once, by hand):
#   1. Create the ECR repo:
#        aws ecr create-repository --repository-name harmony-acres-api
#   2. Create an App Runner service from that ECR image (console is easiest):
#        - Port 8000, health check path /health
#        - Environment variables: DATABASE_URL, AUTH_MODE=cognito,
#          COGNITO_REGION, COGNITO_USER_POOL_ID, COGNITO_APP_CLIENT_ID,
#          CORS_ALLOW_ORIGINS=<your amplify domain>, plus the AGENT_* vars.
#        - Turn ON "automatic deployments" so pushes here roll out.

set -euo pipefail
cd "$(dirname "$0")"

export AWS_PROFILE="${AWS_PROFILE:-Arjun}"
REGION="${AWS_REGION:-us-east-1}"
REPO="harmony-acres-api"
TAG="latest"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REGISTRY}/${REPO}:${TAG}"

echo "Logging in to ECR (${REGISTRY}) ..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "Building image for linux/amd64 (App Runner runs amd64) ..."
docker build --platform linux/amd64 -f Dockerfile.api -t "$IMAGE" .

echo "Pushing ${IMAGE} ..."
docker push "$IMAGE"

echo "Done. If App Runner auto-deploy is on, the rollout starts now."
