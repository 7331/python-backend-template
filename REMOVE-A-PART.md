# Remove a part you do not need

The template comes whole: Postgres, passkey accounts, a job worker and object storage. A project that does not need a
part removes it once, right after it starts.

1. Remove in this order, skipping the parts you keep: object storage, worker, accounts, Postgres. Accounts, the worker
   and object storage each need Postgres, and the `files` sample domain needs accounts.
2. For each part, delete its paths, then cut its lines from each file in its table.
3. Run `uv lock` in `backend/` and in `e2e/`, then `uv run --directory backend python tools/dump_openapi.py openapi.json`.
4. Run `uvx prek run --stage pre-push --all-files`. Ruff, vulture, deptry, import-linter and the setting-key check name
   most of what a cut left behind.
5. Delete this file.

Nothing in CI checks these lists, because CI only runs the template whole. They were compared with the files each
part added when the template was still generated per option.

## Object storage

Delete:

- `backend/app/infrastructure/object_storage/`
- `backend/app/starter/files/`
- `backend/migrations/template_versions/object_storage_0001_files_table.py`
- `e2e/object_storage_flow.py`

| Cut from | What |
| --- | --- |
| `backend/app/main.py` | the files router |
| `backend/app/lifespan/composition.py` and `resources.py` | the object storage client |
| `backend/app/rate_limit_middleware.py` | the upload URL budget |
| `backend/migrations/env.py` | its import |
| `backend/pyproject.toml` | `botocore`, two layers, three contracts |
| `backend/vulture_whitelist.py` | its names |
| `backend/tools/check_function_names.py` | the verb `copy` |
| `docker-compose.yml` and `deploy/docker-compose.production.yml` | the `object-storage` service and its volume |
| `e2e/stack_commands.py` | its env lines |
| `.env.example` | its keys |
| `.github/workflows/ci.yml` | the flow's step |
| `e2e/README.md` and `BACKEND-API.md` | what they say about it |

## Worker

Delete:

- `backend/app/infrastructure/task_queue/`
- `backend/app/starter/queue_probe/`
- `backend/app/worker.py`
- `backend/app/worker_healthcheck.py`
- `backend/migrations/template_versions/worker_0001_job_queue.py`
- `e2e/worker_flow.py`

| Cut from | What |
| --- | --- |
| `backend/app/cli.py` | two commands |
| `backend/app/lifespan/composition.py` and `resources.py` | the process resources |
| `backend/migrations/env.py` | its import |
| `backend/pyproject.toml` | four layers, one contract |
| `backend/vulture_whitelist.py` | its names |
| `backend/tools/check_file_kinds.py` | the `jobs` kind |
| `backend/tools/check_function_names.py` | the queue's verbs: `claim`, `enqueue`, `fail`, `release`, `requeue` |
| `docker-compose.yml`, `compose.watch.yml` and `deploy/docker-compose.production.yml` | the `worker` service |
| `.env.example` | its keys |
| `.github/workflows/ci.yml` | the flow's step |
| `e2e/README.md` and `BACKEND-API.md` | what they say about it |

## Accounts

The `files` sample domain belongs to an account. Remove it first (the object storage list above, keeping
`backend/app/infrastructure/object_storage/` if the project will store files), or rewrite it without an owner.

Delete:

- `backend/app/starter/accounts/`
- `backend/app/shared/identifiers.py`
- `backend/migrations/template_versions/accounts_0001_account_tables.py`
- `e2e/accounts_flow.py`
- `e2e/software_passkey.py`

| Cut from | What |
| --- | --- |
| `backend/app/main.py` | the accounts router and the relying party's host |
| `backend/app/lifespan/api_lifespan.py` | the relying party check at startup |
| `backend/app/rate_limit_middleware.py` | the passkey budget |
| `backend/app/shared/errors.py` | the four errors nothing raises any more |
| `backend/migrations/env.py` | its import |
| `backend/pyproject.toml` | `webauthn`, one layer, one contract |
| `e2e/pyproject.toml` | `cbor2`, `cryptography` |
| `e2e/stack_commands.py` | its env lines |
| `.env.example` | its keys |
| `.github/workflows/ci.yml` | the flow's step |
| `e2e/README.md` and `BACKEND-API.md` | what they say about it |

With no domain left, vulture reports the scaffolding the first domain will use (`API_PREFIX`, `ApiRequest`,
`describe_error_responses`, `DatabaseSession`, the ORM mixins). List it in `backend/vulture_whitelist.py` until a
domain uses it.

## Postgres

Without Postgres the request budgets live in process memory, which means one API replica.

Delete:

- `backend/alembic.ini`
- `backend/migrations/`
- `backend/app/infrastructure/postgres/`
- `backend/app/infrastructure/rate_limit/log_events.py`, `models.py` and `postgres_limiter_store.py`
- `backend/app/shared/blocking_executor.py`
- `backend/tools/check_migrations.py`
- `deploy/postgres/`
- `compose.postgres-loopback.yml`
- `.env.database-owner.example`

| Cut from | What |
| --- | --- |
| `backend/app/configuration.py` | the connection settings |
| `backend/app/lifespan/composition.py`, `dependencies.py` and `resources.py` | the database; `Resources` keeps an `InMemoryRateLimiter` |
| `backend/app/main.py` | `/ready` answers like `/health` |
| `backend/app/rate_limit_middleware.py` | the in-memory check is not awaited |
| `backend/app/shared/errors.py` | `NotReadyError` |
| `backend/app/shared/logging.py` | the SQLAlchemy logger and the database detail redaction |
| `backend/Dockerfile` and `backend/Dockerfile.dockerignore` | the migrations, `alembic.ini` and the owner env file |
| `backend/pyproject.toml` | its dependencies, layers and contracts |
| `backend/vulture_whitelist.py` | its names |
| `backend/tools/check_file_kinds.py` | the `models` and `repository` kinds |
| `backend/tools/check_function_names.py`, `check_constant_homes.py` and `run_house_rules.py` | the `migrations` directory |
| `.pre-commit-config.yaml` | the migrations hook and the `migrations` directory in the ruff hooks |
| `docker-compose.yml` and `deploy/docker-compose.production.yml` | the `postgres` and `migrate` services |
| `deploy/deploy.sh` | the backup and owner env file checks |
| `e2e/stack_commands.py` | the owner env file and the database read |
| `.env.example` and `.gitignore` | its keys and the owner env file |
| `.github/dependabot.yml` | the `/deploy/postgres` entry |
| `.github/pull_request_template.md` | the migration checkbox |
| `.github/workflows/ci.yml` | its env file lines |
| `README.md`, `e2e/README.md` and `BACKEND-API.md` | what they say about it |
