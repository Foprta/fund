import * as React from "react";
import { Drawer as DrawerPrimitive } from "vaul";

import { cn } from "@/lib/utils";

type Direction = "top" | "bottom" | "left" | "right";

const DrawerDirectionContext = React.createContext<Direction>("bottom");

const Drawer = ({
  shouldScaleBackground = true,
  direction = "bottom",
  ...props
}: React.ComponentProps<typeof DrawerPrimitive.Root>) => (
  <DrawerDirectionContext.Provider value={direction as Direction}>
    <DrawerPrimitive.Root
      shouldScaleBackground={shouldScaleBackground}
      direction={direction}
      {...props}
    />
  </DrawerDirectionContext.Provider>
);
Drawer.displayName = "Drawer";

const DrawerTrigger = DrawerPrimitive.Trigger;

const DrawerPortal = DrawerPrimitive.Portal;

const DrawerClose = DrawerPrimitive.Close;

const DrawerOverlay = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DrawerPrimitive.Overlay
    ref={ref}
    className={cn("fixed inset-0 z-50 bg-black/80", className)}
    {...props}
  />
));
DrawerOverlay.displayName = DrawerPrimitive.Overlay.displayName;

const directionClasses: Record<Direction, string> = {
  bottom:
    "inset-x-0 bottom-0 mt-24 h-auto max-h-[96vh] flex-col rounded-t-[10px] border-t",
  top: "inset-x-0 top-0 mb-24 h-auto max-h-[96vh] flex-col rounded-b-[10px] border-b",
  left: "inset-y-0 left-0 h-full w-3/4 max-w-sm flex-col rounded-r-[10px] border-r",
  right:
    "inset-y-0 right-0 h-full w-3/4 max-w-sm flex-col rounded-l-[10px] border-l",
};

const handleClasses: Record<Direction, string> = {
  bottom: "mx-auto mt-4 h-2 w-[100px] rounded-full bg-muted",
  top: "mx-auto mb-4 h-2 w-[100px] rounded-full bg-muted order-last",
  left: "my-auto ml-auto mr-2 h-[100px] w-2 rounded-full bg-muted",
  right: "my-auto ml-2 mr-auto h-[100px] w-2 rounded-full bg-muted order-first",
};

const DrawerContent = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Content>
>(({ className, children, ...props }, ref) => {
  const direction = React.useContext(DrawerDirectionContext);
  const isHorizontal = direction === "left" || direction === "right";
  return (
    <DrawerPortal>
      <DrawerOverlay />
      <DrawerPrimitive.Content
        ref={ref}
        className={cn(
          "fixed z-50 flex bg-background",
          directionClasses[direction],
          isHorizontal && "flex-row",
          className,
        )}
        {...props}
      >
        <div className={handleClasses[direction]} />
        <div className="flex flex-1 flex-col">{children}</div>
      </DrawerPrimitive.Content>
    </DrawerPortal>
  );
});
DrawerContent.displayName = "DrawerContent";

const DrawerHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("grid gap-1.5 p-4 text-center sm:text-left", className)}
    {...props}
  />
);
DrawerHeader.displayName = "DrawerHeader";

const DrawerFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("mt-auto flex flex-col gap-2 p-4", className)}
    {...props}
  />
);
DrawerFooter.displayName = "DrawerFooter";

const DrawerTitle = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DrawerPrimitive.Title
    ref={ref}
    className={cn(
      "text-lg font-semibold leading-none tracking-tight",
      className,
    )}
    {...props}
  />
));
DrawerTitle.displayName = DrawerPrimitive.Title.displayName;

const DrawerDescription = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DrawerPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
DrawerDescription.displayName = DrawerPrimitive.Description.displayName;

export {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerOverlay,
  DrawerPortal,
  DrawerTitle,
  DrawerTrigger,
};
