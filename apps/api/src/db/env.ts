import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export function loadEnvFiles(): void {
  for (const path of [resolve(process.cwd(), '.env'), resolve(process.cwd(), '..', '..', '.env')]) {
    if (!existsSync(path)) {
      continue;
    }

    const lines = readFileSync(path, 'utf8').split(/\r?\n/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) {
        continue;
      }

      const separatorIndex = trimmed.indexOf('=');
      if (separatorIndex <= 0) {
        continue;
      }

      const key = trimmed.slice(0, separatorIndex).trim();
      const value = trimmed.slice(separatorIndex + 1).trim();
      process.env[key] ??= value;
    }
  }
}

export function getDatabaseUrl(): string {
  loadEnvFiles();

  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    throw new Error('DATABASE_URL is required');
  }

  return databaseUrl;
}
