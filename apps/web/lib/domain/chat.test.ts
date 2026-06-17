import { describe, expect, it } from "vitest";
import {
  chatRequestSchema,
  extractTokenText,
  parseLunaSseLine,
} from "./chat";

describe("parseLunaSseLine", () => {
  it("parses token events", () => {
    expect(parseLunaSseLine('data: {"type":"token","content":"Hi"}')).toEqual({
      type: "token",
      content: "Hi",
    });
  });

  it("parses done events", () => {
    expect(
      parseLunaSseLine(
        'data: {"type":"done","conversation_id":"abc"}',
      ),
    ).toEqual({ type: "done", conversation_id: "abc" });
  });
});

describe("extractTokenText", () => {
  it("accumulates tokens across chunks", () => {
    const a = extractTokenText(
      'data: {"type":"token","content":"Hel"}\n\n',
      "",
    );
    expect(a.text).toBe("Hel");
    const b = extractTokenText(
      'data: {"type":"token","content":"lo"}\n\n',
      a.rest,
    );
    expect(b.text).toBe("lo");
  });
});

describe("chatRequestSchema", () => {
  it("requires message", () => {
    expect(chatRequestSchema.safeParse({ message: "x" }).success).toBe(true);
    expect(chatRequestSchema.safeParse({}).success).toBe(false);
  });
});
