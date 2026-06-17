import type { Preview } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import "../pages/tailwind.css";

const VIEWPORTS = {
  mobile: {
    name: "Mobile (375)",
    styles: { width: "375px", height: "667px" },
    type: "mobile",
  },
  mobileLarge: {
    name: "Mobile Large (414)",
    styles: { width: "414px", height: "896px" },
    type: "mobile",
  },
  tablet: {
    name: "Tablet (768)",
    styles: { width: "768px", height: "1024px" },
    type: "tablet",
  },
  desktop: {
    name: "Desktop (1280)",
    styles: { width: "1280px", height: "800px" },
    type: "desktop",
  },
} as const;

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      test: "todo",
    },
    backgrounds: {
      options: {
        light: { name: "light", value: "oklch(1 0 0)" },
        dark: { name: "dark", value: "oklch(0.145 0 0)" },
      },
    },
    viewport: {
      options: VIEWPORTS,
    },
  },
  initialGlobals: {
    backgrounds: { value: "light" },
    viewport: { value: "mobile", isRotated: false },
  },
  globalTypes: {
    theme: {
      description: "Color theme",
      defaultValue: "light",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "light", title: "Light", icon: "sun" },
          { value: "dark", title: "Dark", icon: "moon" },
        ],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    (Story) => {
      const [client] = useState(
        () =>
          new QueryClient({
            defaultOptions: {
              queries: { retry: false, staleTime: Number.POSITIVE_INFINITY },
            },
          }),
      );
      return (
        <QueryClientProvider client={client}>
          <Story />
        </QueryClientProvider>
      );
    },
    (Story, ctx) => {
      const theme = ctx.globals.theme as "light" | "dark";
      useEffect(() => {
        const root = document.documentElement;
        root.classList.toggle("dark", theme === "dark");
      }, [theme]);
      return <Story />;
    },
  ],
};

export default preview;
