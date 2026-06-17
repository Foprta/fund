import type { Context } from "hono";
import { chatRequestSchema, extractTokenText } from "@/lib/domain/chat";
import { lunaApiUrl, type WorkerEnv } from "@/lib/env";

type AppEnv = { Bindings: WorkerEnv };

export async function handleLunaChat(c: Context<AppEnv>) {
  const parsed = chatRequestSchema.safeParse(await c.req.json());
  if (!parsed.success) {
    return c.json(
      { error: "Неверный запрос", issues: parsed.error.issues },
      400,
    );
  }

  const { message, conversation_id } = parsed.data;
  const apiUrl = lunaApiUrl(c.env);

  const upstream = await fetch(`${apiUrl}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id }),
    cache: "no-store",
  });

  if (!upstream.ok) {
    const body = await upstream.text();
    return c.json(
      { error: `Ошибка API ${upstream.status}`, detail: body.slice(0, 500) },
      upstream.status as 400,
    );
  }

  const conversationHeader =
    upstream.headers.get("X-Conversation-Id") ?? undefined;

  const encoder = new TextEncoder();
  const reader = upstream.body?.getReader();
  if (!reader) {
    return c.json({ error: "Пустой ответ API" }, 502);
  }

  const decoder = new TextDecoder();
  let sseBuffer = "";

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          const { text, rest, done: streamDone } = extractTokenText(
            chunk,
            sseBuffer,
          );
          sseBuffer = rest;
          if (text) {
            controller.enqueue(encoder.encode(text));
          }
          if (streamDone) break;
        }
        controller.close();
      } catch (err) {
        controller.error(err);
      } finally {
        reader.releaseLock();
      }
    },
  });

  const headers: Record<string, string> = {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-cache",
  };
  if (conversationHeader) {
    headers["X-Conversation-Id"] = conversationHeader;
  }

  return new Response(stream, { status: 200, headers });
}
