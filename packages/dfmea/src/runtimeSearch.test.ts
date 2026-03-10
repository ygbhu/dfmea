import { describe, expect, test } from 'bun:test';
import { buildRuntimeShard, type DfmeaSubtreeDocument } from './runtimeIndex';
import { searchRuntimeShard, findRuntimeNodeById } from './runtimeSearch';

const subtree: DfmeaSubtreeDocument = {
  subtreeId: 'brake-signal',
  filePath: '/tmp/demo-brake/content/braking/brake-signal.md',
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
};

describe('dfmea runtime search', () => {
  test('finds the best local node by keyword', () => {
    const shard = buildRuntimeShard(subtree);
    const result = searchRuntimeShard(shard, 'signal');

    expect(result[0]?.id).toBe('FAIL-001');
    expect(result.length).toBeGreaterThan(0);
  });

  test('finds a local node by id', () => {
    const shard = buildRuntimeShard(subtree);
    const result = findRuntimeNodeById(shard, 'FNC-001');
    expect(result?.title).toBe('Brake signal acquisition');
  });
});
