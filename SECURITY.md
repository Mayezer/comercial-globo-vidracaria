# Security policy

To report a vulnerability privately, use **Security → Report a vulnerability** on
GitHub when that option is enabled. Do not post credentials, personal information,
exploit details, or database copies in public issues. If private reporting is not
available, ask the maintainer for a private contact channel without publishing the
technical details.

The public repository contains source code and example configuration. Databases,
uploads, backups, and production secrets must remain outside it. Constants used as
keys or passwords in automated tests are artificial fixtures and must never be
used in production.

- [Security implementation](docs/SECURITY_GUIDE.md): safeguards and their scope.
- [Security operations runbook](SECURITY_DEPLOYMENT.md): deployment and key rotation.
- [Source publication](PUBLICATION.md): reviewing and exporting a public copy.
