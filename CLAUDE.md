# caldart-proto

## GitHub credentials: this repo is always `astrocfi`

The machine's default GitHub account is `rfrenchseti`. This repo overrides that.
It is wired up already — **run `git` and `gh` normally, with no prefix.**

- `git` — repo-local credential helper reads `~/.git-credentials.astrocfi`
  (the inherited global `credential.helper=store` is cleared by an empty entry
  ahead of it). Commits use `user.email=rfrench@rfrench.org`.
- `gh` — `~/bin/gh` wraps the real `/usr/bin/gh`: it reads
  `git config --get gh.account` and injects `GH_TOKEN` for that account from gh's
  keyring. This repo sets `gh.account = astrocfi`.

Do **not** prefix commands with `GH_TOKEN=...`, and do **not** run
`gh auth switch` — that changes the global default and breaks other repos.
`gh auth status` intentionally still reports `rfrenchseti` as the *active*
account; that is expected and does not affect this repo.
