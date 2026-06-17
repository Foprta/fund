import { MessageSquare, Moon, Settings } from "lucide-react";
import type { ReactNode } from "react";
import { usePageContext } from "vike-react/usePageContext";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./ThemeToggle";

const navItems = [
  { href: "/", label: "Чат", icon: MessageSquare },
  { href: "/admin", label: "Админ", icon: Settings },
];

export function Shell({ children }: { children: ReactNode }) {
  const pageContext = usePageContext();
  const isChat = pageContext.urlPathname === "/";

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b bg-background">
        <div className="mx-auto flex h-14 w-full items-center gap-3 px-4">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <Moon className="size-5 text-amber-400" aria-hidden />
            <span>Luna Fund</span>
          </a>
          <p className="hidden text-muted-foreground text-sm sm:block">
            Ассистент фонда
          </p>
          <nav
            aria-label="Основная"
            className="ml-auto hidden items-center gap-1 md:flex"
          >
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = pageContext.urlPathname === item.href;
              return (
                <a
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm transition-colors",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  <Icon className="size-4" aria-hidden />
                  {item.label}
                </a>
              );
            })}
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main className={cn("flex-1", isChat && "overflow-hidden")}>
        {children}
      </main>
      <nav
        aria-label="Мобильная"
        className="fixed inset-x-0 bottom-0 z-40 border-t bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <ul className="grid grid-cols-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pageContext.urlPathname === item.href;
            return (
              <li key={item.href}>
                <a
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex h-14 flex-col items-center justify-center gap-1 text-xs",
                    active ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  <Icon className="size-5" aria-hidden />
                  {item.label}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
