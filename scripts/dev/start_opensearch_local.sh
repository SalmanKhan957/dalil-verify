#!/usr/bin/env bash
set -euo pipefail
container="dalil-opensearch"
if ! docker ps -a --format '{{.Names}}' | grep -qx "$container"; then
  docker run -d --name "$container" \
    -p 9200:9200 -p 9600:9600 \
    -e discovery.type=single-node \
    -e plugins.security.disabled=true \
    -e OPENSEARCH_JAVA_OPTS='-Xms512m -Xmx512m' \
    opensearchproject/opensearch:2.14.0 >/dev/null
else
  docker start "$container" >/dev/null
fi
printf 'OpenSearch should be available at http://localhost:9200\n'
printf 'Export env vars before push/search:\n'
printf 'export OPENSEARCH_URL=http://localhost:9200\n'
printf 'export OPENSEARCH_USERNAME=admin\n'
printf 'export OPENSEARCH_PASSWORD=admin\n'
printf 'export OPENSEARCH_VERIFY_SSL=false\n'
