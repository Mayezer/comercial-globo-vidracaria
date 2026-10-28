import assert from "node:assert/strict";
import test from "node:test";

import {
  enforceSensitivePostRateLimit,
  type RateLimitEnv,
} from "./rate-limit.ts";
import { sanitizedErrorMessage } from "./logging.ts";

class MemoryLimiter {
  readonly counts = new Map<string, number>();
  readonly limitValue: number;

  constructor(limitValue: number) {
    this.limitValue = limitValue;
  }

  async limit({ key }: { key: string }): Promise<{ success: boolean }> {
    const count = (this.counts.get(key) ?? 0) + 1;
    this.counts.set(key, count);
    return { success: count <= this.limitValue };
  }
}

function request(path: string, ip: string, method = "POST"): Request {
  return new Request(`https://example.test${path}`, {
    method,
    headers: { "cf-connecting-ip": ip },
  });
}

test("limita autenticação por IP e rota sem misturar IPs", async () => {
  const auth = new MemoryLimiter(20);
  const email = new MemoryLimiter(3);
  const env: RateLimitEnv = { AUTH_RATE_LIMITER: auth, EMAIL_RATE_LIMITER: email };

  for (let index = 0; index < 20; index += 1) {
    const current = request("/entrar/", "203.0.113.10");
    assert.equal(await enforceSensitivePostRateLimit(current, new URL(current.url), env), null);
  }
  const blocked = request("/entrar/", "203.0.113.10");
  assert.equal(
    (await enforceSensitivePostRateLimit(blocked, new URL(blocked.url), env))?.status,
    429,
  );
  const otherIp = request("/entrar/", "203.0.113.11");
  assert.equal(await enforceSensitivePostRateLimit(otherIp, new URL(otherIp.url), env), null);
});

test("mantém limites separados para login administrativo e reenvio", async () => {
  const auth = new MemoryLimiter(1);
  const email = new MemoryLimiter(1);
  const env: RateLimitEnv = { AUTH_RATE_LIMITER: auth, EMAIL_RATE_LIMITER: email };

  const customer = request("/entrar/", "203.0.113.20");
  const admin = request("/admin/login/", "203.0.113.20");
  const resend = request("/perfil/reenviar-confirmacao/", "203.0.113.20");
  assert.equal(await enforceSensitivePostRateLimit(customer, new URL(customer.url), env), null);
  assert.equal(await enforceSensitivePostRateLimit(admin, new URL(admin.url), env), null);
  assert.equal(await enforceSensitivePostRateLimit(resend, new URL(resend.url), env), null);
  assert.equal(
    (await enforceSensitivePostRateLimit(resend, new URL(resend.url), env))?.status,
    429,
  );
});

test("ignora GET e rotas fora da lista sensível", async () => {
  const env: RateLimitEnv = {
    AUTH_RATE_LIMITER: new MemoryLimiter(0),
    EMAIL_RATE_LIMITER: new MemoryLimiter(0),
  };
  const getLogin = request("/entrar/", "203.0.113.30", "GET");
  const otherPost = request("/produtos/", "203.0.113.30");
  assert.equal(await enforceSensitivePostRateLimit(getLogin, new URL(getLogin.url), env), null);
  assert.equal(await enforceSensitivePostRateLimit(otherPost, new URL(otherPost.url), env), null);
});

test("remove tokens de mensagens de erro antes de registrar", () => {
  const sanitized = sanitizedErrorMessage(
    new Error(
      "falha em /confirmar-email/token-assinado-secreto/?token=outro-segredo Authorization: Bearer abc.def.ghi",
    ),
  );
  assert.doesNotMatch(sanitized, /token-assinado-secreto|outro-segredo|abc\.def\.ghi/u);
  assert.match(sanitized, /\[redacted\]/u);
});
