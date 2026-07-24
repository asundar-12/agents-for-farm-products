#!/usr/bin/env bash
# Deploy the agent runtime to Bedrock AgentCore.
#
# Why this wrapper exists: .dockerignore excludes .env, so secrets are NOT baked
# into the container image. They have to be passed at launch time via --env, or
# the container fails on startup with a pydantic ValidationError for the missing
# required Settings (DATABASE_URL, JWT_SECRET). This script reads each value
# from .env via command substitution so the values are passed to agentcore
# without being echoed to the terminal — only the key names are ever printed.
#
# Usage:  ./deploy.sh
# Requires: AWS_PROFILE set (defaults to Arjun), .env present.

set -euo pipefail

cd "$(dirname "$0")"

export AWS_PROFILE="${AWS_PROFILE:-Arjun}"

if [[ ! -f .env ]]; then
  echo "error: .env not found in $(pwd)" >&2
  exit 1
fi

# Pull one value from .env by key, without printing it. cut -d= -f2- keeps
# everything after the first '=', so values containing '=' (e.g. a DB URL with
# query params) survive intact.
get() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }

# Keys the container needs at runtime. DATABASE_URL and JWT_SECRET are required
# by Settings; AGENT_MEMORY_ID is required by the AgentCore memory session
# manager; the rest override Settings defaults with the real deployed values.
KEYS=(DATABASE_URL JWT_SECRET AGENT_MEMORY_ID AGENT_RUNTIME_ARN AWS_REGION BEDROCK_MODEL_ID)

env_args=()
for key in "${KEYS[@]}"; do
  value="$(get "$key")"
  if [[ -z "$value" ]]; then
    echo "warning: $key is empty or missing in .env — skipping" >&2
    continue
  fi
  env_args+=(--env "$key=$value")
  echo "  passing $key" # name only, never the value
done

echo "Launching with AWS_PROFILE=$AWS_PROFILE ..."
agentcore launch "${env_args[@]}"
