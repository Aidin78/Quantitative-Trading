"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Zap } from "lucide-react";
import { AppFooter } from "@/components/layout/AppFooter";
import { APP_NAME } from "@/lib/app-info";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("changeme");
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await api.login(username, password);
      setToken(res.access_token);
      router.push("/");
    } catch {
      setError("Invalid credentials");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-accent to-emerald-500 shadow-lg shadow-accent/30">
            <Zap className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{APP_NAME}</h1>
          <p className="mt-1 text-sm text-muted">
            Sign in to the trading platform
          </p>
        </div>

        <form onSubmit={onSubmit} className="glass-card space-y-4 p-6">
          <div>
            <label
              htmlFor="username"
              className="text-xs font-medium uppercase tracking-wider text-muted"
            >
              Username
            </label>
            <input
              id="username"
              className="input-field mt-2"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div>
            <label
              htmlFor="password"
              className="text-xs font-medium uppercase tracking-wider text-muted"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              className="input-field mt-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}
          <button type="submit" className="btn-primary w-full">
            Sign in
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-muted">
          Auth is optional in development — go directly to{" "}
          <a href="/" className="text-accent hover:underline">
            dashboard
          </a>
        </p>

        <div className="mt-6">
          <AppFooter variant="full" />
        </div>
      </div>
    </div>
  );
}
