<!-- Title: `type(scope): sentence` saying what changes. It becomes the squash commit's subject. -->

## What and why

A few lines. Name the shortcomings of the approach too.

## Reproduced on

For a fix: the commit, the command or e2e flow, and what it showed before the change. `Not run: <why>` is allowed. A batch gives one line per `Fixes #N`. Delete this section when the change fixes nothing.

## Proof on this head

The command or e2e flow run on this branch's last commit, and what it showed. `Not run: <why>` is allowed. A batch gives one line per `Fixes #N`.

- [ ] `backend/openapi.json` is current: the OpenAPI hook passed and left no diff.
- [ ] A revision that drops or rewrites data does so on purpose. Migrations only go forward, and a mistake is fixed by the next revision.

## How verified

Which CI lanes cover the change (`Hooks`, `Image build`, `End-to-end flows`), plus what was done by hand: a request against the running stack, a second stack, a restore drill. Say what was not checked, and why.

## Flow

For a change to a flow across three or more parts, a Mermaid diagram. Delete this section otherwise.

## Follow-ups

Issue links only.

Fixes #
