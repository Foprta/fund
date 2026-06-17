"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminPage() {
  const [secret, setSecret] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const runSync = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/admin/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_secret: secret }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? `HTTP ${res.status}`);
      }
      setResult(JSON.stringify(data, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка sync");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle>Синхронизация (админ)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">Секрет админа</span>
            <input
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2"
            />
          </label>
          <Button
            type="button"
            disabled={loading || !secret}
            onClick={runSync}
          >
            {loading ? "Запуск…" : "Запустить sync"}
          </Button>
          {error && <p className="text-destructive text-sm">{error}</p>}
          {result && (
            <pre className="max-h-96 overflow-auto rounded-md bg-muted p-3 text-xs">
              {result}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
