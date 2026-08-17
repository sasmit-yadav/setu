# Project rules for Claude

These are binding instructions for this repository, not suggestions.

## Never attribute commits to Claude/AI

**Every commit message in this repository must contain no reference to
Claude, Anthropic, or AI authorship of any kind.** Specifically:

- **Never** add a `Co-Authored-By: Claude ...` trailer, or any
  `Co-Authored-By` line referencing an AI, to a commit message.
- **Never** mention "Claude", "AI", "Anthropic", or similar in a commit
  subject or body.
- Commit messages should read as if written by the human developer alone —
  because authorship of the work is the human's, not a tool's.

This applies to every commit, in every branch, from this point forward, with
no exceptions and no "just this once." If a commit template, hook, or default
CLI behavior would add such a trailer automatically, override or strip it
before the commit is made — do not rely on remembering to remove it after
the fact.

**History note:** commits made before this rule existed
(`ef2d366`/`fe0c1b2`/`326a98e`, since rewritten to `6fe169e`/`134836b`/`dc1aad6`)
had the trailer stripped via `git filter-branch` on 17 Aug 2026, while the
repo had no remote and nothing had been pushed. If this repo ever gains
collaborators or a remote before you read this, do **not** casually rewrite
shared history again — filter-branch/rebase on published commits requires
everyone's coordination first.

## Secrets

Never write a real credential, token, or key into any file that is not
`.env` (or another `.gitignore`d path). `.env.example` and all committed
docs get placeholders only, never the real value — even if a real value was
given directly in chat.
