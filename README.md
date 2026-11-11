# python-backend-template

[![template-check](https://github.com/7331/python-backend-template/actions/workflows/template-check.yml/badge.svg?branch=main)](https://github.com/7331/python-backend-template/actions/workflows/template-check.yml)

A [Copier](https://copier.readthedocs.io/en/stable/) template for a Python backend app. It gives you FastAPI on Python
3.15, typed structlog events, a typer CLI, uv and Docker Compose. PostgreSQL through SQLAlchemy and Alembic is on
unless you turn it off. There is no frontend. The OpenAPI document is the contract for any client. The generated
`BACKEND-API.md` shows the backend as a directory tree and diagrams, then the rules the code follows.

## Start an app

```sh
uvx copier copy --trust gh:7331/python-backend-template my-app
cd my-app
cp .env.example .env
cp .env.database-owner.example .env.database-owner
docker compose up -d --build --wait
curl http://127.0.0.1:8000/health
uvx prek run --stage pre-push --all-files
```

`--trust` lets Copier run the setup tasks: `git init`, `uv lock` in `backend/` and `e2e/`, an import sort and format
pass, a first `backend/openapi.json` and `uvx prek install`. Each app makes and commits its own `uv.lock`.

The app's own `README.md` has the first-push steps: the first commit, the labels the issue forms use, squash-only
merges with auto-merge, Dependabot alerts, and the `main` ruleset from `.github/rulesets/main.json`.

Fill in the env files before the first `up`. The copy message lists the keys that need a value. Without Postgres,
skip the second `cp`: there is no `.env.database-owner`. The API reads `.env` and gets only its own database role's
password.
`.env.database-owner` holds the superuser password, and only the `postgres` and `migrate` containers read it.
Production keeps both files outside the checkout with mode 600, plus the WAL-G backup file from
`deploy/postgres/backup.env.example`. `deploy/deploy.sh` refuses to run without them.

## Questions

| Question | What it does |
| --- | --- |
| `project_slug` | Lowercase with hyphens, like `shop-7331`. Names the compose project, the image, the database, the CLI and the service. Its first segment upper-cased is the env prefix (`SHOP_`). |
| `root_package` | The domain package under `backend/app/`, like `shop`. Defaults to the slug's first segment. |
| `project_description` | One line for `pyproject.toml` and the CLI help. |
| `include_postgres` | Default yes. Adds Postgres 18, Alembic, the `migrate` service, a request-scoped `DatabaseSession` and `deploy/postgres/` with WAL-G backups and the restore drill. Off means no database at all. |
| `include_accounts` | Asked only with Postgres. Default yes. Adds `app/<root>/accounts/`: passkey sign-up and sign-in, cookie sessions, sign-out and `GET /api/v1/me`. |
| `include_worker` | Asked only with Postgres. Default no. Adds a job queue in a `jobs` table (`app/infrastructure/task_queue/`), the `run-worker` command, a `worker` service in compose, one sample job kind and `e2e/worker_flow.py`. |

## Update an app

```sh
uvx copier update --trust
```

The app must be a git repository with a clean tree. Copier reads `.copier-answers.yml`, diffs the recorded template
version against the newest release tag and applies that diff. Conflicts land as inline markers. Each
[release](https://github.com/7331/python-backend-template/releases) lists the steps an update needs by hand.

## This repository

- `copier.yml` holds the questions, the setup tasks and the copy message.
- `template/` is what Copier renders. Only `.jinja` files are rendered. A file or folder whose name renders empty is
  skipped, which is how the options drop their files.
- `.github/workflows/template-check.yml` generates the app five ways (no Postgres, Postgres, Postgres with accounts, and the last two with the worker),
  runs `uvx prek run --stage pre-push --all-files` in each and audits the workflows each app gets with
  [zizmor](https://docs.zizmor.sh/). A second job audits this repository's own workflows. `Check` passes only when
  both did.
- `.github/workflows/pr-title.yml` and `.github/rulesets/main.json` are the same files an app gets: a pull request
  title is `type(scope): sentence`, and `main` takes squash merges of pull requests that pass `Check` and
  `Conventional title`. `template-check` fails when the two copies differ.
- `README.md` and `AGENTS.md` are in `_skip_if_exists`, so an update never overwrites an app's edits to them.
- Every release gets a tag, because `copier update` only moves between tags.
