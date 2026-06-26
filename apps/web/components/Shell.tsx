import type { ReactNode } from "react";
import { usePageContext } from "vike-react/usePageContext";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./ThemeToggle";

export function Shell({ children }: { children: ReactNode }) {
  const pageContext = usePageContext();
  const isChat = pageContext.urlPathname === "/";

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b bg-background">
        <div className="mx-auto flex h-14 w-full items-center gap-3 px-4">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <img
              src="/logo.png"
              alt="Luna Fund"
              className="size-7 rounded-full dark:invert"
            />
            <span>Luna Fund</span>
          </a>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className={cn("flex-1", isChat && "overflow-hidden")}>
        {children}
      </main>
    </div>
  );
}
