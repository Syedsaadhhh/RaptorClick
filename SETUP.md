# Setup, verification and deployment

Everything needed to get this branch pushed and CI green.

## 1. Copy into the repo

The folder you have mirrors the repo layout exactly. From the repo root:

```bash
cd Raptor-Agent

git checkout main
git pull origin main
git checkout -b feature/protection-analytics
```

Copy these paths in, preserving structure:

```
src/raptor/__init__.py
src/raptor/analytics/*.py
tests/analytics/*.py
tests/run_with_stdlib.py
docs/analytics/*.md
.github/workflows/analytics.yml
pyproject.toml            # merge if one already exists — see note below
PR_DESCRIPTION.md         # paste into the PR body, then delete the file
```

**If `pyproject.toml` already exists on main**, do not overwrite it. Merge only
the `[tool.pytest.ini_options]` block and `[tool.setuptools.packages.find]`
(`where = ["src"]`), and check `requires-python` is not raised above 3.10.

## 2. Verify before you push

This is the step I could not complete — my sandbox had no network to install
pytest, and the VM became unresponsive. Run it locally first.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest tests/analytics -v
```

Expect a handful of hand-computed expectations to need last-decimal
corrections — those are test-side fixes, not model bugs. If something fails,
check the assertion against the actual output before changing any source.

Then confirm the pipeline runs:

```bash
python -m raptor.analytics.cli --all
```

You should see the five fixtures scoring 95.46 / 70.78 / 39.99 / 39.99 / 90.00.

Confirm determinism across processes:

```bash
python -m raptor.analytics.cli --fixture balanced > /tmp/a.json
python -m raptor.analytics.cli --fixture balanced > /tmp/b.json
diff /tmp/a.json /tmp/b.json && echo OK
```

## 3. Generate the golden file

Only once the suite is green — the golden file must come from the code, never
from hand-editing:

```bash
python -m raptor.analytics.cli --golden
git add fixtures/golden_report.json
```

From then on, any diff in that file on a future PR means the model moved and
someone needs to have decided that deliberately.

## 4. Seed the frontend

Generate mock data for Issue #1 so Reann is unblocked:

```bash
python -m raptor.analytics.cli --seed-frontend
git add fixtures/frontend_seed/
```

## 5. Commit and push

```bash
git add src/raptor tests docs/analytics .github/workflows/analytics.yml pyproject.toml
git commit -m "feat(analytics): deterministic protection metrics, scoring and tests

Typed analytics module with Decimal-based deterministic arithmetic, exposure
and concentration metrics, drawdown analysis, stress-scenario risk model with
an idiosyncratic term driven by concentration, hedge payoff and auction
ranking, weighted protection scoring with hard overrides, and a pytest suite
including determinism and contract tests.

Refs #3"

git push -u origin feature/protection-analytics
```

If push is rejected with a permissions error, the repo invitation is still
pending — accept it at https://github.com/Syedsaadhhh/Raptor-Agent/invitations
and retry.

## 6. Open the draft PR

```bash
# with the GitHub CLI
gh pr create --draft \
  --base main \
  --head feature/protection-analytics \
  --title "Analytics: protection metrics, scoring and tests" \
  --body-file PR_DESCRIPTION.md
```

Or on the web: **Pull requests → New pull request →** base `main`, compare
`feature/protection-analytics` → **Create draft pull request**, and paste
`PR_DESCRIPTION.md` as the body. Link it to Issue #3.

Delete `PR_DESCRIPTION.md` from the branch afterwards — it is a PR body, not a
repo file.

```bash
git rm PR_DESCRIPTION.md && git commit -m "chore: drop PR body file" && git push
```

## 7. CI

`.github/workflows/analytics.yml` runs on any push to `feature/**` and on PRs
touching analytics paths. It tests against Python 3.10 and 3.12, reports
coverage, and — the part worth having — asserts that two separate interpreter
processes produce identical JSON.

If the Actions tab shows nothing, check **Settings → Actions → General →
Allow all actions**.

## Deployment notes

There is nothing to deploy here in the service sense. This is a pure library:
no network calls, no database, no state, no background jobs. It ships as part
of whatever process imports it.

The backend (Issue #2) deploys the API that calls `analyse()`. When that
happens, the only things to get right are that `src/` is on the import path
(handled by `pip install -e .`) and that `AnalyticsConfig` is constructed once
at startup and passed down, rather than rebuilt per request.

For a container, this is enough:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .
CMD ["python", "-m", "raptor.analytics.cli", "--all"]
```

Replace `CMD` with the backend's server command once #2 lands.
