import "./tailwind.css";
import { QueryClientProvider } from "@tanstack/react-query";
import { Shell } from "@/components/Shell";
import { getQueryClient } from "@/lib/query-client";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={getQueryClient()}>
      <Shell>{children}</Shell>
    </QueryClientProvider>
  );
}
