const STORAGE_KEY = "luna-fund-threads-v1";

export const DEFAULT_THREAD_TITLE = "Новый диалог";

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

export type StoredThread = {
  id: string;
  title: string;
  updatedAt: number;
  messages: StoredMessage[];
  status: "idle" | "streaming";
  draftAssistant?: string;
};

export type ThreadStore = {
  activeId: string | null;
  threads: StoredThread[];
};

export function emptyThreadStore(): ThreadStore {
  return { activeId: null, threads: [] };
}

function emptyStore(): ThreadStore {
  return emptyThreadStore();
}

export function loadThreadStore(): ThreadStore {
  if (typeof window === "undefined") {
    return emptyStore();
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw) as ThreadStore;
    if (!parsed.threads) return emptyStore();
    // Backfill titles for threads saved before titling existed (or saved while
    // still on the placeholder), so the whole history list shows real titles
    // immediately on load — not only the thread the user happens to open.
    parsed.threads = parsed.threads.map((t) => ({
      ...t,
      title: deriveThreadTitle(
        t.messages ?? [],
        t.title ?? DEFAULT_THREAD_TITLE,
      ),
    }));
    return parsed;
  } catch {
    return emptyStore();
  }
}

export function saveThreadStore(store: ThreadStore): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function titleFromMessage(text: string): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (t.length <= 48) return t || DEFAULT_THREAD_TITLE;
  return `${t.slice(0, 45)}…`;
}

/**
 * Title for a thread shown in the history list. Once a thread has a real,
 * user-set title we keep it; otherwise we derive it from the thread's FIRST
 * user message so the list shows what the conversation is about instead of the
 * "Новый диалог" placeholder. Using the first (not last) message keeps the
 * title stable as the conversation grows.
 */
export function deriveThreadTitle(
  messages: StoredMessage[],
  currentTitle: string,
): string {
  const placeholder =
    !currentTitle.trim() || currentTitle === DEFAULT_THREAD_TITLE;
  if (!placeholder) return currentTitle;
  const firstUser = messages.find((m) => m.role === "user");
  return firstUser ? titleFromMessage(firstUser.text) : DEFAULT_THREAD_TITLE;
}

export function newThreadId(): string {
  return crypto.randomUUID();
}
