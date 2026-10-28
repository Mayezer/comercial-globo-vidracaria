import { Container, ContainerProxy, getContainer } from "@cloudflare/containers";
import { enforceSensitivePostRateLimit } from "./rate-limit.ts";
import { sanitizedErrorMessage } from "./logging.ts";

export { ContainerProxy };

const MEDIA_PREFIX = "/media/";
const MEDIA_CONTENT_TYPES = new Map([
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".png", "image/png"],
  [".webp", "image/webp"],
]);

function optionalGoogleVerification(env: Env): string | undefined {
  // Optional secrets are intentionally absent from wrangler.jsonc and therefore from typegen.
  return (env as Env & { GOOGLE_SITE_VERIFICATION?: string }).GOOGLE_SITE_VERIFICATION;
}

function mediaContentType(key: string): string | null {
  const filename = key.split("/").at(-1)?.toLowerCase() ?? "";
  const extensionIndex = filename.lastIndexOf(".");
  return extensionIndex === -1
    ? null
    : (MEDIA_CONTENT_TYPES.get(filename.slice(extensionIndex)) ?? null);
}

function mediaKeyFromPath(pathname: string, prefix = "/"): string | null {
  if (!pathname.startsWith(prefix)) {
    return null;
  }

  try {
    const key = decodeURIComponent(pathname.slice(prefix.length)).replaceAll("\\", "/");
    if (
      !key ||
      key.length > 1024 ||
      key.startsWith("/") ||
      /[\u0000-\u001f\u007f]/u.test(key) ||
      key.split("/").some((segment) => !segment || segment === "." || segment === "..") ||
      !mediaContentType(key)
    ) {
      return null;
    }
    return key;
  } catch {
    return null;
  }
}

function objectHeaders(object: R2Object, key: string): Headers {
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("content-type", mediaContentType(key) ?? "application/octet-stream");
  headers.set("etag", object.httpEtag);
  headers.set("content-length", String(object.size));
  headers.set("x-content-type-options", "nosniff");
  headers.set("cross-origin-resource-policy", "same-origin");
  headers.set("content-security-policy", "default-src 'none'; sandbox");
  if (!headers.has("cache-control")) {
    headers.set("cache-control", "public, max-age=3600");
  }
  return headers;
}

async function servePublicMedia(
  request: Request,
  env: Pick<Env, "MEDIA_BUCKET">,
): Promise<Response> {
  const key = mediaKeyFromPath(new URL(request.url).pathname, MEDIA_PREFIX);
  if (!key || (request.method !== "GET" && request.method !== "HEAD")) {
    return new Response("Not found", { status: 404 });
  }

  if (request.method === "HEAD") {
    const object = await env.MEDIA_BUCKET.head(key);
    return object
      ? new Response(null, { status: 200, headers: objectHeaders(object, key) })
      : new Response("Not found", { status: 404 });
  }

  const object = await env.MEDIA_BUCKET.get(key);
  return object
    ? new Response(object.body, { status: 200, headers: objectHeaders(object, key) })
    : new Response("Not found", { status: 404 });
}

export class DjangoContainer extends Container<Env> {
  defaultPort = 8080;
  requiredPorts = [8080];
  sleepAfter = "10m";
  enableInternet = true;
  envVars = {
    DATABASE_URL: this.env.DATABASE_URL,
    DEFAULT_FROM_EMAIL: this.env.DEFAULT_FROM_EMAIL,
    DJANGO_ALLOWED_HOSTS: this.env.DJANGO_ALLOWED_HOSTS,
    DJANGO_CSRF_TRUSTED_ORIGINS: this.env.DJANGO_CSRF_TRUSTED_ORIGINS,
    DJANGO_DEBUG: this.env.DJANGO_DEBUG,
    DJANGO_SECRET_KEY: this.env.DJANGO_SECRET_KEY,
    DJANGO_SECURE_SSL_REDIRECT: this.env.DJANGO_SECURE_SSL_REDIRECT,
    DJANGO_SECURE_HSTS_SECONDS: this.env.DJANGO_SECURE_HSTS_SECONDS,
    FIELD_ENCRYPTION_ACTIVE_KEY: this.env.FIELD_ENCRYPTION_ACTIVE_KEY,
    FIELD_ENCRYPTION_KEYS: this.env.FIELD_ENCRYPTION_KEYS,
    FIELD_HASH_KEY: this.env.FIELD_HASH_KEY,
    PUBLIC_SITE_URL: this.env.PUBLIC_SITE_URL,
    CORS_ALLOWED_ORIGINS: this.env.CORS_ALLOWED_ORIGINS,
    EMAIL_BACKEND: this.env.EMAIL_BACKEND,
    EMAIL_DELIVERY_ENABLED: this.env.EMAIL_DELIVERY_ENABLED,
    EMAIL_HOST: this.env.EMAIL_HOST,
    EMAIL_HOST_PASSWORD: this.env.RESEND_API_KEY,
    EMAIL_HOST_USER: this.env.EMAIL_HOST_USER,
    EMAIL_PORT: this.env.EMAIL_PORT,
    EMAIL_TIMEOUT: this.env.EMAIL_TIMEOUT,
    EMAIL_USE_TLS: this.env.EMAIL_USE_TLS,
    MEDIA_STORAGE_ENDPOINT: this.env.MEDIA_STORAGE_ENDPOINT,
    POSTGRES_CONN_MAX_AGE: this.env.POSTGRES_CONN_MAX_AGE,
    ...(optionalGoogleVerification(this.env)
      ? { GOOGLE_SITE_VERIFICATION: optionalGoogleVerification(this.env) }
      : {}),
  };
}

DjangoContainer.outboundByHost = {
  "media.internal": async (request, env) => {
    const key = mediaKeyFromPath(new URL(request.url).pathname);
    if (!key) {
      return new Response("Invalid media key", { status: 400 });
    }

    if (request.method === "PUT") {
      if (!request.body) {
        return new Response("Missing body", { status: 400 });
      }
      await env.MEDIA_BUCKET.put(key, request.body, {
        httpMetadata: {
          contentType: mediaContentType(key) ?? "application/octet-stream",
        },
      });
      return new Response(null, { status: 204 });
    }

    if (request.method === "DELETE") {
      await env.MEDIA_BUCKET.delete(key);
      return new Response(null, { status: 204 });
    }

    if (request.method === "HEAD") {
      const object = await env.MEDIA_BUCKET.head(key);
      return object
        ? new Response(null, { status: 200, headers: objectHeaders(object, key) })
        : new Response("Not found", { status: 404 });
    }

    if (request.method === "GET") {
      const object = await env.MEDIA_BUCKET.get(key);
      return object
        ? new Response(object.body, { status: 200, headers: objectHeaders(object, key) })
        : new Response("Not found", { status: 404 });
    }

    return new Response("Method not allowed", { status: 405 });
  },
};

// Wrangler 4.125 generates Container namespaces without their exported class generic.
type WorkerEnv = Omit<Env, "DJANGO_CONTAINER"> & {
  DJANGO_CONTAINER: DurableObjectNamespace<DjangoContainer>;
};

export default {
  async fetch(request: Request, env: WorkerEnv): Promise<Response> {
    const url = new URL(request.url);

    try {
      if (url.protocol !== "https:") {
        url.protocol = "https:";
        return Response.redirect(url.toString(), 308);
      }

      const rateLimitResponse = await enforceSensitivePostRateLimit(request, url, env);
      if (rateLimitResponse) {
        return rateLimitResponse;
      }

      if (url.pathname.startsWith(MEDIA_PREFIX)) {
        return await servePublicMedia(request, env);
      }

      const container = getContainer(env.DJANGO_CONTAINER, "production");
      await container.startAndWaitForPorts();

      const headers = new Headers(request.headers);
      headers.set("x-forwarded-host", url.host);
      headers.set("x-forwarded-proto", "https");

      return await container.fetch(new Request(request, { headers }));
    } catch (error) {
      console.error(
        JSON.stringify({
          message: "request failed",
          error: sanitizedErrorMessage(error),
          method: request.method,
          path: url.pathname.startsWith("/confirmar-email/")
            ? "/confirmar-email/[redacted]/"
            : url.pathname,
        }),
      );
      return new Response("Serviço temporariamente indisponível.", { status: 503 });
    }
  },
} satisfies ExportedHandler<WorkerEnv>;
