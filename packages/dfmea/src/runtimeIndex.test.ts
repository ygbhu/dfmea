import { describe, expect, test } from 'bun:test';
import { buildRuntimeShard, buildRuntimeManifest, type DfmeaSubtreeDocument } from './runtimeIndex';

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
  ],
};

describe('dfmea runtime index', () => {
  test('builds one shard from one subtree document', () => {
    const shard = buildRuntimeShard(subtree);

    expect(shard.meta.subtreeId).toBe('brake-signal');
    expect(shard.meta.nodeCount).toBe(1);
    expect(shard.nodes[0]?.id).toBe('FNC-001');
    expect(shard.edges[0]?.type).toBe('ref');
  });

  test('builds a manifest from subtree documents', () => {
    const manifest = buildRuntimeManifest('demo-brake', [subtree]);

    expect(manifest.projectId).toBe('demo-brake');
    expect(manifest.subtrees[0]?.subtreeId).toBe('brake-signal');
    expect(manifest.subtrees[0]?.shardPath).toBe('runtime/shards/brake-signal');
  });
});
