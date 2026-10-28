# Development guide

[Project README](../README.md) · [Documentation index](README.md)

Local setup, Windows instructions, testing, maintenance, and troubleshooting.

## Running locally

### Linux or macOS setup

Obtain the source through a clone or ZIP and run the commands from the directory containing `manage.py`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/create_local_env.py

set -a
source .env
set +a

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. To start managing the application, sign in at `http://127.0.0.1:8000/admin/` with the account you created, then open `/painel/` in the same session.

The generator creates `.env` with independent random keys, a `demo.sqlite3` database, and email delivery disabled. It does not print secrets and refuses to overwrite an existing file. Keep these keys as long as you need to read the same encrypted database.

**Django does not load `.env` automatically.** Export the variables in each terminal used to run commands. `.env.example` contains placeholders and serves as a reference; generate your `.env` before starting the application.

### Windows/PowerShell setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/create_local_env.py

Get-Content .env | ForEach-Object {
    if ($_ -match '^([A-Z_][A-Z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py runserver
```

### Initial records

1. Create product categories in Django Admin or through category management on the dashboard's products screen.
2. Create products with prices, stock quantities, and photos; enable their storefront publication option.
3. Create and publish services.
4. Add materials to the calculator, selecting m² or linear meters and the corresponding unit price.
5. Update company details at `/painel/configuracoes/`.
6. Register a fictional customer through the public page to test profiles and quote requests.
7. Explore the sales, cash management, and personnel screens using fictional data.

The installation does not include ready-made administrator credentials, the company's database, or customer uploads.

### Testing email verification without external delivery

In `.env`, keep `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` and set `EMAIL_DELIVERY_ENABLED=True`. Export the variables again and restart the server. The verification link will appear in the terminal.

### Using local PostgreSQL

1. Set `DATABASE_ENGINE=postgresql` in `.env`. Leave `DATABASE_URL` empty to use the local `POSTGRES_*` variables.
2. Check the generated password and database name/username.
3. Export the variables again and run:

```bash
docker compose -f docker-compose.yaml up -d postgres
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Compose starts only PostgreSQL, with a persistent volume and its port bound to `127.0.0.1`. A password is required. An existing SQLite database is not automatically transferred to PostgreSQL. Use PostgreSQL to validate concurrency behavior that depends on row-level locking.

## Tests and checks

With the local environment activated and its variables exported:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
python manage.py test
python -m unittest discover -s scripts -p 'test_*.py'
```

Django tests cover authentication, permissions, quotes, products, services, inventory, sales, finances, encryption, headers, CORS, SEO, and settings. Tests in `scripts/` check key generation, overwrite prevention, and exclusion of private files from exports. The test database is separate from the application's normal database.

For the Worker, with Node.js and pnpm installed:

```bash
pnpm install --frozen-lockfile
pnpm run cf-typegen
pnpm run typecheck
pnpm run test:worker
```

Publication inspection commands must run in a complete Git checkout:

```bash
python scripts/check_public_files.py
gitleaks git . --config .gitleaks.toml --redact --log-opts="--all"
```

The `.github/workflows/secret-scanning.yml` workflow runs path protection checks, publication tests, and Gitleaks on pushes, pull requests, or manual dispatch. The Django and TypeScript checks above are project validation commands; this security workflow does not run the full Django suite.

Use `python manage.py check --deploy` with the **production settings** loaded. `pnpm run check` performs a Worker dry run and requires the corresponding build environment. These commands do not replace integration testing with PostgreSQL and Cloudflare services.

## Maintenance guide

### Project conventions

| File or directory | Role in the workflow |
| --- | --- |
| `models.py` | Entities, relationships, and persistence-related rules. |
| `forms.py` | Validation and transformation of submitted form data. |
| `views.py` | HTTP handling, authorization, and use-case coordination. |
| `services.py` | Reusable business operations; for sales, it centralizes completion and cancellation. |
| `urls.py` | URL-to-view mapping, including namespaces. |
| `admin.py` | Model registration and behavior in Django Admin. |
| `apps.py` | Module configuration and any specific initialization. |
| `templates/` | HTML, layout inheritance, and components rendered by Django. |
| `static/` | Presentation assets maintained in the source code. |
| `migrations/` | Versioned schema evolution and data migrations. |
| `tests.py` and `test_*.py` | Automatically verified behaviors and safeguards. |

### Where to change each behavior

| Requirement | Starting point |
| --- | --- |
| Adjust the storefront cover, navigation, or footer | `showcase/templates/showcase/base.html` and `showcase/templates/showcase/home.html`. |
| Adjust profile/authentication structure and the shared dashboard layout | `templates/base.html`. |
| Change the dashboard menu, notifications, or visual structure | `dashboard/templates/dashboard/base.html`. |
| Modify customer registration, authentication, or validation | `accounts/forms.py`, `accounts/models.py`, `accounts/backends.py`, and `accounts/security.py`. |
| Change quote rules | `dashboard/models.py`, `dashboard/forms.py`, and `dashboard/views.py`. |
| Change sale completion, stock deduction, or refunds | `sales/services.py`; review the sales models and tests alongside the change. |
| Change item calculations | `sales/models.py` and `sales/forms.py`. |
| Change measurement or suggested-price simulations | The material calculator and profit calculator templates. |
| Change cross-cutting security | `app/settings.py`, `app/middleware.py`, `app/crypto.py`, and their corresponding tests. |
| Change container routing, media, or external rate limits | `src/index.ts`, `src/rate-limit.ts`, and `wrangler.jsonc`. |
| Change the public distribution's contents | The explicit list in `scripts/export_public_source.py`, exclusions, and publication tests. |

When adding persisted fields, generate and review the corresponding migration. Preserve transactional financial operations, historical snapshots, and inventory/cash links when changing business workflows. Keep server-side monetary values as `Decimal` and respect the distinction between meters in simulations and millimeters in sale items.

## Troubleshooting

| Symptom | Recommended check |
| --- | --- |
| Errors comparing or encrypting data | Export FIELD_ENCRYPTION_KEYS, FIELD_ENCRYPTION_ACTIVE_KEY, and FIELD_HASH_KEY; check their format and the active version. Preserve the keys used by the existing database. |
| The application tries to connect to PostgreSQL during the demo | Confirm DATABASE_ENGINE=sqlite and an empty DATABASE_URL in the current process environment. |
| Compose requires a password | Generate .env or configure POSTGRES_PASSWORD; the database no longer receives a hardcoded default password. |
| Customer login with email is rejected | Use CPF/CNPJ and a password. For the initial administrator account, sign in through Django Admin using the registered username. |
| The catalog is empty | Create products/services in the active database and enable their storefront publication setting. |
| A new quote request is blocked | Complete the street, neighborhood, and house number and wait four hours after the previous request. |
| Email verification does not appear in the terminal | Use the console backend, enable EMAIL_DELIVERY_ENABLED, and restart the process after exporting the variables. |
| Manifest error or missing static asset | Run collectstatic with the environment configured; the original files must remain in the project's/module's static directories. |
| Upload failure when running locally | Leave MEDIA_STORAGE_ENDPOINT empty. The media.internal host belongs to the container/Worker integration. |
| CSRF error or invalid host | Check the domain, scheme, and port in DJANGO_ALLOWED_HOSTS and DJANGO_CSRF_TRUSTED_ORIGINS. |
| check_public_files cannot read Git | Run it in a Git checkout. A freshly extracted ZIP does not have a Git index yet. |
| The exporter refuses an existing ZIP | Choose a different destination with --output to preserve the previous version. |
| A check flags a tracked database or upload | Review the index and history as described in PUBLICATION.md; adding a name to .gitignore does not erase earlier commits. |
