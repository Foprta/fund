import { cn } from "@/lib/utils";

export function ScrollShadow({
  side,
  visible,
}: {
  side: "left" | "right";
  visible: boolean;
}) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-y-0 z-10 w-10 transition-opacity duration-150",
        side === "left"
          ? "left-0 bg-linear-to-r from-background to-transparent"
          : "right-0 bg-linear-to-l from-background to-transparent",
        visible ? "opacity-100" : "opacity-0",
      )}
    />
  );
}
