import { ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export type PillSelectOption<T extends string> = {
  value: T;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
};

type PillSelectProps<T extends string> = {
  value: T;
  onValueChange: (value: T) => void;
  options: PillSelectOption<T>[];
  className?: string;
};

export function PillSelect<T extends string>({
  value,
  onValueChange,
  options,
  className,
}: PillSelectProps<T>) {
  const active = options.find((o) => o.value === value) ?? options[0];
  const ActiveIcon = active?.icon;
  const anyHasIcon = options.some((o) => o.icon);

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger
        className={cn(
          "inline-flex shrink-0 items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5 text-sm text-secondary-foreground transition-colors hover:bg-secondary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "[&[data-state=open]>svg:last-child]:rotate-180",
          className,
        )}
      >
        {ActiveIcon ? <ActiveIcon className="size-4" aria-hidden /> : null}
        <span>{active?.label}</span>
        <ChevronDown
          className="size-4 transition-transform duration-200"
          aria-hidden
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        sideOffset={8}
        className="min-w-[220px] rounded-2xl border-border/60 bg-popover p-2"
      >
        {options.map((option) => {
          const Icon = option.icon;
          const selected = option.value === value;
          return (
            <DropdownMenuItem
              key={option.value}
              onSelect={() => onValueChange(option.value)}
              className="cursor-pointer gap-3 rounded-xl px-3 py-2.5 text-base [&_svg]:size-5 [&_svg]:text-muted-foreground"
            >
              {Icon ? (
                <Icon aria-hidden />
              ) : anyHasIcon ? (
                <span className="size-5" aria-hidden />
              ) : null}
              <span className="flex-1 text-foreground">{option.label}</span>
              {selected ? (
                <span aria-hidden className="size-2 rounded-full bg-sky-500" />
              ) : null}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
