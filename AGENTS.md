# starter-app

Read `BACKEND-API.md` before writing or reviewing code here. It is the shape the code follows. `README.md` says how
to run the app and its checks.

## Pull requests

- Every change reaches `main` through a pull request. The `main` ruleset refuses a direct push.
- The title is `type(scope): sentence`, with a type from `feat fix refactor style chore docs test perf ci build
  revert` and at most one lowercase scope. It becomes the squash commit's subject. The `Conventional title` check
  and the commit-msg hook read the one pattern in `.github/workflows/pr-title.yml`.
- Fill in the pull request template. Each issue gets its own line, `Fixes #N` or `Part of #N`, and the check
  refuses a number that is not an issue of this repository.
- A batch of related changes is one branch from `main` and one pull request, however many people or agents work on
  it. A part worked on separately is merged into the batch's branch and gets no pull request of its own. Every issue
  the batch closes has its own `Fixes #N` line.
- Open a draft while the work is in progress. CI runs no lane on a draft and starts them when the pull request is
  marked ready for review.
- Arm auto-merge once the pull request is ready: `gh pr merge --auto --squash`. GitHub squashes it once `Check` and
  `Conventional title` pass on a branch that is up to date with `main`. Never merge by hand, and never push past a
  red check.
- Leave auto-merge off for a change to a migration, authentication, money or the deploy files. The owner reads
  those before they merge.
- Run `uvx prek run --stage pre-push --all-files` before you push. CI plays the e2e flows; run one by hand when the
  change touches its journey.

## Writing

- A pull request is not done until its docs are. A change to what `README.md`, `BACKEND-API.md`, `e2e/README.md` or
  this file describes edits that text in the same pull request.
- Working notes stay out of the repository: no plan, status write-up, investigation log, report, handoff or dated
  record, whether as a new file, a new folder or a progress section added to an existing document. What a change did
  goes in its commit message and its pull request. What the system does goes in the document that already describes
  that part, edited in place. Writing that fits neither is a note.

## A new repository

Once, after the first push: create the labels the issue forms name, allow only squash merges with auto-merge and
branch deletion, turn on Dependabot alerts and security updates, then apply `.github/rulesets/main.json` as a
ruleset. The ruleset goes last because it refuses a direct push to `main`.
