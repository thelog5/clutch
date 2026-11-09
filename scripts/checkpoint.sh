#!/usr/bin/env bash
# Records a build-log entry and commits everything staged + unstaged.
#
# Usage: scripts/checkpoint.sh <block-id> "<commit subject>" ["<log note>"]
#   block-id   short tag like P1, M2, A3, W4 (see docs/BUILD_LOG.md legend)
#   subject    git commit subject line
#   log note   optional longer note for the build log (defaults to subject)
#
# The log line is written before the commit, so the commit that introduces a
# block also contains its timestamped log entry. `git log` gives the hash.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

block="${1:?block id required}"
subject="${2:?commit subject required}"
note="${3:-$subject}"
stamp="$(date '+%Y-%m-%d %H:%M %Z')"

printf '| %s | %s | %s |\n' "$stamp" "$block" "$note" >> docs/BUILD_LOG.md

git add -A
git commit -q -m "$subject" -m "Block: $block"
git log -1 --format='%h %s'
