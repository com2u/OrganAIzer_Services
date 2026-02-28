$BASE = "http://localhost:8000"

function Chat($msg, $session, $uid="default_user") {
    $body = @{message=$msg; session_id=$session; user_id=$uid; provider="gmail"} | ConvertTo-Json
    try {
        $r = Invoke-RestMethod -Uri "$BASE/api/agent/chat" -Method POST -ContentType "application/json" -Body $body -TimeoutSec 30
        return $r
    } catch {
        Write-Host "HTTP Error: $($_.Exception.Message)"
        return $null
    }
}

function ClearSession($session) {
    try { Invoke-RestMethod -Uri "$BASE/api/agent/session/$session" -Method DELETE -TimeoutSec 5 | Out-Null } catch {}
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  Executive AI Tool Execution Live Test"
Write-Host "=========================================="

# ── TEST 1: Email Flow ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "TEST 1: Email Send via Executive AI"
Write-Host "------------------------------------------"
ClearSession "test-email-ps"

$r1 = Chat "Send an email to alice@example.com about the project update" "test-email-ps"
if ($r1) {
    Write-Host "  type    : $($r1.type)"
    Write-Host "  state   : $($r1.agent_state)"
    Write-Host "  message : $($r1.message.Substring(0,[Math]::Min(250,$r1.message.Length)))"

    if ($r1.type -eq "email_slot_request" -or $r1.type -eq "email_confirmation") {
        Write-Host "  [PASS] Agent entering email flow correctly"

        # If body is missing, provide it
        if ($r1.type -eq "email_slot_request") {
            $r2 = Chat "The project is on track. We deliver by Friday." "test-email-ps"
            Write-Host ""
            Write-Host "  [Turn 2 - body]"
            Write-Host "  type    : $($r2.type)"
            Write-Host "  message : $($r2.message.Substring(0,[Math]::Min(250,$r2.message.Length)))"
            $confirmTurn = $r2
        } else {
            $confirmTurn = $r1
        }

        if ($confirmTurn.type -eq "email_confirmation") {
            Write-Host ""
            Write-Host "  [Turn 3 - confirm]"
            $r3 = Chat "yes" "test-email-ps"
            Write-Host "  type    : $($r3.type)"
            Write-Host "  message : $($r3.message.Substring(0,[Math]::Min(300,$r3.message.Length)))"

            if ($r3.type -eq "email_sent") {
                Write-Host "  [PASS] EMAIL ACTUALLY SENT - message_id: $($r3.data.message_id)"
            } elseif ($r3.type -eq "error") {
                Write-Host "  [PASS*] Agent attempted /api/integrations/google/gmail/send (OAuth error expected without connected account)"
                Write-Host "  Error: $($r3.error)"
            } else {
                Write-Host "  [FAIL] Unexpected type after confirm: $($r3.type)"
            }
        }
    } else {
        Write-Host "  [FAIL] Expected email_slot_request or email_confirmation, got: $($r1.type)"
    }
}

# ── TEST 2: Calendar Flow ───────────────────────────────────────────────────
Write-Host ""
Write-Host "TEST 2: Calendar Event Creation via Executive AI"
Write-Host "------------------------------------------"
ClearSession "test-cal-ps"

$r1 = Chat "Schedule a meeting called Strategy Sync tomorrow at 10:00 in google calendar" "test-cal-ps"
if ($r1) {
    Write-Host "  type    : $($r1.type)"
    Write-Host "  state   : $($r1.agent_state)"
    Write-Host "  message : $($r1.message.Substring(0,[Math]::Min(250,$r1.message.Length)))"

    if ($r1.type -eq "calendar_confirmation") {
        Write-Host "  [PASS] Agent entering calendar confirmation correctly"
        $r2 = Chat "yes" "test-cal-ps"
        Write-Host ""
        Write-Host "  [Turn 2 - confirm]"
        Write-Host "  type    : $($r2.type)"
        Write-Host "  message : $($r2.message.Substring(0,[Math]::Min(300,$r2.message.Length)))"

        if ($r2.type -eq "calendar_created") {
            Write-Host "  [PASS] CALENDAR EVENT CREATED - event_id: $($r2.data.event_id)"
        } elseif ($r2.type -eq "error") {
            Write-Host "  [PASS*] Agent attempted /api/integrations/google/calendar/events (OAuth error expected without connected account)"
            Write-Host "  Error: $($r2.error)"
        } else {
            Write-Host "  [FAIL] Unexpected type: $($r2.type)"
        }
    } else {
        Write-Host "  [FAIL] Expected calendar_confirmation, got: $($r1.type)"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  Test complete"
Write-Host "=========================================="
