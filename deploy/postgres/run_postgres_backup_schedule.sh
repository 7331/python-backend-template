#!/usr/bin/env bash
set -uo pipefail

script_directory=$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
backup_interval_seconds=${POSTGRES_BACKUP_INTERVAL_SECONDS:-86400}
restore_drill_interval_seconds=${POSTGRES_RESTORE_DRILL_INTERVAL_SECONDS:-604800}
retry_after_failure_seconds=${POSTGRES_BACKUP_RETRY_SECONDS:-3600}
next_backup_epoch=0
next_restore_drill_epoch=0

report_outcome() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$1"; }

while :; do
  if (( $(date -u +%s) >= next_backup_epoch )); then
    started_epoch=$(date -u +%s)
    if "$script_directory/backup_postgres.sh"; then
      report_outcome "base backup passed in $(( $(date -u +%s) - started_epoch ))s"
      next_backup_epoch=$(( started_epoch + backup_interval_seconds ))
    else
      report_outcome "base backup FAILED with exit $?; retrying in ${retry_after_failure_seconds}s"
      next_backup_epoch=$(( started_epoch + retry_after_failure_seconds ))
    fi
  fi
  if (( $(date -u +%s) >= next_restore_drill_epoch )); then
    started_epoch=$(date -u +%s)
    if "$script_directory/verify_postgres_backup_restore.sh"; then
      report_outcome "restore drill passed in $(( $(date -u +%s) - started_epoch ))s"
      next_restore_drill_epoch=$(( started_epoch + restore_drill_interval_seconds ))
    else
      report_outcome "restore drill FAILED with exit $?; retrying in ${retry_after_failure_seconds}s"
      next_restore_drill_epoch=$(( started_epoch + retry_after_failure_seconds ))
    fi
  fi
  sleep 60
done
