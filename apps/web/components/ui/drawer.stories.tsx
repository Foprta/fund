import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, within } from "storybook/test";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "./drawer";

const meta = {
  component: Drawer,
  parameters: { layout: "centered" },
  tags: ["autodocs"],
} satisfies Meta<typeof Drawer>;

export default meta;
type Story = StoryObj<typeof meta>;

const SampleBody = () => (
  <>
    <DrawerHeader>
      <DrawerTitle>Panel title</DrawerTitle>
      <DrawerDescription>Short description for this drawer.</DrawerDescription>
    </DrawerHeader>
    <div className="px-4 pb-4 text-sm text-muted-foreground">
      Drawer body content goes here. Replace with forms, filters, or detail
      panels.
    </div>
    <DrawerFooter>
      <Button>Confirm</Button>
      <DrawerClose asChild>
        <Button variant="outline">Cancel</Button>
      </DrawerClose>
    </DrawerFooter>
  </>
);

export const Bottom: Story = {
  args: { direction: "bottom" },
  render: (args) => (
    <Drawer {...args}>
      <DrawerTrigger asChild>
        <Button>Open bottom drawer</Button>
      </DrawerTrigger>
      <DrawerContent>
        <SampleBody />
      </DrawerContent>
    </Drawer>
  ),
};

export const LeftFullHeight: Story = {
  args: { direction: "left" },
  render: (args) => (
    <Drawer {...args}>
      <DrawerTrigger asChild>
        <Button>Open left drawer</Button>
      </DrawerTrigger>
      <DrawerContent>
        <SampleBody />
      </DrawerContent>
    </Drawer>
  ),
};

export const Right: Story = {
  args: { direction: "right" },
  render: (args) => (
    <Drawer {...args}>
      <DrawerTrigger asChild>
        <Button>Open right drawer</Button>
      </DrawerTrigger>
      <DrawerContent>
        <SampleBody />
      </DrawerContent>
    </Drawer>
  ),
};

export const Top: Story = {
  args: { direction: "top" },
  render: (args) => (
    <Drawer {...args}>
      <DrawerTrigger asChild>
        <Button>Open top drawer</Button>
      </DrawerTrigger>
      <DrawerContent>
        <SampleBody />
      </DrawerContent>
    </Drawer>
  ),
};

export const OpensOnClick: Story = {
  args: { direction: "bottom" },
  render: (args) => (
    <Drawer {...args}>
      <DrawerTrigger asChild>
        <Button>Open</Button>
      </DrawerTrigger>
      <DrawerContent>
        <SampleBody />
      </DrawerContent>
    </Drawer>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole("button", { name: /open/i }));
    const title = await within(document.body).findByText("Panel title");
    await expect(title).toBeInTheDocument();
  },
};
