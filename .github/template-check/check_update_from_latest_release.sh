#!/usr/bin/env bash
set -euo pipefail

template_directory="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
changed_app_directory="${template_directory}/.github/template-check/changed-app"
app_directory="${1:?usage: check_update_from_latest_release.sh <app directory> <untouched|changed>}"
app_state="${2:?usage: check_update_from_latest_release.sh <app directory> <untouched|changed>}"
latest_release_tag="$(git -C "${template_directory}" describe --tags --abbrev=0)"

insert_line_after() {
  local file_path="$1" anchor_line="$2" new_line="$3"
  grep --quiet --fixed-strings --line-regexp -- "${anchor_line}" "${file_path}" || {
    echo "::error::${file_path} has no line '${anchor_line}' to anchor the app's edit on"
    exit 1
  }
  ANCHOR_LINE="${anchor_line}" NEW_LINE="${new_line}" \
    awk '{ print } $0 == ENVIRON["ANCHOR_LINE"] { print ENVIRON["NEW_LINE"] }' "${file_path}" > "${file_path}.edited"
  mv "${file_path}.edited" "${file_path}"
}

apply_changed_app_edit() {
  cp -R "${changed_app_directory}/." .
  insert_line_after backend/app/configuration.py \
    '    log_level: LogLevel = LogLevel.INFO' \
    '    service_notice_message: str = ""'
  insert_line_after .env.example \
    'SAMPLE_LOG_LEVEL=INFO' \
    'SAMPLE_SERVICE_NOTICE_MESSAGE='
  insert_line_after backend/app/main.py \
    'from app.request_log_middleware import RequestLogMiddleware' \
    'from app.sample.notices.router import notices_router'
  insert_line_after backend/app/main.py \
    '    application.add_api_route("/health", read_health, methods=["GET", "HEAD"], include_in_schema=False)' \
    '    application.include_router(notices_router)'
  if [[ "${INCLUDE_ACCOUNTS}" == true ]]; then
    insert_line_after backend/pyproject.toml \
      '    "log_events",' \
      '    "sample.notices",'
  fi
  uv run --quiet --directory backend ruff check --select I --fix --quiet app
  uv run --quiet --directory backend python tools/dump_openapi.py openapi.json
}

require_changed_app_edit() {
  local kept_line_checks=(
    'backend/app/configuration.py:    service_notice_message: str = ""'
    '.env.example:SAMPLE_SERVICE_NOTICE_MESSAGE='
    'backend/app/main.py:from app.sample.notices.router import notices_router'
    'backend/app/main.py:    application.include_router(notices_router)'
    'backend/openapi.json:    "/api/v1/notices/current": {'
  )
  if [[ "${INCLUDE_ACCOUNTS}" == true ]]; then
    kept_line_checks+=('backend/pyproject.toml:    "sample.notices",')
  fi
  local kept_line_check
  for kept_line_check in "${kept_line_checks[@]}"; do
    grep --quiet --fixed-strings --line-regexp -- "${kept_line_check#*:}" "${kept_line_check%%:*}" || {
      echo "::error::the update dropped the app's own line '${kept_line_check#*:}' from ${kept_line_check%%:*}"
      exit 1
    }
  done
  diff --recursive "${changed_app_directory}/backend/app/sample/notices" backend/app/sample/notices \
    --exclude __pycache__ || {
    echo "::error::the update changed the app's own notices package"
    exit 1
  }
}

fail_on_update_conflicts() {
  local unmerged_paths conflict_marker_lines reject_files
  unmerged_paths="$(git diff --name-only --diff-filter=U)"
  conflict_marker_lines="$(git grep --untracked --line-number --extended-regexp '^(<{7}|>{7}) ' || true)"
  reject_files="$(git ls-files --cached --others --exclude-standard -- '*.rej')"
  if [[ -n "${unmerged_paths}${conflict_marker_lines}${reject_files}" ]]; then
    echo "::error::copier update from ${latest_release_tag} left conflicts in the ${app_state} app"
    printf 'unmerged paths:\n%s\nconflict markers:\n%s\nreject files:\n%s\n' \
      "${unmerged_paths}" "${conflict_marker_lines}" "${reject_files}"
    exit 1
  fi
}

echo "Generating the app from ${latest_release_tag}"
uvx copier copy --trust --defaults --vcs-ref "${latest_release_tag}" \
  --data project_slug=sample-app \
  --data "include_postgres=${INCLUDE_POSTGRES}" \
  --data "include_accounts=${INCLUDE_ACCOUNTS}" \
  "${template_directory}" "${app_directory}"
cd "${app_directory}"
git add --all
git commit --quiet --no-verify --message "Generated app from ${latest_release_tag}"

if [[ "${app_state}" == changed ]]; then
  apply_changed_app_edit
  git add --all
  git commit --quiet --no-verify --message "The app adds a setting key and a route"
fi

echo "Updating the ${app_state} app from ${latest_release_tag} to the template's HEAD"
uvx copier update --trust --defaults --vcs-ref HEAD --conflict inline
fail_on_update_conflicts
uv run --quiet --directory backend python tools/dump_openapi.py openapi.json
if [[ "${app_state}" == changed ]]; then
  require_changed_app_edit
fi
git add --all
git commit --quiet --no-verify --allow-empty --message "Updated app"
uvx prek run --all-files
