# Security policy

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose credentials, execute code through a plugin, bypass report redaction, or compromise a system running the framework.

Use GitHub's private vulnerability reporting feature when it is enabled for the repository. Otherwise, contact the repository maintainer privately and include:

- the affected version or commit;
- reproduction steps;
- expected and observed behaviour;
- impact;
- a suggested mitigation, when available.

Do not include real credentials, private customer data, or attack evidence from a system you are not authorised to test.

## Supported versions

The project is currently in alpha. Security fixes are applied to the latest version on the default branch.

## Operational safety

- Run only against systems you own or have explicit permission to assess.
- Review external plugins before loading them; plugins run with the permissions of the Python process.
- Use a dedicated test account and least-privileged API keys.
- Do not point the generic HTTP adapter at production without change approval and rate controls.
- Treat SQLite databases and generated reports as sensitive test evidence.
- Inspect reports before publishing; regex redaction is not guaranteed to remove every secret.
