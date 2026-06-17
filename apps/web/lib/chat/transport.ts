import { TextStreamChatTransport } from "ai";

function lastUserText(
  messages: Array<{ role: string; parts: Array<{ type: string; text?: string }> }>,
): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== "user") continue;
    return m.parts
      .filter((p) => p.type === "text" && p.text)
      .map((p) => p.text)
      .join("");
  }
  return "";
}

export function createLunaChatTransport(conversationId: string | undefined) {
  return new TextStreamChatTransport({
    api: "/api/chat",
    prepareSendMessagesRequest: ({ messages }) => ({
      body: {
        message: lastUserText(messages),
        conversation_id: conversationId,
      },
    }),
  });
}
