# python-backend-template

[![template-check](https://github.com/7331/python-backend-template/actions/workflows/template-check.yml/badge.svg?branch=main)](https://github.com/7331/python-backend-template/actions/workflows/template-check.yml)

A [Copier](https://copier.readthedocs.io/en/stable/) template for a Python backend: FastAPI on Python 3.15, uv,
Docker Compose, and the gates that keep every app the same shape. Postgres, passkey accounts and a job worker are
options. There is no frontend; the OpenAPI document is the contract.

## Start an app

```sh
uvx copier copy --trust gh:7331/python-backend-template my-app
cd my-app
cp .env.example .env
cp .env.database-owner.example .env.database-owner
docker compose up -d --build --wait
curl http://127.0.0.1:8000/health
```

`--trust` lets Copier run the setup tasks (`git init`, `uv lock`, a first `openapi.json`, the git hooks). The copy
message lists the env keys that need a value. From there the app's own `README.md` covers checks and deploy, and its
`BACKEND-API.md` shows the backend as a tree and diagrams, then the rules the code follows.

## What it's for

A backend that one team runs on one host, with a web app, a mobile app, a CLI or another service as its client.

- **No Postgres:** a thin API in front of someone else's, such as a mobile app's backend that wraps, caches and
  rate-limits a third-party API and keeps its keys off the device.
- **Postgres:** the API behind a web or mobile app's own data, an internal tool, or a webhook receiver that
  verifies, stores and answers.
- **Accounts:** a consumer app where people sign up and sign in with a passkey and stay signed in with a cookie
  session.
- **Worker:** work that should not hold a request open: sending email or push notifications, processing an upload,
  syncing from a third-party API, retrying a delivery that failed.

It is not for server-rendered pages or a cluster: the deploy is Docker Compose on a single host. With Postgres the
request budgets live in the database, so a second API replica shares them. Without Postgres they live in process
memory, which means one replica.

## Questions

| Question | What it does |
| --- | --- |
| `project_slug` | Lowercase with hyphens, like `shop-7331`. Names the compose project, image, database and CLI. Its first segment is the env prefix (`SHOP_`). |
| `root_package` | The domain package under `backend/app/`. Defaults to the slug's first segment. |
| `project_description` | One line for `pyproject.toml` and the CLI help. |
| `include_postgres` | Default yes. Postgres 18, Alembic, WAL-G backups and a restore drill. |
| `include_accounts` | Postgres only, default yes. Passkey sign-up and sign-in with cookie sessions. |
| `include_worker` | Postgres only, default no. A job queue in a `jobs` table and a `worker` service. |

## Update an app

```sh
uvx copier update --trust
```

The tree must be clean. Conflicts land as inline markers. Each
[release](https://github.com/7331/python-backend-template/releases) lists the steps an update needs by hand.

## This repository

- `copier.yml` holds the questions and setup tasks; `template/` is what Copier renders.
- `template-check` generates the app with every option set, runs its gates, updates an app from the newest release
  tag, and boots the Postgres sets with their e2e flows.
- Every release gets a tag, because `copier update` only moves between tags.
