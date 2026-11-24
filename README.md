# python-backend-template

[![CI](https://github.com/7331/python-backend-template/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/7331/python-backend-template/actions/workflows/ci.yml)

A Python backend to start a project from: FastAPI on Python 3.15, uv, Docker Compose, Postgres 18, passkey accounts,
a job worker, object storage, and the gates that keep the code one shape. The repository is the app itself, so
everything in it runs and is checked as it stands. There is no frontend; the OpenAPI document is the contract.
`BACKEND-API.md` shows the backend as a tree and diagrams, then the rules the code follows. `AGENTS.md` holds the
rules for agents and pull requests.

It is for a backend one team runs on one host, with a web app, a mobile app, a CLI or another service as its client:
the API behind an app's own data, an internal tool, a webhook receiver. It is not for server-rendered pages or a
cluster: the deploy is Docker Compose on a single host.

## Start a project

Create a repository from this one (`gh repo create <name> --template 7331/python-backend-template --private --clone`),
then rename the four names the template runs under: `starter-app` (compose project, image, CLI), `starterapp`
(database), `STARTER` (env prefix) and `starter` (the domain package under `backend/app/`). Paste the block as one,
with your names in its first line:

```sh
project_slug=shop-7331 database_name=shop7331 environment_prefix=SHOP root_package=shop
git grep -lz -e starter -e STARTER | xargs -0 sed --in-place \
  -e "s/starter-app/$project_slug/g" -e "s/starterapp/$database_name/g" \
  -e "s/STARTER_/${environment_prefix}_/g" -e "s/starter/$root_package/g"
git mv backend/app/starter "backend/app/$root_package"
git mv deploy/postgres/starter-app-postgres-backup-schedule.service \
  "deploy/postgres/$project_slug-postgres-backup-schedule.service"
uv run --directory backend ruff check --select I --fix app tools migrations
uv run --directory backend ruff format app tools migrations
uv run --directory backend python tools/dump_openapi.py openapi.json
uvx prek install
uvx prek run --stage pre-push --all-files
```

The block rewrites this file too: replace its top with the project's own words and delete this section and the next.
`AGENTS.md` (A new repository) lists the settings to apply once on GitHub.

## Remove a part you do not need

Accounts, the worker and object storage each need Postgres, and the `files` sample domain needs accounts, so remove
in this order: object storage, worker, accounts, Postgres. For each part, delete the paths, cut the part's block from
each file named, then run `uv lock` in `backend/` and `e2e/`, rewrite `backend/openapi.json` and run the gates: ruff,
vulture, deptry, import-linter and the setting-key check name most of what a cut left behind. Nothing in CI checks
these lists, because CI only runs the template whole.

- **Object storage.** Delete `backend/app/infrastructure/object_storage/`, `backend/app/starter/files/`,
  `backend/migrations/template_versions/object_storage_0001_files_table.py` and `e2e/object_storage_flow.py`. Cut from
  `backend/app/main.py` (the router), `backend/app/lifespan/composition.py` and `resources.py` (the client),
  `backend/app/rate_limit_middleware.py` (the upload URL budget), `backend/migrations/env.py`,
  `backend/pyproject.toml` (`botocore`, two layers, three contracts), `backend/vulture_whitelist.py`,
  `docker-compose.yml` and `deploy/docker-compose.production.yml` (the `object-storage` service and its volume),
  `e2e/stack_commands.py`, `e2e/README.md`, `.env.example`, `.github/workflows/ci.yml` and `BACKEND-API.md`.
- **Worker.** Delete `backend/app/infrastructure/task_queue/`, `backend/app/starter/queue_probe/`,
  `backend/app/worker.py`, `backend/app/worker_healthcheck.py`,
  `backend/migrations/template_versions/worker_0001_job_queue.py` and `e2e/worker_flow.py`. Cut from
  `backend/app/cli.py` (two commands), `backend/app/lifespan/composition.py` and `resources.py` (the process
  resources), `backend/migrations/env.py`, `backend/pyproject.toml` (four layers, one contract),
  `backend/vulture_whitelist.py`, `docker-compose.yml`, `compose.watch.yml` and
  `deploy/docker-compose.production.yml` (the `worker` service), `e2e/README.md`, `.env.example`,
  `.github/workflows/ci.yml` and `BACKEND-API.md`.
- **Accounts.** Remove the `files` sample domain first (the object storage list, keeping the client package if the
  project will store files), or rewrite it without an owner. Delete `backend/app/starter/accounts/`,
  `backend/app/shared/identifiers.py`, `backend/migrations/template_versions/accounts_0001_account_tables.py`,
  `e2e/accounts_flow.py` and `e2e/software_passkey.py`. Cut from `backend/app/main.py` (the router and the relying
  party's host), `backend/app/lifespan/api_lifespan.py`, `backend/app/rate_limit_middleware.py` (the passkey budget),
  `backend/app/shared/errors.py` (the four errors nothing raises any more), `backend/migrations/env.py`,
  `backend/pyproject.toml` (`webauthn`, one layer, one contract), `e2e/pyproject.toml` (`cbor2`, `cryptography`),
  `e2e/stack_commands.py`, `e2e/README.md`, `.env.example`, `.github/workflows/ci.yml` and `BACKEND-API.md`. With no
  domain left, vulture reports the scaffolding the first domain will use (`API_PREFIX`, `ApiRequest`,
  `describe_error_responses`, `DatabaseSession`, the ORM mixins): list it in `backend/vulture_whitelist.py` until then.
- **Postgres.** Delete `backend/alembic.ini`, `backend/migrations/`, `backend/app/infrastructure/postgres/`,
  `log_events.py`, `models.py` and `postgres_limiter_store.py` in `backend/app/infrastructure/rate_limit/`,
  `backend/app/shared/blocking_executor.py`, `backend/tools/check_migrations.py`, `deploy/postgres/`,
  `compose.postgres-loopback.yml` and `.env.database-owner.example`. Cut from `backend/app/configuration.py` (the
  connection settings), `composition.py`, `dependencies.py` and `resources.py` in `backend/app/lifespan/`
  (`Resources` keeps an `InMemoryRateLimiter`), `backend/app/main.py` (`/ready` answers like `/health`),
  `backend/app/rate_limit_middleware.py` (the in-memory check is not awaited), `backend/app/shared/errors.py`
  (`NotReadyError`), `backend/app/shared/logging.py`, `backend/Dockerfile`, `backend/Dockerfile.dockerignore`,
  `backend/pyproject.toml`, `backend/vulture_whitelist.py`, `backend/tools/check_file_kinds.py` (the `models` and
  `repository` kinds), `check_function_names.py`, `check_constant_homes.py` and `run_house_rules.py` beside it (the
  `migrations` directory), `.pre-commit-config.yaml`, `deploy/deploy.sh`, `docker-compose.yml`,
  `deploy/docker-compose.production.yml`, `e2e/stack_commands.py`, `e2e/README.md`, `.env.example`, `.gitignore`,
  `.github/dependabot.yml`, `.github/pull_request_template.md`, `.github/workflows/ci.yml`, this file and
  `BACKEND-API.md`. The request budgets then live in process memory, which means one API replica.

## Run it

Copy the example env files, fill in every key they leave empty (none of them is committed), then start the stack:

```sh
cp .env.example .env
cp .env.database-owner.example .env.database-owner
docker compose up -d --build --wait
curl http://127.0.0.1:8000/health
```

For day-to-day work without an image rebuild, see Local development in `BACKEND-API.md`.

## Checks

```sh
uvx prek run --stage pre-push --all-files
```

CI runs the same command and plays the flows in `e2e/`: on a pull request once it is ready for review, on `main` and
every Monday. It runs on `ubuntu-latest` unless the repository variable `CI_RUNNER` names other runner labels as JSON.

## Deploy

On the host, with the env files outside the checkout and mode 600:

```sh
export STARTER_ENVIRONMENT_FILE=<deploy .env>
export STARTER_DATABASE_OWNER_ENVIRONMENT_FILE=<database owner env file>
export STARTER_POSTGRES_BACKUP_ENVIRONMENT_FILE=<backup env file>
deploy/deploy.sh
```

Once per host, install the backup schedule's systemd unit (Backup schedule in `BACKEND-API.md`). Until it runs,
`deploy/deploy.sh` deploys, warns and exits 1.
