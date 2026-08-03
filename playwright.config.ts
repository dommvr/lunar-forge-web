import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3107",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command:
        ".\\backend\\.venv\\Scripts\\python.exe -m uvicorn lunar_forge_web.api.main:app --app-dir backend/src --host 127.0.0.1 --port 8107 --no-access-log --log-level warning",
      url: "http://127.0.0.1:8107/api/v1/health",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        LUNAR_FORGE_WEB_ENVIRONMENT: "test",
        LUNAR_FORGE_WEB_CORS_ALLOWED_ORIGINS: "http://localhost:3107",
        LUNAR_FORGE_WEB_FAKE_AUTH_ENABLED: "true",
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3107",
      url: "http://localhost:3107",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        LUNAR_FORGE_AUTH_E2E_MODE: "playwright",
        LUNAR_FORGE_ADMIN_USER_IDS: "admin-e2e",
        NEXT_PUBLIC_LUNAR_FORGE_API_URL: "http://127.0.0.1:8107",
        NEXT_PUBLIC_LUNAR_FORGE_API_E2E_MODE: "playwright",
      },
    },
  ],
});
