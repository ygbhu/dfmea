import { existsSync } from 'node:fs';
import { defineConfig, devices } from '@playwright/test';

const chromeExecutablePath =
  process.env.PLAYWRIGHT_CHROME_EXECUTABLE_PATH ?? findLocalChromeExecutable();

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 120_000,
  expect: {
    timeout: 30_000,
  },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    launchOptions: {
      ...(chromeExecutablePath !== undefined ? { executablePath: chromeExecutablePath } : {}),
    },
  },
  webServer: [
    {
      command: 'pnpm db:migrate && pnpm --filter @dfmea/api dev',
      url: 'http://127.0.0.1:3000/health',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'pnpm --filter @dfmea/web dev -- --host 127.0.0.1 --port 5173',
      url: 'http://127.0.0.1:5173',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        VITE_API_BASE_URL: 'http://127.0.0.1:3000',
      },
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});

function findLocalChromeExecutable(): string | undefined {
  const candidates = [
    process.env.ProgramFiles
      ? `${process.env.ProgramFiles}\\Google\\Chrome\\Application\\chrome.exe`
      : undefined,
    process.env['ProgramFiles(x86)']
      ? `${process.env['ProgramFiles(x86)']}\\Google\\Chrome\\Application\\chrome.exe`
      : undefined,
    process.env.ProgramFiles
      ? `${process.env.ProgramFiles}\\Microsoft\\Edge\\Application\\msedge.exe`
      : undefined,
    process.env['ProgramFiles(x86)']
      ? `${process.env['ProgramFiles(x86)']}\\Microsoft\\Edge\\Application\\msedge.exe`
      : undefined,
  ];

  return candidates.find((candidate) => candidate !== undefined && existsSync(candidate));
}
