# Globo Vidraçaria

A Django application for a glazing business, combining a public product and service catalog with customer accounts, quote requests, and an internal operations dashboard.

**[Website](https://comercial-globo-vidracaria-e-construcao.mayezer.com/)** · **[Documentation](docs/README.md)** · **[Architecture](docs/ARCHITECTURE.md)**

## Features

- **Public storefront:** published products and services, contact details, responsive layouts, and light/dark themes.
- **Customer area:** individual/business registration, profile management, email verification, and quote requests.
- **Sales and inventory:** product, material, and service items; server-side pricing; stock deductions on completion and returns on cancellation.
- **Business operations:** daily cash management, monthly reports, expenses, suppliers, employees, payroll, and PDF exports.
- **Management tools:** material calculators, role-based access, request history, and dashboard notifications.

The sales workflow coordinates inventory and cash entries within database transactions. Customer and financial records use protected fields where configured. See the [business workflows](docs/FEATURES.md) and [security implementation](docs/SECURITY_GUIDE.md) for details and limitations.

## Technology

**Python · Django · PostgreSQL · TypeScript · Cloudflare Workers, Containers, and R2**

The application renders HTML on the server and uses JavaScript for interactive forms and calculators. SQLite supports the local demo. [Architecture and dependency versions →](docs/ARCHITECTURE.md)

## Quick start

Requires **Python 3.11+**. Run these commands from the project root on Linux or macOS:

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

| Address | Purpose |
| --- | --- |
| `http://127.0.0.1:8000/` | Public storefront. |
| `http://127.0.0.1:8000/admin/` | Sign in with the administrator account you created. |
| `http://127.0.0.1:8000/painel/` | Open the management dashboard in the same session. |

The setup script creates independent local keys, selects an empty demo database, and disables email delivery. Django reads the exported environment variables; it does not load `.env` automatically. The catalog starts empty until you create and publish products or services.

Use fictional data for the demo and keep the generated keys while using the same database. [Windows setup, initial records, email testing, and local PostgreSQL →](docs/DEVELOPMENT.md)

## Checks

With the local environment active and its variables exported:

```bash
python manage.py check
python manage.py test
python -m unittest discover -s scripts -p 'test_*.py'
```

The GitHub security workflow also checks tracked paths and scans the available history for secrets. [Worker tests and complete validation commands →](docs/DEVELOPMENT.md#tests-and-checks)

## Documentation

| Guide | Purpose |
| --- | --- |
| [Features and workflows](docs/FEATURES.md) | Access roles, business rules, and routes. |
| [Architecture](docs/ARCHITECTURE.md) | Modules, data relationships, and request handling. |
| [Development](docs/DEVELOPMENT.md) | Setup, tests, maintenance, and troubleshooting. |
| [Configuration](docs/CONFIGURATION.md) | Environment variable reference. |
| [Deployment](docs/DEPLOYMENT.md) | Cloudflare and external service setup. |
| [File reference](docs/FILE_GUIDE.md) | Responsibilities of every distributed file. |
| [Security implementation](docs/SECURITY_GUIDE.md) | Safeguards and data handling. |
| [Security operations](SECURITY_DEPLOYMENT.md) | Key rotation, backups, migrations, and rollback. |
| [Source publication](PUBLICATION.md) | Preparing a public copy without company data. |

## Support and security

For setup problems, see [troubleshooting](docs/DEVELOPMENT.md#troubleshooting). Follow [SECURITY.md](SECURITY.md) to report vulnerabilities privately.

Keep databases, uploads, credentials, and production backups out of the public repository. The export tool includes the source code, documentation, and approved layout assets.

## Author

Mayezer S. de Souza.
