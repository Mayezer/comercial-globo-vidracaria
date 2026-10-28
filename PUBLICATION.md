# Publishing the source code

[Project README](README.md) · [Documentation index](docs/README.md)

This guide describes how to publish a source copy while keeping company data and
private history separate. Publishing source code and deploying a running website
are separate operations.

## Publication safeguards

- `.gitignore` excludes secrets, databases, uploads, backups, logs, and local dependencies.
- `.dockerignore` allows only the files required by Django in the image build context.
- `.env.example` describes a local demo with an empty database and email delivery disabled.
- `scripts/create_local_env.py` generates independent keys, does not print them, and refuses to overwrite existing files.
- Local PostgreSQL requires a configured password and binds only to `127.0.0.1`.
- The `Secret scanning` workflow checks tracked paths, runs publication tests, and scans the available history with read-only repository permissions.
- `.gitleaks.toml` extends the default rules and allows only four exact fictional password values in reviewed test files.

These safeguards do not remove files from earlier commits. A clean automated scan
also does not replace a review of personal information and images.

## Recommended workflow: a new public copy

1. Run `python scripts/export_public_source.py`. If the destination exists, use a
   new name, for example:

   ```bash
   python scripts/export_public_source.py --output dist/globo-vidracaria-publico-atualizado.zip
   ```

2. Extract the ZIP into another directory. The exporter uses an explicit list of
   directories, files, and extensions, including `docs/`. Review that list when
   adding resources. Only the two reviewed layout images are included.
3. Review the extracted files, then run the [official Gitleaks scanner](https://github.com/gitleaks/gitleaks)
   from the extracted project root:

   ```bash
   gitleaks dir . --config .gitleaks.toml --redact
   ```

   Investigate findings without publishing reports containing secret values.
4. Create a new GitHub repository, initially private so the first upload can be
   reviewed. Initialize Git only in the extracted directory and push that copy.
   The original database and uploads remain in the original local directory.
5. Wait for the `Secret scanning` workflow to finish. Review files, images, and
   workflow output before changing visibility.
6. Open **Settings → General → Danger Zone → Change visibility** and select **Public**.
7. Under **Settings → Security**, enable available secret scanning, push protection,
   Dependabot alerts, and private vulnerability reporting options.

The ZIP excludes `.git`, databases, actual `.env` files, uploads, and logs. Use
dedicated services and credentials for any demo deployment.

## Publishing an existing repository

Review every commit, branch, and tag before changing visibility. Even a single
commit may contain a database, credentials, or personal information. In a complete
clone, inspect the tracked files and scan the history:

```bash
git ls-files
gitleaks git . --config .gitleaks.toml --redact --log-opts="--all"
```

Pay particular attention to `db.sqlite3`, `media/`, `.env`, backups, and logs. A new
`.gitignore` does not untrack existing files or erase their earlier versions.

If a credential has been compromised, revoke or rotate it with its provider.
Data-encryption keys require the rotation procedure in
[SECURITY_DEPLOYMENT.md](SECURITY_DEPLOYMENT.md) to preserve access to existing data.
Rewriting history requires backups and coordination with everyone using the
repository. A new public copy lets the original private history remain intact.

Review the resulting package before each upload: it reflects the source files
present at export time. The full file inventory is in
[docs/FILE_GUIDE.md](docs/FILE_GUIDE.md).

## References

- [GitHub repository visibility](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
