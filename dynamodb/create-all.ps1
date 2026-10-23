$ErrorActionPreference = "Stop"
$endpoint = "http://localhost:8000"
$region = "us-east-1"
$files = @("create-users.json","create-events.json","create-alerts.json","create-audit-logs.json","create-simulations.json")
$env:AWS_ACCESS_KEY_ID = "local"
$env:AWS_SECRET_ACCESS_KEY = "local"
$env:AWS_DEFAULT_REGION = $region

foreach ($file in $files) {
    Write-Host "`nCreating table from $file ..." -ForegroundColor Cyan
    aws dynamodb create-table --cli-input-json "file://$file" --endpoint-url $endpoint --region $region
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI failed at $file. Inspect the error before rerunning." }
}
foreach ($name in @("Users","Events","Alerts","AuditLogs","Simulations")) {
    aws dynamodb wait table-exists --table-name $name --endpoint-url $endpoint --region $region
    if ($LASTEXITCODE -ne 0) { throw "Wait failed for $name." }
}
Write-Host "`nTables:" -ForegroundColor Green
aws dynamodb list-tables --endpoint-url $endpoint --region $region
if ($LASTEXITCODE -ne 0) { throw "Could not list tables." }
