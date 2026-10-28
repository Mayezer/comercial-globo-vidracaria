# Security operations runbook

[Project README](README.md) · [Deployment guide](docs/DEPLOYMENT.md) · [Security implementation](docs/SECURITY_GUIDE.md)

This runbook describes controls prepared in the source code and procedures for
operating them. Deployment, production data migrations, and changes to Cloudflare
or Google accounts require the appropriate access and operational authorization.

## Architecture and security decisions

- Authentication uses Django sessions and CSRF protection. JWT is not part of the current architecture.
- Email verification tokens are signed by Django, expire after 24 hours, are bound to an email fingerprint, and cannot be reused after verification.
- Worker limits are configured per IP and route: 20 POSTs/minute for login, registration, and administrator login; 3 POSTs/minute for verification resends.
- Django adds persistent identifier-based lockout in PostgreSQL. Normalized identifiers are stored as HMACs, customer and administrator scopes are separate, delays grow after further failures, old state expires, and successful login clears it.
- CORS is closed by default. Configured `CORS_ALLOWED_ORIGINS` apply only to read-only public pages using `GET`, `HEAD`, and `OPTIONS`. Dashboard, profile, quote, and administration routes do not receive CORS access headers. Credentialed CORS is not enabled.
- The Django ORM remains the application's SQL interface. Encrypted-field lookups use exact HMAC indexes and do not interpolate input into SQL.
- Worker and Django container log formatters redact sensitive patterns such as verification tokens, Bearer credentials, secret parameters, document numbers, and email addresses before emitting messages.

## Secrets and environment variables

Required production secrets:

- `DJANGO_SECRET_KEY`;
- `DATABASE_URL`;
- `RESEND_API_KEY`;
- `FIELD_ENCRYPTION_KEYS`, in `v1:<32-byte-base64url-key>` format, with additional versions separated by commas;
- `FIELD_HASH_KEY`, an independent 32-byte Base64 URL-safe key.

Configuration values:

- `FIELD_ENCRYPTION_ACTIVE_KEY=v1`;
- `PUBLIC_SITE_URL=https://comercial-globo-vidracaria-e-construcao.mayezer.com`;
- `DJANGO_CSRF_TRUSTED_ORIGINS` must contain the production HTTPS origin;
- leave `CORS_ALLOWED_ORIGINS` empty unless a cross-origin consumer is required;
- provide optional `GOOGLE_SITE_VERIFICATION` through the environment or provider configuration rather than hardcoding it;
- `AUTH_LOCKOUT_THRESHOLD`, `AUTH_LOCKOUT_BASE_SECONDS`, `AUTH_LOCKOUT_MAX_SECONDS`, and `AUTH_LOCKOUT_RESET_SECONDS` control identifier-based lockout.

Generate the encryption and HMAC keys independently in a secure terminal. This
example generates new key material without writing it to a file:

```powershell
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Do not reuse one key for both purposes or save the output in Git, the database, or logs.

## Encryption and key rotation

Recoverable values use AES-256-GCM with a random nonce, authenticated model/field
context, and a version prefix. Protected fields cover CPF/CNPJ, email, phone,
address, personal names, and salaries in profiles, quote snapshots, employees,
suppliers, payroll, sales, and settings. Searchable or unique values have separate
HMAC columns. Passwords remain exclusively protected by Django's password hashing.

To rotate recoverable-data encryption keys:

1. Keep the old key in `FIELD_ENCRYPTION_KEYS` and add the new version.
2. Set `FIELD_ENCRYPTION_ACTIVE_KEY` to the new version.
3. Verify that existing records remain readable.
4. Run `python manage.py rotate_sensitive_data` first to obtain the record count.
5. After a backup and within a maintenance window, run `python manage.py rotate_sensitive_data --apply`.
6. Validate samples. Remove an old key only after confirming that no ciphertext using it remains in the active database or retained backups.

## Backup, migration, and rollback

Before deployment:

1. Create a consistent PostgreSQL backup, for example in PowerShell:
   `pg_dump --format=custom --file=before-encryption.dump "$env:DATABASE_URL"`.
2. Test restoring the backup into an isolated instance.
3. Record the image/Worker version and pause writes during migration.
4. Configure all required secrets before starting the new container.
5. Run `python manage.py migrate --plan`, then `python manage.py migrate --noinput`
   during the approved maintenance window.
6. Validate login, registration, verification, profiles, quotes, dashboard, sales,
   PDFs, and uploads before allowing writes again.

The data migrations expand columns, encrypt values, and create HMAC indexes inside
a transaction before unique indexes become mandatory. To roll back the code and
schema, keep the keys available, pause writes, and use this order before starting
the older image:

```powershell
python manage.py migrate accounts 0004
python manage.py migrate dashboard 0003
python manage.py migrate sales 0002
python manage.py migrate accounts 0003
```

Reversing `accounts.0005` decrypts fields and restores legacy user identifiers
before reducing column sizes. If a step fails, retain the keys and restore the
validated backup and previous application version.

## SEO and external service checks

- The application generates `sitemap.xml`, `robots.txt`, and `llms.txt` with absolute HTTPS URLs.
- The origin `robots.txt` responds with HTTP 200 and includes a `Sitemap` directive. If Cloudflare-managed robots are enabled, confirm that origin content is included in the final response after deployment.
- Previous deployment notes reported a `google-site-verification` DNS record for `mayezer.com`. Reconfirm the correct Search Console property, verification, and submission of `https://comercial-globo-vidracaria-e-construcao.mayezer.com/sitemap.xml`.
- A previous local Cloudflare inspection could not confirm managed rules, the Cloudflare Managed Ruleset, OWASP Core Ruleset, custom rules, Skip exceptions, or events because CLI authentication had expired. Authenticate with read-only access and inspect their current state before proposing changes.
- Start any proposed login/admin WAF rule in `Log` or `Managed Challenge`, observe false positives, and obtain authorization before stronger enforcement.

These notes describe checks to perform; they do not attest to the current state of external accounts.

## Operational limitations

- Photos and uploads in R2 rely on provider encryption and controls; they do not receive application field encryption. The Worker's public media path does not check a Django customer session.
- Operational sale values, including items, subtotal, discounts, payment, and total, and general expense amounts remain numeric columns for calculations and reconciliation. Avoid personal data in those values. Cash-entry amounts, salaries, and financial snapshots tied to people use protected fields.
- Cash totals are computed after application-side decryption. Monitor performance and add pagination or archiving if transaction volume grows.
- `FIELD_HASH_KEY` must remain stable. Rotating it requires a planned migration to recompute all HMAC indexes and revalidate uniqueness; the automatic rotation command changes only recoverable-data encryption.
- Free-text fields can contain personal information entered by users. Primary sensitive profile, quote, payroll, supplier, and sale text fields are protected, but data minimization remains an operational practice.
- Worker rate limiting is local to the point of presence and permissive by design. Persistent PostgreSQL HMAC-based lockout complements it against distributed attempts.
