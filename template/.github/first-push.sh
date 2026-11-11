#!/usr/bin/env bash
set -euo pipefail

create_label() {
  gh label create "$1" --force --color "$2" --description "$3"
}

create_label bug d73a4a "Something doesn't work as intended"
create_label enhancement a2eeef "New behaviour, or a refactor, cleanup, tooling, docs or performance change"
create_label question d876e3 "Needs an owner decision before work starts"
create_label idea c5def5 "Kept for later, not work yet"
create_label parked ededed "Skipped for now by the owner, to be picked up later"
create_label security b60205 "Touches authentication, keys, encryption or privacy"
create_label priority:urgent b60205 "Users blocked, or data or security at risk now: drop everything"
create_label priority:high d93f0b "A broken flow with no workaround: next up"
create_label priority:low c2e0c6 "Polish, fine if it never happens"

gh api --method PATCH "repos/{owner}/{repo}" \
  --field allow_squash_merge=true --field allow_merge_commit=false --field allow_rebase_merge=false \
  --field allow_auto_merge=true --field delete_branch_on_merge=true \
  --field squash_merge_commit_title=PR_TITLE --field squash_merge_commit_message=PR_BODY >/dev/null

gh api --method PUT "repos/{owner}/{repo}/vulnerability-alerts"
gh api --method PUT "repos/{owner}/{repo}/automated-security-fixes"

gh api --method POST "repos/{owner}/{repo}/rulesets" --input .github/rulesets/main.json >/dev/null

echo "labels, squash-only merges with auto-merge, Dependabot alerts and the main ruleset are set"
