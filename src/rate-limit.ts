const AUTH_POST_PATHS = new Set(["/entrar/", "/criar-conta/", "/admin/login/"]);
const EMAIL_POST_PATHS = new Set(["/perfil/reenviar-confirmacao/"]);

export type RateLimitEnv = Pick<Env, "AUTH_RATE_LIMITER" | "EMAIL_RATE_LIMITER">;

export async function enforceSensitivePostRateLimit(
  request: Request,
  url: URL,
  env: RateLimitEnv,
): Promise<Response | null> {
  if (request.method !== "POST") {
    return null;
  }

  const actor = request.headers.get("cf-connecting-ip") ?? "unknown";
  const limiter = AUTH_POST_PATHS.has(url.pathname)
    ? env.AUTH_RATE_LIMITER
    : EMAIL_POST_PATHS.has(url.pathname)
      ? env.EMAIL_RATE_LIMITER
      : null;

  if (!limiter) {
    return null;
  }

  const { success } = await limiter.limit({ key: `${actor}:${url.pathname}` });
  if (success) {
    return null;
  }

  return new Response("Muitas tentativas. Aguarde um minuto e tente novamente.", {
    status: 429,
    headers: {
      "cache-control": "no-store",
      "content-type": "text/plain; charset=utf-8",
      "retry-after": "60",
      "x-content-type-options": "nosniff",
    },
  });
}
