import vike from "@vikejs/hono";
import { Hono } from "hono";
import type { WorkerEnv } from "@/lib/env";
import { handleAdminSync } from "./luna-admin";
import { handleLunaChat } from "./luna-chat";

const app = new Hono<{ Bindings: WorkerEnv }>();

app.post("/api/chat", handleLunaChat);
app.post("/api/admin/sync", handleAdminSync);

vike(app);

export { app };
