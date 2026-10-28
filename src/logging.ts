export function sanitizedErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return message
    .replace(/\/confirmar-email\/[^/?\s]+/giu, "/confirmar-email/[redacted]")
    .replace(/([?&](?:token|key|secret)=)[^&\s]+/giu, "$1[redacted]")
    .replace(/(bearer\s+)[a-z0-9._~-]+/giu, "$1[redacted]")
    .slice(0, 500);
}
