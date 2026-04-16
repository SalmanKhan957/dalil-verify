param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$OutputDir = ".\dalil_manual_test_output",
    [switch]$DebugRequests,
    [switch]$IncludeNegative,
    [switch]$UseSharedConversationForFollowups
)

$ErrorActionPreference = "Stop"

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Safe-FileName {
    param([string]$Value)
    $name = $Value -replace '[^a-zA-Z0-9._-]+', '_'
    return $name.Trim('_')
}

function Build-Uri {
    param([string]$Base)

    if (-not $Base) {
        throw "BaseUrl is empty or null"
    }

    # Strip any accidental literal quotes, spaces, and trailing slashes
    $clean = $Base.Replace('"', '').Replace("'", "").Trim().TrimEnd('/')
    
    return "$clean/ask"
}

function Invoke-DalilAsk {
    param(
        [string]$Query,
        [string]$ConversationId,
        [string]$ParentTurnId,
        [bool]$DebugMode
    )

    $payload = @{ query = $Query }
    if ($ConversationId) { $payload.conversation_id = $ConversationId }
    if ($ParentTurnId) { $payload.parent_turn_id = $ParentTurnId }
    if ($DebugMode) { $payload.debug = $true }

    $json = $payload | ConvertTo-Json -Depth 20

    $uri = Build-Uri -Base $BaseUrl

    $response = Invoke-WebRequest `
        -Uri $uri `
        -Method Post `
        -ContentType "application/json" `
        -Body $json `
        -UseBasicParsing

    $requestId = $null
    if ($response.Headers["X-Dalil-Request-Id"]) {
        $requestId = $response.Headers["X-Dalil-Request-Id"]
    }

    # FIX: Removed -Depth parameter from ConvertFrom-Json for PS 5.1 compatibility
    $body = $response.Content | ConvertFrom-Json

    return [PSCustomObject]@{
        status_code = [int]$response.StatusCode
        request_id = $requestId
        json = $body
        raw = $response.Content
    }
}

function Write-JsonFile {
    param([string]$Path, $Object)
    $Object | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Summarize-Response {
    param($Response)

    $routeType = $Response.json.route_type
    $actionType = $Response.json.action_type
    $answerMode = $Response.json.answer_mode
    $terminalState = $Response.json.terminal_state
    $requestId = $Response.request_id

    $answerText = $null
    if ($Response.json.answer_text) {
        $answerText = [string]$Response.json.answer_text
        if ($answerText.Length -gt 220) {
            $answerText = $answerText.Substring(0, 220) + "..."
        }
    }

    $normBackend = $null
    $normChanged = $null
    $normUsedHosted = $null

    if ($Response.json.route -and $Response.json.route.query_normalization) {
        $normBackend = $Response.json.route.query_normalization.backend
        $normChanged = $Response.json.route.query_normalization.changed
        $normUsedHosted = $Response.json.route.query_normalization.used_hosted_model
    }

    return [PSCustomObject]@{
        request_id = $requestId
        route_type = $routeType
        action_type = $actionType
        answer_mode = $answerMode
        terminal_state = $terminalState
        normalization_backend = $normBackend
        normalization_changed = $normChanged
        used_hosted_model = $normUsedHosted
        answer_preview = $answerText
    }
}

Ensure-Directory -Path $OutputDir
$rawDir = Join-Path $OutputDir "raw_json"
Ensure-Directory -Path $rawDir

$startedAt = Get-Date
$sharedConversationId = if ($UseSharedConversationForFollowups) { [guid]::NewGuid().ToString() } else { $null }

$tests = @(
    [PSCustomObject]@{ id="A1"; phase="explicit_quran"; query="2:255"; conversation=""; parent="" },
    [PSCustomObject]@{ id="A2"; phase="explicit_quran"; query="94:5-6"; conversation=""; parent="" },
    [PSCustomObject]@{ id="A3"; phase="explicit_quran"; query="Surah Ikhlas"; conversation=""; parent="" },
    [PSCustomObject]@{ id="B1"; phase="quran_tafsir"; query="Tafsir of Surah Ikhlas"; conversation=""; parent="" },
    [PSCustomObject]@{ id="B2"; phase="quran_tafsir"; query="Explain Ayat al-Kursi with tafsir"; conversation=""; parent="" },
    [PSCustomObject]@{ id="B3"; phase="quran_tafsir"; query="Explain Surah Al-Baqarah with tafsir"; conversation=""; parent="" },
    [PSCustomObject]@{ id="C1"; phase="messy_normalization"; query="Wht does IbnKathir sy about Surah al bqra?"; conversation=""; parent="" },
    [PSCustomObject]@{ id="C2"; phase="messy_normalization"; query="wht does ibnkathir say about surah al baqra"; conversation=""; parent="" },
    [PSCustomObject]@{ id="C3"; phase="messy_normalization"; query="Tafsir of Surah Ikhlas"; conversation=""; parent="" },
    [PSCustomObject]@{ id="C4"; phase="messy_normalization"; query="bukari 7277"; conversation=""; parent="" },
    [PSCustomObject]@{ id="C5"; phase="messy_normalization"; query="Bukhari20"; conversation=""; parent="" },
    [PSCustomObject]@{ id="E1"; phase="explicit_hadith"; query="Bukhari 20"; conversation=""; parent="" },
    [PSCustomObject]@{ id="E2"; phase="explicit_hadith"; query="Explain Bukhari 7"; conversation=""; parent="" },
    [PSCustomObject]@{ id="E3"; phase="explicit_hadith"; query="Bukhari 7277"; conversation=""; parent="" }
)

if ($IncludeNegative) {
    $tests += @(
        [PSCustomObject]@{ id="F1"; phase="negative"; query="What did the Prophet say about Dajjal?"; conversation=""; parent="" },
        [PSCustomObject]@{ id="F2"; phase="negative"; query="What does Islam say about anxiety?"; conversation=""; parent="" },
        [PSCustomObject]@{ id="F3"; phase="negative"; query="Give me a hadith about patience"; conversation=""; parent="" },
        [PSCustomObject]@{ id="F4"; phase="negative"; query="zzzz qqqq ibnkathir moon cow banana"; conversation=""; parent="" }
    )
}

# Follow-up sequence
$followConversationId = if ($UseSharedConversationForFollowups) { $sharedConversationId } else { [guid]::NewGuid().ToString() }
$tests += @(
    [PSCustomObject]@{ id="G0"; phase="followup"; query="Tafsir of Surah Ikhlas"; conversation=$followConversationId; parent="" },
    [PSCustomObject]@{ id="G1"; phase="followup"; query="simplify"; conversation=$followConversationId; parent="PREVIOUS" },
    [PSCustomObject]@{ id="G2-ROOT"; phase="followup"; query="Explain Bukhari 7"; conversation=$followConversationId; parent="" },
    [PSCustomObject]@{ id="G2"; phase="followup"; query="summarize this hadith"; conversation=$followConversationId; parent="PREVIOUS" },
    [PSCustomObject]@{ id="G3-ROOT"; phase="followup"; query="Tafsir of Surah Ikhlas"; conversation=$followConversationId; parent="" },
    [PSCustomObject]@{ id="G3"; phase="followup"; query="what does ibn kathir say?"; conversation=$followConversationId; parent="PREVIOUS" },
    [PSCustomObject]@{ id="G4-ROOT"; phase="followup"; query="Explain Ayat al-Kursi with tafsir"; conversation=$followConversationId; parent="" },
    [PSCustomObject]@{ id="G4"; phase="followup"; query="what about the next verse"; conversation=$followConversationId; parent="PREVIOUS" },
    [PSCustomObject]@{ id="G5"; phase="followup"; query="Wht does IbnKathir sy about Surah al bqra?"; conversation=$followConversationId; parent="" }
)

$results = @()
$previousTurnId = ""

foreach ($test in $tests) {
    $conversationId = $test.conversation
    $parentTurnId = if ($test.parent -eq "PREVIOUS") { $previousTurnId } else { $test.parent }

    Write-Host ("Running {0} [{1}] :: {2}" -f $test.id, $test.phase, $test.query) -ForegroundColor Cyan

    try {
        $response = Invoke-DalilAsk -Query $test.query -ConversationId $conversationId -ParentTurnId $parentTurnId -DebugMode:$DebugRequests.IsPresent
        $summary = Summarize-Response -Response $response

        $turnId = $null
        if ($response.json.conversation -and $response.json.conversation.turn_id) {
            $turnId = $response.json.conversation.turn_id
            $previousTurnId = $turnId
        }

        $record = [PSCustomObject]@{
            id = $test.id
            phase = $test.phase
            query = $test.query
            conversation_id = $conversationId
            parent_turn_id = $parentTurnId
            turn_id = $turnId
            status = "ok"
            status_code = $response.status_code
            request_id = $summary.request_id
            route_type = $summary.route_type
            action_type = $summary.action_type
            answer_mode = $summary.answer_mode
            terminal_state = $summary.terminal_state
            normalization_backend = $summary.normalization_backend
            normalization_changed = $summary.normalization_changed
            used_hosted_model = $summary.used_hosted_model
            answer_preview = $summary.answer_preview
            raw_file = (Join-Path "raw_json" ((Safe-FileName $test.id) + ".json"))
        }

        $rawPath = Join-Path $rawDir ((Safe-FileName $test.id) + ".json")
        Set-Content -LiteralPath $rawPath -Value $response.raw -Encoding UTF8
        $results += $record
    }
    catch {
        $results += [PSCustomObject]@{
            id = $test.id
            phase = $test.phase
            query = $test.query
            status = "error"
            answer_preview = $_.Exception.Message
        }
    }
}

$finishedAt = Get-Date

$summaryJson = [PSCustomObject]@{
    started_at = $startedAt.ToString("o")
    finished_at = $finishedAt.ToString("o")
    base_url = $BaseUrl
    results = $results
}

Write-JsonFile -Path (Join-Path $OutputDir "summary.json") -Object $summaryJson

Write-Host ""
Write-Host "Finished. Outputs written to: $OutputDir" -ForegroundColor Green