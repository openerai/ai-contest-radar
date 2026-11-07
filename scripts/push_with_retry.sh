#!/usr/bin/env bash
# Never force-push or choose a side of a data conflict. Preserve remote edits.
set -euo pipefail
branch="${GITHUB_REF_NAME:-$(git symbolic-ref --short HEAD)}"
for attempt in 1 2 3 4 5; do
  git fetch origin "refs/heads/$branch"
  if ! git rebase FETCH_HEAD; then
    git rebase --abort
    echo "Concurrent edits conflict; refusing to overwrite remote data." >&2
    exit 1
  fi
  if git push origin "HEAD:refs/heads/$branch"; then
    exit 0
  fi
  if [ "$attempt" -lt 5 ]; then
    sleep "$attempt"
  fi
done
echo "Push still failed after five attempts; no remote data was overwritten." >&2
exit 1
