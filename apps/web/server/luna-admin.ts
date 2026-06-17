import type { Context } from "hono";
import { adminSecret, lunaApiUrl, type WorkerEnv } from "@/lib/env";

type AppEnv = { Bindings: WorkerEnv };

export async function handleAdminSync(c: Context<AppEnv>) {
  const secret = adminSecret(c.env);
  if (!secret) {
    return c.json({ error: "ADMIN_SECRET не настроен на сервере" }, 500);
  }

  const body = (await c.req.json().catch(() => ({}))) as {
    admin_secret?: string;
  };
  if (body.admin_secret !== secret) {
    return c.json({ error: "Неверный секрет" }, 401);
  }

  const apiUrl = lunaApiUrl(c.env);
  const upstream = await fetch(`${apiUrl}/admin/jobs/sync`, {
    method: "POST",
    headers: { "X-Admin-Secret": secret },
  });

  const text = await upstream.text();
  if (!upstream.ok) {
    return c.json(
      { error: `Ошибка sync ${upstream.status}`, detail: text.slice(0, 500) },
      upstream.status as 400,
    );
  }

  try {
    return c.json(JSON.parse(text));
  } catch {
    return c.json({ raw: text });
  }
}
