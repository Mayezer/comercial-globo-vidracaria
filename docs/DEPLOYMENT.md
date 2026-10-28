# Deployment guide

[Project README](../README.md) · [Documentation index](README.md)

Cloudflare configuration, external services, provider secrets, and deployment checks.

## Cloudflare deployment

### Existing configuration

`wrangler.jsonc` defines a Worker with a custom domain, a Django container, a Durable Object binding, R2, request limits, and observability. The Durable Object namespace maintains the container reference; Django's business data is persisted in external PostgreSQL.

The container runs Gunicorn on port 8080 with one worker process and four threads. The entrypoint applies migrations before starting the server. The configured Worker uses one container instance and puts it to sleep after ten minutes of inactivity. Static assets are collected during the image build.

### Environment preparation

1. Provide a Cloudflare account with Containers and R2 resources, the configured domain, and Docker for local builds when applicable.
2. Configure PostgreSQL so the container can access it over a TLS connection. The documented deployment uses Neon; the application accepts valid PostgreSQL URLs.
3. Configure the sender and SMTP access in Resend.
4. Review the domain, hosts, CSRF origins, sender, and bindings in `wrangler.jsonc` for the target environment.
5. Back up the data and follow the migration plan in [SECURITY_DEPLOYMENT.md](../SECURITY_DEPLOYMENT.md).

Authenticate and configure the provider secrets:

```bash
pnpm exec wrangler login
pnpm exec wrangler secret put DATABASE_URL
pnpm exec wrangler secret put DJANGO_SECRET_KEY
pnpm exec wrangler secret put RESEND_API_KEY
pnpm exec wrangler secret put FIELD_ENCRYPTION_KEYS
pnpm exec wrangler secret put FIELD_HASH_KEY
```

Run the checks before deploying:

```bash
pnpm run cf-typegen
pnpm run typecheck
pnpm run test:worker
pnpm run check
```

The deployment command is `pnpm run deploy`. Monitor container startup and migrations, then validate navigation, login, registration, quotes, sales, cancellations, PDFs, and uploads in the target environment.

The local demo configuration uses an isolated database and console email. To deploy a browsable demo, use dedicated services and credentials. This source documentation describes the configured architecture; the actual state of DNS, WAF, database, and sender configuration must be checked during deployment.
