import { z } from "zod";

export const chatRequestSchema = z.object({
  message: z.string().min(1).max(4000),
  conversation_id: z.string().uuid().optional(),
});

export type ChatRequest = z.infer<typeof chatRequestSchema>;

export type LunaSseEvent =
  | { type: "token"; content: string }
  | { type: "done"; conversation_id?: string };

export function parseLunaSseLine(line: string): LunaSseEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data: ")) {
    return null;
  }
  try {
    const payload = JSON.parse(trimmed.slice(6)) as {
      type?: string;
      content?: string;
      conversation_id?: string;
    };
    if (payload.type === "token" && typeof payload.content === "string") {
      return { type: "token", content: payload.content };
    }
    if (payload.type === "done") {
      return {
        type: "done",
        conversation_id: payload.conversation_id,
      };
    }
  } catch {
    return null;
  }
  return null;
}

export function extractTokenText(chunk: string, buffer: string): {
  text: string;
  rest: string;
  conversationId?: string;
  done: boolean;
} {
  let rest = buffer + chunk;
  let text = "";
  let conversationId: string | undefined;
  let done = false;

  const lines = rest.split("\n");
  rest = lines.pop() ?? "";

  for (const line of lines) {
    const event = parseLunaSseLine(line);
    if (!event) continue;
    if (event.type === "token") {
      text += event.content;
    } else if (event.type === "done") {
      done = true;
      conversationId = event.conversation_id;
    }
  }

  return { text, rest, conversationId, done };
}
