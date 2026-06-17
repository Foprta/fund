import type { Server } from "vike/types";
import { app } from "./server/app";

export default {
  fetch: app.fetch,
} satisfies Server;
