"use client";

import { useChat } from "@ai-sdk/react";
import type { UIMessage } from "ai";
import { AlertCircle, MessageSquare, Menu, Plus, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import { Button } from "@/components/ui/button";
import { InputGroupAddon } from "@/components/ui/input-group";
import {
  DEFAULT_THREAD_TITLE,
  deriveThreadTitle,
  emptyThreadStore,
  loadThreadStore,
  type StoredMessage,
  type StoredThread,
  saveThreadStore,
} from "@/lib/chat/storage";
import { createLunaChatTransport } from "@/lib/chat/transport";

function toStoredMessages(messages: UIMessage[]): StoredMessage[] {
  return messages.map((m) => ({
    id: m.id,
    role: m.role === "user" ? "user" : "assistant",
    text: m.parts
      .filter((p) => p.type === "text")
      .map((p) => ("text" in p ? p.text : ""))
      .join(""),
  }));
}

function fromStoredMessages(stored: StoredMessage[]): UIMessage[] {
  return stored.map((s) => ({
    id: s.id,
    role: s.role,
    parts: [{ type: "text" as const, text: s.text }],
  }));
}

function threadSnapshot(thread: StoredThread): string {
  return JSON.stringify({
    title: thread.title,
    messages: thread.messages,
    status: thread.status,
    draftAssistant: thread.draftAssistant,
  });
}

function buildThread(
  conversationId: string,
  messages: UIMessage[],
  status: string,
  titleFallback: string,
): StoredThread {
  const stored = toStoredMessages(messages);
  return {
    id: conversationId,
    title: deriveThreadTitle(stored, titleFallback),
    updatedAt: Date.now(),
    messages: stored,
    status:
      status === "streaming" || status === "submitted" ? "streaming" : "idle",
    draftAssistant:
      status === "streaming"
        ? stored.filter((m) => m.role === "assistant").at(-1)?.text
        : undefined,
  };
}

type ChatSessionProps = {
  conversationId: string;
  initialThread?: StoredThread;
  seedMessage?: string | null;
  onSeedConsumed?: () => void;
  onThreadUpdate?: (thread: StoredThread) => void;
};

function ChatSession({
  conversationId,
  initialThread,
  seedMessage,
  onSeedConsumed,
  onThreadUpdate,
}: ChatSessionProps) {
  const transport = useMemo(
    () => createLunaChatTransport(conversationId),
    [conversationId],
  );

  const initialMessages = useMemo(
    () =>
      initialThread?.messages?.length
        ? fromStoredMessages(initialThread.messages)
        : undefined,
    [initialThread],
  );

  const { messages, sendMessage, status, error } = useChat({
    id: conversationId,
    transport,
    messages: initialMessages,
  });

  const onThreadUpdateRef = useRef(onThreadUpdate);
  onThreadUpdateRef.current = onThreadUpdate;
  const titleFallback = initialThread?.title ?? DEFAULT_THREAD_TITLE;

  useEffect(() => {
    const thread = buildThread(conversationId, messages, status, titleFallback);
    onThreadUpdateRef.current?.(thread);
  }, [conversationId, messages, status, titleFallback]);

  useEffect(() => {
    if (!seedMessage?.trim()) return;
    const text = seedMessage;
    onSeedConsumed?.();
    void sendMessage({ text });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire once per seed
  }, [seedMessage]);

  const handleSubmit = async (msg: { text: string }) => {
    if (!msg.text.trim()) return;
    await sendMessage({ text: msg.text });
  };

  // Show a "thinking" bubble while the request is in flight but the assistant
  // hasn't produced any visible text yet (request submitted, or streaming
  // started but no token landed). It disappears as soon as text arrives.
  const last = messages.at(-1);
  const lastAssistantText =
    last?.role === "assistant"
      ? last.parts.some((p) => p.type === "text" && "text" in p && p.text.trim())
      : false;
  const showThinking =
    (status === "submitted" || status === "streaming") && !lastAssistantText;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mx-auto flex h-full w-full max-w-3xl flex-col px-3 sm:px-4">
        {error && (
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2 text-destructive text-sm">
            <AlertCircle className="size-4 shrink-0" />
            {error.message}
          </div>
        )}

        <Conversation className="min-h-0 flex-1">
          <ConversationContent>
            {messages.length === 0 ? (
              <ConversationEmptyState
                title="Начните диалог"
                description="Спросите про портфель, NAV/PnL или research-мемо."
                icon={<MessageSquare className="size-8" />}
              />
            ) : (
              <>
                {messages.map((message) => (
                  <Message key={message.id} from={message.role}>
                    <MessageContent>
                      {message.parts.map((part, i) =>
                        part.type === "text" ? (
                          <MessageResponse key={`${message.id}-${i}`}>
                            {part.text}
                          </MessageResponse>
                        ) : null,
                      )}
                    </MessageContent>
                  </Message>
                ))}
                {showThinking && (
                  <Message from="assistant">
                    <MessageContent>
                      <span className="inline-flex items-center gap-1 text-muted-foreground text-sm">
                        Думаю
                        <span className="inline-flex gap-0.5">
                          <span className="size-1 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
                          <span className="size-1 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
                          <span className="size-1 animate-bounce rounded-full bg-current" />
                        </span>
                      </span>
                    </MessageContent>
                  </Message>
                )}
              </>
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        <div className="shrink-0 border-t bg-background py-3">
          <PromptInput onSubmit={handleSubmit}>
            <PromptInputTextarea
              placeholder="Вопрос про фонд…"
              className="min-h-[3.5rem] px-3 text-base"
            />
            <InputGroupAddon align="inline-end" className="self-end pb-2">
              <PromptInputSubmit status={status} />
            </InputGroupAddon>
          </PromptInput>
        </div>
      </div>
    </div>
  );
}

// Shared thread list, reused by the desktop sidebar and the mobile drawer.
// Module-level (not nested in ChatApp's render) so it doesn't remount.
function DialogList({
  threads,
  activeId,
  onSelect,
  onNavigate,
}: {
  threads: StoredThread[];
  activeId: string;
  onSelect: (id: string) => void;
  onNavigate?: () => void;
}) {
  return (
    <ul className="flex-1 overflow-y-auto p-2">
      {threads.map((t) => (
        <li key={t.id}>
          <button
            type="button"
            onClick={() => {
              onSelect(t.id);
              onNavigate?.();
            }}
            className={`w-full rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-accent ${
              t.id === activeId ? "bg-accent" : ""
            }`}
          >
            <span className="line-clamp-2">{t.title}</span>
            {t.status === "streaming" && (
              <span className="text-muted-foreground text-xs">…</span>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}

export function ChatApp() {
  const [store, setStore] = useState(emptyThreadStore);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [seedMessage, setSeedMessage] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const activeThread = store.threads.find((t) => t.id === activeId);

  useEffect(() => {
    const loaded = loadThreadStore();
    let id = loaded.activeId;
    let next = loaded;

    if (!id) {
      id = crypto.randomUUID();
      next = {
        activeId: id,
        threads: [
          {
            id,
            title: DEFAULT_THREAD_TITLE,
            updatedAt: Date.now(),
            messages: [],
            status: "idle" as const,
          },
          ...loaded.threads,
        ],
      };
      saveThreadStore(next);
    }

    setStore(next);
    setActiveId(id);
    setMounted(true);
  }, []);

  const handleThreadUpdate = useCallback((thread: StoredThread) => {
    setStore((prev) => {
      const existing = prev.threads.find((t) => t.id === thread.id);
      if (existing && threadSnapshot(existing) === threadSnapshot(thread)) {
        return prev;
      }
      const threads = [
        thread,
        ...prev.threads.filter((t) => t.id !== thread.id),
      ].sort((a, b) => b.updatedAt - a.updatedAt);
      const next = { activeId: thread.id, threads };
      saveThreadStore(next);
      return next;
    });
  }, []);

  const handleNewChat = () => {
    const id = crypto.randomUUID();
    const next = {
      activeId: id,
      threads: [
        {
          id,
          title: "Новый диалог",
          updatedAt: Date.now(),
          messages: [],
          status: "idle" as const,
        },
        ...store.threads.filter((t) => t.id !== id),
      ],
    };
    setStore(next);
    saveThreadStore(next);
    setActiveId(id);
  };

  const handleSelectThread = (id: string) => {
    setActiveId(id);
    saveThreadStore({ ...store, activeId: id });
  };

  if (!mounted || !activeId) {
    return (
      <div className="flex h-[calc(100dvh-3.5rem)] items-center justify-center text-muted-foreground text-sm">
        Загрузка…
      </div>
    );
  }

  const conversationId = activeId;

  return (
    <div className="flex h-[calc(100dvh-3.5rem)]">
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-muted/30 md:flex">
        <div className="flex items-center justify-between border-b p-3">
          <span className="font-medium text-sm">Диалоги</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleNewChat}
          >
            Новый
          </Button>
        </div>
        <DialogList
          threads={store.threads}
          activeId={conversationId}
          onSelect={handleSelectThread}
        />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-3 py-2 md:hidden">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setDrawerOpen(true)}
            aria-label="Диалоги"
          >
            <Menu className="size-4" />
            Диалоги
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="ml-auto"
            onClick={handleNewChat}
            aria-label="Новый диалог"
          >
            <Plus className="size-4" />
          </Button>
        </div>

        {/* Lightweight left drawer (no extra deps) for mobile thread switching */}
        {drawerOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <button
              type="button"
              aria-label="Закрыть"
              className="absolute inset-0 bg-black/40"
              onClick={() => setDrawerOpen(false)}
            />
            <div className="absolute inset-y-0 left-0 flex w-80 max-w-[85vw] flex-col border-r bg-background shadow-xl">
              <div className="flex items-center justify-between border-b p-3">
                <span className="font-medium text-sm">Диалоги</span>
                <div className="flex items-center gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      handleNewChat();
                      setDrawerOpen(false);
                    }}
                  >
                    <Plus className="size-4" />
                    Новый
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => setDrawerOpen(false)}
                    aria-label="Закрыть"
                  >
                    <X className="size-4" />
                  </Button>
                </div>
              </div>
              <DialogList
                threads={store.threads}
                activeId={conversationId}
                onSelect={handleSelectThread}
                onNavigate={() => setDrawerOpen(false)}
              />
            </div>
          </div>
        )}
        <ChatSession
          key={conversationId}
          conversationId={conversationId}
          initialThread={activeThread}
          seedMessage={seedMessage}
          onSeedConsumed={() => setSeedMessage(null)}
          onThreadUpdate={handleThreadUpdate}
        />
      </div>
    </div>
  );
}
