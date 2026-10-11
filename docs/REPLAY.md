# Clean-checkout replay

The source dataset is included in the checkout. Rebuilding the study requires no network after installing the pinned dependencies. Use Python 3.11 and the versions in requirements.lock; the local recorded runtime is in outputs/provenance.json.

Replay procedure:

1. Clone this local repository into a new directory with `git clone --no-hardlinks`.
2. From the clean checkout, run the prepared environment's Python with `-m frontier.study`.
3. Verify every output against the committed outputs/SHA256SUMS.
4. Run scripts/verify.py and verify the checkout has no tracked changes.

Do not infer a cross-platform byte identity guarantee from the local receipt. Different numerical libraries or architectures can alter floating-point results. CI checks the committed outputs and small fixtures without networking during the checks; it does not perform the full statistical replay.

The verified local replay receipt is appended after the release-candidate commit.
