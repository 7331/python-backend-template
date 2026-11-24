# e2e

End-to-end flows against a real compose stack, run when a change needs them: by hand, or all of them with
`gh workflow run ci.yml --ref <branch>`. CI also plays them all once a week. They are never a pull request gate. These are the rules for a flow.
`BACKEND-API.md` (Verification) says when one is due.

- One flow is one user journey through the public HTTP surface, start to finish, named `<journey>_flow.py`. No file
  per endpoint, operation or query, and no SQL fixtures: they pin the schema and the implementation, so every migration
  breaks them. An upsert, for example, is checked inside the journey that submits twice.
- State comes in through the API, never through SQL inserts. Assertions go through the API too. A `psql` check through
  `docker compose exec`, in a read-only transaction, is allowed only for an invariant the API can't show, such as a row
  really deleted or a role lacking a privilege.
- Shared code lives in modules named by concern (`flow_run.py`, `stack_commands.py`, `http_client.py`,
  `flow_report.py`, `software_passkey.py`), never copied between flows.
- Each flow starts its own stack from `docker-compose.yml` alone (`--file`), under a separate compose project with
  fresh passwords for both database roles and a free local port, and prints one `PASS` or `FAIL` line per assertion.
  `flow_run.py` plays it: a flow passes `play_flow` its name, its extra env lines and the function that walks the
  journey.
- A run always removes its stack and volumes, also after a failure. A cleanup that fails is a `FAIL` line of its own,
  so the exit code is 0 only when every assertion passed and the stack was removed.
- A run keeps its evidence outside the repository, in `<temp directory>/starter-app-e2e/<start time>-<flow>-<id>/`:
  `summary.txt` with the result, every `PASS` and `FAIL` line and the commit played (`-dirty` when the working tree
  differs from it), and `containers.log` with what every container wrote. The last line a flow prints is the folder.
  CI uploads the folders as the `e2e-evidence-attempt-<n>` artifact.
- By hand, a flow is due after a change to its journey, a migration, the compose files or the deploy files. It is never
  a hook. A new flow gets its own step in the `flows` job of `.github/workflows/ci.yml`. A flow that only pinned old
  details gets deleted or rewritten.
- In work split into steps, a step that changes behaviour runs the flows it touches, and the last step runs them once
  more from the base of the work. A failing flow is run on the base first: red there too means the step did not break
  it.

```sh
cd e2e
uv sync
uv run python health_flow.py
uv run python accounts_flow.py
uv run python worker_flow.py
uv run python object_storage_flow.py
```
