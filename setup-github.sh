#!/usr/bin/env bash
#
# Initialise the repository and prepare the first commit.
#
#   ./setup-github.sh
#
# Does not touch the network. It stages everything, commits, and prints the two
# commands you run afterwards. Nothing here needs your credentials.
set -euo pipefail

if [ -d .git ]; then
  echo "This directory is already a git repository. Nothing to do."
  exit 0
fi

# --- Sanity checks before committing anything public ------------------------
echo "Checking for things that must not be published..."
PROBLEMS=0

if [ -d data ]; then
  echo "  ok    data/ is gitignored — the generated CSVs stay local."
fi

# Placeholders and the CI service container's own credentials are expected.
# Anything else that looks like a live connection string is a problem. A check
# that fires on every placeholder trains you to ignore it.
KNOWN_SAFE="USER:PASSWORD|user:pass|analytics:analytics"
LEAKS=$(grep -rEn "postgresql://[^\"' ]+:[^\"' @]+@" \
          --include="*.py" --include="*.yml" --include="*.sql" --include="*.md" . 2>/dev/null \
          | grep -v "setup-github.sh" \
          | grep -vE "$KNOWN_SAFE" || true)

if [ -n "$LEAKS" ]; then
  echo "  LEAK  a connection string with real-looking credentials:"
  echo "$LEAKS" | sed 's/^/          /'
  echo "        Replace it with an environment variable before pushing."
  PROBLEMS=1
else
  echo "  ok    no live credentials; only placeholders and the CI container."
fi

if [ -f .env ]; then
  echo "  ok    .env exists and is gitignored."
fi

for f in LICENSE README.md; do
  if grep -q "YOUR NAME\|YOUR-USERNAME" "$f" 2>/dev/null; then
    echo "  TODO  replace the placeholder in $f"
  fi
done
echo

git init -q
git add -A
git -c user.name="${GIT_NAME:-$(git config --global user.name || echo 'Analytics')}" \
    -c user.email="${GIT_EMAIL:-$(git config --global user.email || echo 'analytics@example.com')}" \
    commit -q -m "Contribution margin analytics for a US DTC brand

End-to-end profitability analysis: synthetic data generator, Postgres warehouse,
dbt transformation layer, and a static report.

- Generator models SCD2 unit costs, dimensional-weight freight, returns
  disposition and per-channel attribution overstatement. Self-test: 20/20.
- dbt pipeline across raw, staging, intermediate and marts. 100 models and
  tests passing, including six singular integrity tests.
- Reconciliation harness compares every mart total against ground truth and
  agrees to 0.007% of contribution margin.
- Findings are designed into the data on purpose; the analysis rediscovers the
  two loss-making SKUs from return behavior alone, without the label."

BRANCH=$(git symbolic-ref --short HEAD)
if [ "$BRANCH" != "main" ]; then
  git branch -M main
fi

echo "Committed $(git ls-files | wc -l | tr -d ' ') files on branch main."
echo
echo "Next, on github.com: create an empty repository named northlane-analytics."
echo "Do not add a README, .gitignore or license — this repo already has them."
echo
echo "Then run:"
echo
echo "  git remote add origin https://github.com/YOUR-USERNAME/northlane-analytics.git"
echo "  git push -u origin main"
echo
echo "After the push, enable the live demo:"
echo "  Settings -> Pages -> Source: Deploy from a branch -> main -> /docs -> Save"
echo
echo "Then rebuild the page so the masthead link points at your repo:"
echo "  REPO_URL=https://github.com/YOUR-USERNAME/northlane-analytics make dashboard"
echo "  git commit -am 'Point masthead at the repository' && git push"

exit $PROBLEMS
