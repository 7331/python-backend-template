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

The template comes whole. `REMOVE-A-PART.md` lists, part by part, what to delete and what to cut for a project
without object storage, the worker, accounts or Postgres.

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

CI runs the same command on a pull request once it is ready for review, on `main` and every Monday. The flows in
`e2e/` are no pull request gate: CI plays them every Monday and when someone starts the workflow by hand. It runs on `ubuntu-latest` unless the repository variable `CI_RUNNER` names other runner labels as JSON.

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
