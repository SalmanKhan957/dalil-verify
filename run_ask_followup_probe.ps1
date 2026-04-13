param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$CasesFile = ".\ask_followup_probe_cases.json",
  [string]$OutFile = ".\ask_followup_probe_results.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $CasesFile)) {
  throw "Cases file not found: $CasesFile"
}

$cases = Get-Content $CasesFile -Raw | ConvertFrom-Json
$allResults = @()

foreach ($chain in $cases.chains) {
  $conversationId = "probe-" + $chain.chain_id + "-" + ([guid]::NewGuid().ToString("N").Substring(0, 8))
  $stepResults = @()

  Write-Host ""
  Write-Host "Running chain:" $chain.chain_id " | conversation_id:" $conversationId -ForegroundColor Cyan
  Write-Host "Purpose:" $chain.purpose -ForegroundColor DarkCyan

  for ($i = 0; $i -lt $chain.steps.Count; $i++) {
    $step = $chain.steps[$i]
    $payload = @{ query = $step.query } | ConvertTo-Json -Depth 10
    $headers = @{
      "Content-Type" = "application/json"
      "x-conversation-id" = $conversationId
    }

    try {
      $response = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd('/') + "/ask") -Method Post -Headers $headers -Body $payload
      $result = if ($null -ne $response.result) { $response.result } else { $response }

      $resolvedCanonical = $null
      if ($null -ne $result.resolution) {
        $resolvedCanonical = $result.resolution.canonical_source_id
        if (-not $resolvedCanonical) {
          $resolvedCanonical = $result.resolution.canonical_ref
        }
      }

      $activeFollowupAction = $null
      if ($null -ne $result.composition -and $null -ne $result.composition.active_followup_action) {
        $activeFollowupAction = $result.composition.active_followup_action
      }

      $citations = @()
      if ($null -ne $result.citations) {
        foreach ($c in $result.citations) {
          if ($null -ne $c.canonical_ref) {
            $citations += $c.canonical_ref
          } elseif ($null -ne $c.citation_text) {
            $citations += $c.citation_text
          }
        }
      }

      $preview = $null
      if ($null -ne $result.answer_text) {
        $txt = [string]$result.answer_text
        if ($txt.Length -gt 280) { $preview = $txt.Substring(0, 280) + "..." } else { $preview = $txt }
      }

      $stepResult = [ordered]@{
        chain_id = $chain.chain_id
        purpose = $chain.purpose
        step_index = $i + 1
        conversation_id = $conversationId
        query = $step.query
        route_type = $result.route_type
        action_type = $result.action_type
        answer_mode = $result.answer_mode
        terminal_state = $result.terminal_state
        resolved_ref = $resolvedCanonical
        active_followup_action = $activeFollowupAction
        followup_ready = if ($null -ne $result.conversation) { $result.conversation.followup_ready } else { $null }
        abstention_reason = if ($null -ne $result.composition -and $null -ne $result.composition.abstention) { $result.composition.abstention.reason_code } else { $null }
        citations = $citations
        answer_text_preview = $preview
      }

      $stepResults += [pscustomobject]$stepResult
      Write-Host ("  [{0}] {1}" -f ($i + 1), $step.query) -ForegroundColor Yellow
      Write-Host ("      route={0} | action={1} | mode={2} | terminal={3} | resolved={4}" -f `
        $stepResult.route_type, $stepResult.action_type, $stepResult.answer_mode, $stepResult.terminal_state, $stepResult.resolved_ref)
    }
    catch {
      $stepResult = [ordered]@{
        chain_id = $chain.chain_id
        purpose = $chain.purpose
        step_index = $i + 1
        conversation_id = $conversationId
        query = $step.query
        route_type = $null
        action_type = $null
        answer_mode = $null
        terminal_state = "error"
        resolved_ref = $null
        active_followup_action = $null
        followup_ready = $null
        abstention_reason = "request_failed"
        citations = @()
        answer_text_preview = $_.Exception.Message
      }
      $stepResults += [pscustomobject]$stepResult
      Write-Host ("  [{0}] {1}" -f ($i + 1), $step.query) -ForegroundColor Red
      Write-Host ("      ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
    }
  }

  $allResults += [pscustomobject]@{
    chain_id = $chain.chain_id
    purpose = $chain.purpose
    conversation_id = $conversationId
    steps = $stepResults
  }
}

$output = [ordered]@{
  suite_id = $cases.suite_id
  generated_at_utc = (Get-Date).ToUniversalTime().ToString("s") + "Z"
  base_url = $BaseUrl
  chains = $allResults
}

$output | ConvertTo-Json -Depth 20 | Set-Content -Path $OutFile -Encoding UTF8
Write-Host ""
Write-Host "Wrote probe results -> $OutFile" -ForegroundColor Green
