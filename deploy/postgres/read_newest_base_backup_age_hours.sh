#!/usr/bin/env bash
set -euo pipefail

repository_directory=$(cd "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
deploy_environment_file=${STARTER_ENVIRONMENT_FILE:?set STARTER_ENVIRONMENT_FILE to the deploy .env}
: "${STARTER_POSTGRES_BACKUP_ENVIRONMENT_FILE:?set STARTER_POSTGRES_BACKUP_ENVIRONMENT_FILE to the backup env file}"
: "${STARTER_DATABASE_OWNER_ENVIRONMENT_FILE:?set STARTER_DATABASE_OWNER_ENVIRONMENT_FILE to the database owner env file}"
export STARTER_ENVIRONMENT_FILE STARTER_POSTGRES_BACKUP_ENVIRONMENT_FILE STARTER_DATABASE_OWNER_ENVIRONMENT_FILE
export POSTGRES_ARCHIVE_MODE=on

compose=(docker compose --env-file "$deploy_environment_file"
  -f "$repository_directory/docker-compose.yml" -f "$repository_directory/deploy/docker-compose.production.yml")

backup_list_json=$("${compose[@]}" exec -T -u postgres postgres wal-g backup-list --json --detail)
printf '%s\n' "SELECT floor(extract(epoch FROM now() - max((backup ->> 'finish_time')::timestamptz)) / 3600)::int
  FROM jsonb_array_elements(:'backup_list'::jsonb) AS backup;" |
  "${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -tA -v backup_list="$backup_list_json" | tr -d '\r'
