import { afterEach, beforeEach, describe, expect, test } from 'bun:test';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import type { DfmeaSubtreeDocument } from './runtimeIndex';
import {
  materializeDfmeaRuntime,
  readRuntimeManifest,
  readRuntimeShard,
  readSubtreeDocument,
  searchDfmeaProject,
  writeSubtreeDocument,
} from './storage';

const subtree: DfmeaSubtreeDocument = {
  subtreeId: 'brake-signal',
  filePath: '',
  title: 'Brake Signal Subtree',
  sections: [
    {
      name: 'functions',
      entries: [
        {
          id: 'FNC-001',
          kind: 'function',
          title: 'Brake signal acquisition',
          summary: 'Receives and processes brake input signal.',
          refs: ['CHAIN-001'],
        },
      ],
    },
    {
      name: 'failures',
      entries: [
        {
          id: 'FAIL-001',
          kind: 'failure_mode',
          title: 'Signal lost',
          summary: 'Brake input signal is not received.',
          refs: [],
        },
      ],
    },
  ],
  notes: [
    {
      section: 'functions',
      text: 'Signal integrity must remain local to the subtree.',
    },
  ],
};

describe('dfmea storage helpers', () => {
  let projectRoot = '';

  beforeEach(async () => {
    projectRoot = (await mkdtemp(path.join(os.tmpdir(), 'dfmea-storage-'))).replace(/\\/g, '/');
  });

  afterEach(async () => {
    if (projectRoot) {
      await rm(projectRoot, { recursive: true, force: true });
    }
  });

  test('writes and reloads a canonical subtree markdown document', async () => {
    const filePath = `${projectRoot}/content/braking/brake-signal.md`;

    await writeSubtreeDocument({
      ...subtree,
      filePath,
    });

    const loaded = await readSubtreeDocument(filePath);

    expect(loaded.subtreeId).toBe('brake-signal');
    expect(loaded.title).toBe('Brake Signal Subtree');
    expect(loaded.sections[0]?.entries[0]?.id).toBe('FNC-001');
    expect(loaded.notes?.[0]?.text).toContain('Signal integrity');
  });

  test('materializes runtime artifacts and searches a subtree from canonical markdown', async () => {
    const filePath = `${projectRoot}/content/braking/brake-signal.md`;

    await writeSubtreeDocument({
      ...subtree,
      filePath,
    });

    const runtime = await materializeDfmeaRuntime(projectRoot);
    const manifest = await readRuntimeManifest(projectRoot);
    const shard = await readRuntimeShard(projectRoot, 'brake-signal');
    const results = await searchDfmeaProject({
      projectRoot,
      subtreeId: 'brake-signal',
      query: 'signal',
    });

    expect(runtime.manifestPath).toBe(`${projectRoot}/runtime/manifest.json`);
    expect(manifest?.subtrees[0]?.subtreeId).toBe('brake-signal');
    expect(shard?.meta.nodeCount).toBe(2);
    expect(results.results[0]?.node.id).toBe('FAIL-001');
    expect(results.results[0]?.subtreeId).toBe('brake-signal');
  });
});
