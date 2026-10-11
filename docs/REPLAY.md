# Clean-checkout replay

The source dataset is included in the checkout. Rebuilding the study requires no network after installing the pinned dependencies. Use Python 3.11 and the versions in requirements.lock; the local recorded runtime is in outputs/provenance.json.

Replay procedure:

1. Clone this local repository into a new directory with `git clone --no-hardlinks`.
2. From the clean checkout, run the prepared environment's Python with `-m frontier.study`.
3. Verify every output against the committed outputs/SHA256SUMS.
4. Run scripts/verify.py and verify the checkout has no tracked changes.

Do not infer a cross-platform byte identity guarantee from the local receipt. Different numerical libraries or architectures can alter floating-point results. CI checks the committed outputs and small fixtures without networking during the checks; it does not perform the full statistical replay.

## Verified local receipt

Verified 2026-10-11 02:36:02 PDT.

- Replayed source commit: `00c225f3d40918ab3925fafa4089847774c84f36`.
- Clean clone: `work-tmp/clean-replay`, created with `git clone --no-hardlinks . work-tmp/clean-replay`.
- Runtime: the pinned environment in `work-tmp/venv`, Python 3.11; exact package versions in outputs/provenance.json.
- Full build: exit 0. The module ran through runpy with socket connect, connection creation and address resolution patched to reject networking.
- Checksum verification: exit 0. All 17 generated artifact hashes and both frozen input hashes matched the committed values, including the five-page PDF and static page.
- Clean replay checkout: `git diff --exit-code` returned 0; `git status --porcelain` was empty.
- Lint: exit 0. Formatting: exit 0. Types: exit 0. Fixture tests: exit 0, 23 passed. Frozen-artifact verification: exit 0.
- Hosted CI is configured but has not run. No repository was created remotely and no commit was pushed.

Replay logs remain outside the tracked release package in research/. The output checksum manifest SHA-256 is `acaf5b6b9c0183087548916c387b810a6d939fd81e3953ee222c3fb30acfc630`.

