import type { Meta, StoryObj } from "@storybook/react-vite";
import { Circle, Square, Triangle } from "lucide-react";
import { useState } from "react";
import { expect, userEvent, within } from "storybook/test";
import { PillSelect, type PillSelectOption } from "./pill-select";

type SampleValue = "a" | "b" | "c";

const withIconsOptions: PillSelectOption<SampleValue>[] = [
  { value: "a", label: "Option A", icon: Circle },
  { value: "b", label: "Option B", icon: Square },
  { value: "c", label: "Option C", icon: Triangle },
];

const noIconOptions: PillSelectOption<SampleValue>[] = [
  { value: "a", label: "Daily" },
  { value: "b", label: "Weekly" },
  { value: "c", label: "Monthly" },
];

const meta = {
  component: PillSelect,
  parameters: { layout: "centered" },
  tags: ["autodocs"],
} satisfies Meta<typeof PillSelect<SampleValue>>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithIcons: Story = {
  args: {
    value: "a",
    options: withIconsOptions,
    onValueChange: () => {},
  },
};

export const NoIcons: Story = {
  args: {
    value: "a",
    options: noIconOptions,
    onValueChange: () => {},
  },
};

export const Interactive: Story = {
  args: {
    value: "a",
    options: withIconsOptions,
    onValueChange: () => {},
  },
  render: (args) => {
    const [value, setValue] = useState<SampleValue>(args.value as SampleValue);
    return (
      <PillSelect
        {...args}
        value={value}
        onValueChange={(v) => setValue(v as SampleValue)}
      />
    );
  },
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole("button", { name: /option a/i });

    await step("opens menu on click", async () => {
      await userEvent.click(trigger);
      const menu = await within(document.body).findByRole("menu");
      await expect(menu).toBeInTheDocument();
    });

    await step("selecting an option updates the trigger label", async () => {
      const optionC = await within(document.body).findByRole("menuitem", {
        name: /option c/i,
      });
      await userEvent.click(optionC);
      await expect(trigger).toHaveTextContent(/option c/i);
    });
  },
};
