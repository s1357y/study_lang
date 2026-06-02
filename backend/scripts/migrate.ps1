<#
.SYNOPSIS
수동 마이그레이션 스크립트 — 메시지를 지정해 리비전을 생성하고 바로 적용한다.

.DESCRIPTION
AUTO_MIGRATE=false 환경(운영 등)이나, 의미 있는 이름으로 리비전을 만들고 싶을 때 사용.
자동 생성된 auto_YYYYMMDD_HHMMSS 리비전과 달리 설명적 이름을 붙일 수 있다.

.PARAMETER Message
리비전 메시지 (alembic revision -m). 기본값은 현재 타임스탬프.

.EXAMPLE
.\scripts\migrate.ps1 add_user_profile_table
.\scripts\migrate.ps1 widen_content_payload_index
.\scripts\migrate.ps1    # 메시지 없으면 manual_YYYYMMDD_HHMMSS 사용
#>
param(
    [string]$Message = "manual_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
)

# backend/ 루트로 이동 (alembic.ini 위치)
Push-Location (Join-Path $PSScriptRoot "..")
try {
    Write-Host "리비전 생성: $Message"
    uv run alembic revision --autogenerate -m $Message
    if ($LASTEXITCODE -ne 0) {
        Write-Host "리비전 생성 실패" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "마이그레이션 적용 (upgrade head)..."
    uv run alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "마이그레이션 적용 실패" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "완료" -ForegroundColor Green
} finally {
    Pop-Location
}
