#!/usr/bin/env bash
set -euo pipefail
umask 077

repository_directory=$(cd "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
deploy_environment_file=${STARTER_ENVIRONMENT_FILE:?set STARTER_ENVIRONMENT_FILE to the deploy .env}
: "${STARTER_POSTGRES_BACKUP_ENVIRONMENT_FILE:?set STARTER_POSTGRES_BACKUP_ENVIRONMENT_FILE to the backup env file}"
: "${STARTER_DATABASE_OWNER_ENVIRONMENT_FILE:?set STARTER_DATABASE_OWNER_ENVIRONMENT_FILE to the database owner env file}"
export STARTER_ENVIRONMENT_FILE STARTER_POSTGRES_BACKUP_ENVIRONMENT_FILE STARTER_DATABASE_OWNER_ENVIRONMENT_FILE
export POSTGRES_ARCHIVE_MODE=on
archive_wait_seconds=${POSTGRES_BACKUP_ARCHIVE_WAIT_SECONDS:-180}

fail() { printf 'backup failed: %s\n' "$1" >&2; exit 1; }

exec 9<"${BASH_SOURCE[0]}"
flock --nonblock 9 || fail "another backup run holds the lock"

compose=(docker compose --env-file "$deploy_environment_file"
  -f "$repository_directory/docker-compose.yml" -f "$repository_directory/deploy/docker-compose.production.yml")
query_postgres() { "${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -tAc "$1" | tr -d '\r'; }
run_wal_g() { "${compose[@]}" exec -T -u postgres postgres wal-g "$@"; }

[[ "$(query_postgres "SELECT current_setting('archive_mode')")" == on ]] ||
  fail "archive_mode is off; start the stack with deploy/deploy.sh"

query_postgres "SELECT pg_create_restore_point('starter-app backup')" >/dev/null
switched_wal_segment=$(query_postgres 'SELECT pg_walfile_name(pg_switch_wal())')
archive_deadline_epoch=$(( $(date -u +%s) + archive_wait_seconds ))
while [[ "$(query_postgres "SELECT coalesce(last_archived_wal, '') FROM pg_stat_archiver")" < "$switched_wal_segment" ]]; do
  (( $(date -u +%s) < archive_deadline_epoch )) ||
    fail "WAL segment $switched_wal_segment was not archived within ${archive_wait_seconds}s; read pg_stat_archiver and docker compose logs postgres"
  sleep 2
done
printf 'WAL segment %s is archived\n' "$switched_wal_segment"

# shellcheck disable=SC2016 # PGDATA expands in the container's shell
"${compose[@]}" exec -T -u postgres postgres sh -c 'exec wal-g backup-push "$PGDATA"'

wal_verify_report=$(run_wal_g wal-verify integrity timeline 2>&1)
printf '%s\n' "$wal_verify_report"
[[ "$wal_verify_report" != *"status: FAILURE"* ]] || fail "wal-g wal-verify found lost WAL segments or a timeline conflict"

run_wal_g backup-list --detail
printf 'completed starter-app base backup at %s\n' "$(date -u +%FT%TZ)"
