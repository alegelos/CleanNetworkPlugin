# Working on the CleanNetwork plugin

This repository packages consumer guidance for the Swift and Android SDKs. It
does not contain a new networking runtime. Read README.md before changing the
distribution or installation flow.

- Keep `plugins/cleannetwork/skills/ioscleannetwork` and `androidcleannetwork`
  identical to the Git commits pinned in `sources.lock.json`. Fix technical
  guidance upstream, then intentionally update the pins and sync; do not create
  a competing specification in this repository.
- The `cleannetwork` skill handles platform selection and architecture context.
  Preserve existing targets/modules and make presentation conditional on the
  consumer's needs. Use only fictional User/Item examples and example.com URLs.
- Keep manifests, catalogs and references portable. Do not distribute caches,
  credentials, machine paths or symlinks. Keep executable wrapper permissions.
- Keep the Codex and Claude manifests' identity/version/description synchronized.
  The Claude account ZIP has an explicit build-time path projection; preserve
  canonical sources in this repository and record/validate upload transformations.
  Verify the projected examples if their layout changes.
- Plugin version, iOS SDK version and Android SDK version are separate. Do not
  claim a plugin update upgrades a consumer's SDK dependency.
- A GitHub release is not an official directory listing. Track portal status
  separately using docs/PUBLISHING.md; do not claim approval from local checks.
- Keep the plugin instruction-only unless a task explicitly needs more tools.
  Installing it must not execute project changes or require service credentials.
- Do not install into the developer's real Codex/Claude profile as a test. The
  checks use temporary configuration directories supplied only to child processes.

Checks from this repository:

```sh
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 scripts/build_plugin.py
python3 scripts/verify_codex.py --work-dir .unlazy/codex-verification
python3 scripts/verify_claude.py --work-dir .unlazy/claude-verification
```

The Codex check requires a CLI with `plugin marketplace add`, `plugin add`, and
`plugin list --json`. It tests an extracted distribution outside this checkout.
For routing changes, independently exercise a single-module app and a library
without UI. For bundled guide/code changes, run the SDK's documented consumer
checks and review its API/version claims. Report actual results and limitations.
Claude checks need `plugin validate --strict --json`, `plugin list --json`,
`plugin details` and marketplace/install/update/uninstall commands. CLI validation
does not certify acceptance by the account upload service or a desktop UI flow.
