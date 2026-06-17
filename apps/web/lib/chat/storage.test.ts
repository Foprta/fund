import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_THREAD_TITLE,
  deriveThreadTitle,
  loadThreadStore,
  type StoredMessage,
  titleFromMessage,
} from "./storage";

function user(text: string): StoredMessage {
  return { id: crypto.randomUUID(), role: "user", text };
}

function assistant(text: string): StoredMessage {
  return { id: crypto.randomUUID(), role: "assistant", text };
}

describe("titleFromMessage", () => {
  it("returns trimmed single-line text when short", () => {
    expect(titleFromMessage("  Какие позиции\n в фонде?  ")).toBe(
      "Какие позиции в фонде?",
    );
  });

  it("truncates long text with an ellipsis", () => {
    const long = "a".repeat(60);
    const out = titleFromMessage(long);
    expect(out).toHaveLength(46); // 45 chars + ellipsis
    expect(out.endsWith("…")).toBe(true);
  });

  it("falls back to the placeholder for empty text", () => {
    expect(titleFromMessage("   ")).toBe(DEFAULT_THREAD_TITLE);
  });
});

describe("deriveThreadTitle", () => {
  it("derives the title from the first user message when title is the placeholder", () => {
    const messages = [user("Сколько стоит юнит?"), assistant("...")];
    expect(deriveThreadTitle(messages, DEFAULT_THREAD_TITLE)).toBe(
      "Сколько стоит юнит?",
    );
  });

  it("derives from the first user message even after several turns", () => {
    const messages = [
      user("Первый вопрос"),
      assistant("ответ"),
      user("Второй вопрос"),
    ];
    expect(deriveThreadTitle(messages, DEFAULT_THREAD_TITLE)).toBe(
      "Первый вопрос",
    );
  });

  it("keeps an existing real title untouched", () => {
    const messages = [user("Новое сообщение")];
    expect(deriveThreadTitle(messages, "Мой диалог")).toBe("Мой диалог");
  });

  it("treats an empty title as a placeholder", () => {
    const messages = [user("Вопрос")];
    expect(deriveThreadTitle(messages, "")).toBe("Вопрос");
  });

  it("returns the placeholder when there is no user message yet", () => {
    expect(deriveThreadTitle([], DEFAULT_THREAD_TITLE)).toBe(
      DEFAULT_THREAD_TITLE,
    );
    expect(deriveThreadTitle([assistant("hi")], DEFAULT_THREAD_TITLE)).toBe(
      DEFAULT_THREAD_TITLE,
    );
  });
});

describe("loadThreadStore backfill", () => {
  // The unit project runs under `environment: "node"`, so window/localStorage
  // do not exist — stub them just for these load tests.
  function stubStorage(value: string | null) {
    vi.stubGlobal("window", {});
    vi.stubGlobal("localStorage", { getItem: () => value });
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("re-titles existing placeholder threads from their first message on load", () => {
    stubStorage(
      JSON.stringify({
        activeId: "a",
        threads: [
          {
            id: "a",
            title: DEFAULT_THREAD_TITLE,
            updatedAt: 1,
            status: "idle",
            messages: [
              { id: "m1", role: "user", text: "Какой NAV у фонда?" },
              { id: "m2", role: "assistant", text: "..." },
            ],
          },
          {
            id: "b",
            title: DEFAULT_THREAD_TITLE,
            updatedAt: 2,
            status: "idle",
            messages: [],
          },
        ],
      }),
    );

    const store = loadThreadStore();
    expect(store.threads[0].title).toBe("Какой NAV у фонда?");
    // Empty thread keeps the placeholder.
    expect(store.threads[1].title).toBe(DEFAULT_THREAD_TITLE);
  });

  it("leaves a user-set title untouched on load", () => {
    stubStorage(
      JSON.stringify({
        activeId: "a",
        threads: [
          {
            id: "a",
            title: "Мой диалог",
            updatedAt: 1,
            status: "idle",
            messages: [{ id: "m1", role: "user", text: "что-то ещё" }],
          },
        ],
      }),
    );

    expect(loadThreadStore().threads[0].title).toBe("Мой диалог");
  });
});
