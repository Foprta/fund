export type WorkerEnv = {
  LUNA_API_URL: string;
  ADMIN_SECRET?: string;
};

export function lunaApiUrl(env?: Partial<WorkerEnv>): string {
  const url =
    env?.LUNA_API_URL ??
    (typeof process !== "undefined" ? process.env.LUNA_API_URL : undefined);
  if (!url) {
    throw new Error("LUNA_API_URL is not configured");
  }
  return url.replace(/\/$/, "");
}

export function adminSecret(env?: Partial<WorkerEnv>): string | undefined {
  return (
    env?.ADMIN_SECRET ??
    (typeof process !== "undefined" ? process.env.ADMIN_SECRET : undefined)
  );
}
