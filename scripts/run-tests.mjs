import { existsSync, readdirSync, statSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const vitestBin = resolve(rootDir, 'node_modules/vitest/vitest.mjs');

const sourceDirs = [
  'apps/api/src',
  'apps/web/src',
  'packages/shared/src',
  'packages/plugin-sdk/src',
  'packages/capability-sdk/src',
  'plugins/dfmea/src',
];

function findTestFiles(dir) {
  if (!existsSync(dir)) {
    return [];
  }

  return readdirSync(dir).flatMap((entry) => {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);

    if (stat.isDirectory()) {
      return findTestFiles(fullPath);
    }

    if (/\.(spec|test)\.[cm]?[tj]sx?$/.test(entry)) {
      return [relative(rootDir, fullPath).replaceAll('\\', '/')];
    }

    return [];
  });
}

const testFiles = sourceDirs.flatMap((dir) => findTestFiles(resolve(rootDir, dir)));

if (testFiles.length === 0) {
  console.error('No test files found.');
  process.exit(1);
}

const result = spawnSync(
  process.execPath,
  [
    vitestBin,
    'run',
    ...testFiles,
    '--pool',
    'forks',
    '--maxWorkers',
    '1',
    '--no-file-parallelism',
  ],
  {
    cwd: rootDir,
    stdio: 'inherit',
  },
);

if (result.error) {
  console.error(`Failed to start Vitest: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
