# Runs docs/compute_plan_v3.md end to end, unattended.
#
# Installed as a scheduled task so it survives the SSH session closing and a
# reboot.  Every runner in here is resumable -- completed runs are skipped on a
# second pass -- so re-entering the script after an interruption costs nothing
# and is the intended recovery path.
#
# The phase 1 gate is the one place this stops on purpose.  The re-run exists to
# correct a key-order defect, and the delivery layer is order-independent by
# construction, so if delivery moved the fix reached further than intended and
# nothing downstream should be built on it.
#
# ASCII only: PowerShell 5.1 reads this file as the system codepage, and Korean
# text in a UTF-8 file breaks the parser before the first line runs.

$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'

$Repo = 'C:\Users\dor12\2026_core'
$Log = Join-Path $Repo 'compute_plan.log'
$State = Join-Path $Repo 'compute_plan_state.json'
$Models = @('qwen2.5:3b', 'qwen2.5:7b', 'qwen3:8b', 'llama3.1:8b')
# Candidates for phase 3.  Only ones already pulled are attempted; the pilot
# gate decides which of those enter the study.
$Candidates = @('qwen3:14b', 'gemma2:9b', 'mistral-nemo:12b', 'llama3.2:3b')

Set-Location $Repo

function Say($msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  $line | Out-File -FilePath $Log -Append -Encoding utf8
}

function Load-State {
  if (Test-Path $State) { return (Get-Content $State -Raw | ConvertFrom-Json) }
  return [pscustomobject]@{ phase1 = $false; gate = $false; phase2 = $false; phase3 = $false }
}

function Save-State($s) {
  $s | ConvertTo-Json | Out-File -FilePath $State -Encoding utf8
}

function Slug($model) { return ($model -replace ':', '-') }

function Run-Count($dir) {
  $f = Join-Path $Repo (Join-Path $dir 'runs.jsonl')
  if (-not (Test-Path $f)) { return 0 }
  return (Get-Content $f | Measure-Object -Line).Lines
}

# A phase that produced nothing must never be recorded as finished.  The first
# unattended attempt ran as SYSTEM, where `python` is not on PATH, so every
# runner failed in milliseconds and the driver marched on to the gate with 31 of
# 688 runs in hand.  Checking the artifact -- not the exit code, not the absence
# of an exception -- is the only thing that would have caught it.
function Assert-Complete($dirs, $expected, $label) {
  $short = @()
  foreach ($d in $dirs) {
    $n = Run-Count $d
    if ($n -lt $expected) { $short += ("{0} has {1}/{2}" -f $d, $n, $expected) }
  }
  if ($short.Count -gt 0) {
    Say ("$label INCOMPLETE - " + ($short -join '; '))
    Say "$label not marked done; re-running the driver will resume it."
    return $false
  }
  return $true
}

# Resolve the interpreter rather than trusting PATH, and stop outright if it is
# missing: a driver that cannot run Python has nothing useful to do, and
# continuing would only manufacture empty phases.
$Python = (Get-Command python -EA SilentlyContinue).Source
if (-not $Python) {
  foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
                   "C:\Python311\python.exe", "C:\Program Files\Python311\python.exe")) {
    if (Test-Path $c) { $Python = $c; break }
  }
}
if (-not $Python) {
  Say "FATAL: python not found (PATH or known locations). Driver cannot run."
  exit 2
}
Say ("python: " + $Python)

function Publish($message) {
  # Results are the point of the run; getting them off this machine matters more
  # than a tidy history, so each phase lands as its own commit.
  git add experiments/ *.log compute_plan_state.json 2>$null | Out-Null
  $pending = git status --porcelain -- experiments compute_plan_state.json
  if (-not $pending) { Say "publish: nothing to commit"; return }
  git commit -q -m $message | Out-Null
  git pull -q --rebase origin master | Out-Null
  git push -q origin master | Out-Null
  Say ("publish: " + $message + " (push exit " + $LASTEXITCODE + ")")
}

$state = Load-State
Say "=== driver start (commit $(git rev-parse --short HEAD)) ==="

# --- Phase 1: re-run under the determinism fix, capturing outcome classes -----
if (-not $state.phase1) {
  Say "phase 1 start"
  foreach ($m in $Models) {
    $dir = "experiments/rerun-" + (Slug $m)
    Say "phase 1: $m -> $dir"
    & $Python run_experiment_v3.py --experiment-dir $dir --model $m --max-turns 4 `
      --git-commit (git rev-parse --short HEAD) | Out-File -FilePath $Log -Append -Encoding utf8
  }
  $dirs = $Models | ForEach-Object { "experiments/rerun-" + (Slug $_) }
  if (-not (Assert-Complete $dirs 172 "phase 1")) { exit 1 }
  $state.phase1 = $true; Save-State $state
  Publish "run: v3 re-run under determinism fix, with outcome classification"
  Say "phase 1 done"
}

# --- Gate: delivery layer must be unchanged ------------------------------------
if (-not $state.gate) {
  Say "gate: comparing delivery layer against the pre-registered run"
  $origArgs = @(); $rerunArgs = @()
  foreach ($m in $Models) {
    $origArgs += @('--original', ("experiments/main-" + (Slug $m)))
    $rerunArgs += @('--rerun', ("experiments/rerun-" + (Slug $m)))
  }
  & $Python verify_rerun_v3.py @origArgs @rerunArgs --out experiments/rerun_verification.json |
    Out-File -FilePath $Log -Append -Encoding utf8
  if ($LASTEXITCODE -ne 0) {
    Say "GATE FAILED - delivery layer moved. Stopping before phase 2."
    Publish "run: re-run verification FAILED - delivery layer moved"
    exit 1
  }
  $state.gate = $true; Save-State $state
  Say "gate passed"

  & $Python analysis_safe_failure_v3.py `
    ($Models | ForEach-Object { @('--experiment-dir', ("experiments/rerun-" + (Slug $_))) }) `
    | Out-File -FilePath $Log -Append -Encoding utf8
  Publish "analysis: safe-failure classification over the re-run"
}

# --- Phase 2: turn-budget sensitivity ------------------------------------------
if (-not $state.phase2) {
  Say "phase 2 start (max-turns 10)"
  foreach ($m in $Models) {
    $dir = "experiments/turns10-" + (Slug $m)
    Say "phase 2: $m -> $dir"
    & $Python run_experiment_v3.py --experiment-dir $dir --model $m --max-turns 10 `
      --git-commit (git rev-parse --short HEAD) | Out-File -FilePath $Log -Append -Encoding utf8
  }
  $dirs = $Models | ForEach-Object { "experiments/turns10-" + (Slug $_) }
  if (-not (Assert-Complete $dirs 172 "phase 2")) { exit 1 }
  $state.phase2 = $true; Save-State $state
  Publish "run: max_turns=10 sensitivity (exploratory, does not replace the pre-registered run)"
  Say "phase 2 done"
}

# --- Phase 3: more models, pilot first -----------------------------------------
if (-not $state.phase3) {
  Say "phase 3 start"
  $available = @()
  $installed = (ollama list) -join "`n"
  foreach ($c in $Candidates) {
    if ($installed -match [regex]::Escape($c)) { $available += $c }
    else { Say "phase 3: $c not installed, skipping" }
  }
  if ($available.Count -gt 0) {
    $pilotArgs = @()
    foreach ($c in $available) { $pilotArgs += @('--model', $c) }
    Say ("phase 3 pilot: " + ($available -join ', '))
    & $Python run_model_pilot_v3.py --experiment-dir experiments/pilot-round2 @pilotArgs |
      Out-File -FilePath $Log -Append -Encoding utf8
    Publish "run: pilot gate for additional models"

    # Only models the pilot admitted go into the study; the gate exists so that
    # "delivered nothing" cannot be format non-compliance wearing privacy's face.
    $passed = @()
    $pilotFile = 'experiments/pilot-round2/model_pilot.json'
    if (Test-Path $pilotFile) {
      $pilot = Get-Content $pilotFile -Raw | ConvertFrom-Json
      foreach ($p in $pilot.models.PSObject.Properties) {
        if ($p.Value.included -eq $true) { $passed += $p.Name }
      }
    } else {
      Say "phase 3: model_pilot.json missing - treating as no admissions"
    }
    Say ("phase 3 passed pilot: " + $(if ($passed) { $passed -join ', ' } else { 'none' }))
    foreach ($m in $passed) {
      Say "phase 3: $m main study"
      & $Python run_experiment_v3.py --experiment-dir ("experiments/main-" + (Slug $m)) `
        --model $m --max-turns 4 --git-commit (git rev-parse --short HEAD) |
        Out-File -FilePath $Log -Append -Encoding utf8
      Say "phase 3: $m policy authoring"
      & $Python run_policy_authoring_v3.py --experiment-dir experiments/policy-authoring-round2 `
        --model $m --git-commit (git rev-parse --short HEAD) |
        Out-File -FilePath $Log -Append -Encoding utf8
    }
    Publish "run: additional models across both studies"
  }
  $state.phase3 = $true; Save-State $state
  Say "phase 3 done"
}

Say "=== driver complete ==="
