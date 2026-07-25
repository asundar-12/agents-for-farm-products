---
name: commit
description: Commit, amend, and push changes in this project's house style — a plain one-line title, then one bullet per changed file. Use when the user asks to commit changes, write a commit message, amend a commit, or push.
---

# Committing changes

Covers three jobs: writing a new commit, amending the last one, and pushing.
Every commit message follows the same house style below.

## Message format

```
<one-line title: what these changes do>

- <file>: <what changed in it, in plain words>
- <file>: <what changed in it, in plain words>
```

### Rules

- **Title**: one short line saying what the change does overall. No prefixes like
  `feat:` or `fix:`. No trailing period.
- **Body**: one bullet per file that changed. Start each bullet with the file's
  name (or short path), then a colon, then what changed.
- **Tone**: simple and direct. Write like you're explaining it to a teammate, not
  writing a spec. Avoid jargon — say "added a page for reviewing the order," not
  "implemented the order-review view component."
- Group truly trivial files (lockfiles, generated config) into one bullet if
  listing each adds no information.
- End the message with the co-author trailer:

  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

## New commit

1. Run `git status` and `git diff --cached` (stage first if needed) to see what
   actually changed in each file.
2. Write the message in the format above.
3. Commit. Only commit when the user has asked you to.

## Amend the last commit

Use when the user wants to fix the most recent commit's message or fold new
changes into it.

1. Check it isn't already pushed: `git status -sb`. If the branch is not ahead of
   its remote, the commit is public — warn the user before rewriting it, since
   amending changes history.
2. Stage any new changes you're folding in.
3. Re-read the full set of changes and rewrite the message in the house style so
   it still describes everything in the commit, not just the new part.
4. `git commit --amend` with the updated message.

## Push

1. Run `git status -sb` to confirm the branch, its remote, and how many commits
   are ahead.
2. Push with `git push`.
3. If the push is rejected because history was rewritten (e.g. after an amend that
   was already public), stop and tell the user — do not force-push unless they
   explicitly ask.
4. Report what went up: the commit range and which commits it covers.
