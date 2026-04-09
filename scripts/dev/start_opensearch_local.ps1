$container = "dalil-opensearch"
$existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $container }
if (-not $existing) {
  docker run -d --name $container `
    -p 9200:9200 -p 9600:9600 `
    -e "discovery.type=single-node" `
    -e "plugins.security.disabled=true" `
    -e "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" `
    opensearchproject/opensearch:2.14.0 | Out-Null
} else {
  docker start $container | Out-Null
}
Write-Host "OpenSearch should be available at http://localhost:9200"
Write-Host 'Set env vars:'
Write-Host '$env:OPENSEARCH_URL = "http://localhost:9200"'
Write-Host '$env:OPENSEARCH_USERNAME = "admin"'
Write-Host '$env:OPENSEARCH_PASSWORD = "admin"'
Write-Host '$env:OPENSEARCH_VERIFY_SSL = "false"'
