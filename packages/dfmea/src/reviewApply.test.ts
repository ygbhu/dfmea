import { afterEach, beforeEach, describe, expect, test } from 'bun:test';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import type { DfmeaProposal } from './proposal';
import { applyDfmeaReview } from './reviewApply';
import { listChangeRecords, readRuntimeShard, readSubtreeDocument, writeSubtreeDocument } from './storage';

describe('dfmea review-apply', () => {
  let projectRoot = '';

  beforeEach(async () => {
    projectRoot = (await mkdtemp(path.join(os.tmpdir(), 'dfmea-review-apply-'))).replace(/\\/g, '/');
  });

  afterEach(async () => {
    if (projectRoot) {
      await rm(projectRoot, { recursive: true, force: true });
    }
  });

  test('applies a confirmed proposal, refreshes runtime artifacts, and records the change', async () => {
    const filePath = `${projectRoot}/content/braking/brake-signal.md`;

    await writeSubtreeDocument({
      subtreeId: 'brake-signal',
      filePath,
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
              refs: [],
            },
          ],
        },
      ],
    });

    const proposal: DfmeaProposal = {
      proposalId: 'prop-001',
      actionId: 'review-apply',
      projectId: 'demo-brake',
      subtreeId: 'brake-signal',
      summary: 'Apply local failure section updates',
      targetFiles: ['content/braking/brake-signal.md'],
      operations: [
        {
          type: 'update_section',
          file: 'content/braking/brake-signal.md',
          section: 'failures',
          description: 'Persist local failure content',
        },
        {
          type: 'append_note',
          file: 'content/braking/brake-signal.md',
          section: 'failures',
          description: 'Review note for the failure section',
        },
      ],
      status: 'proposed',
      createdAt: '2026-03-09T00:00:00.000Z',
    };

    const result = await applyDfmeaReview({
      projectRoot,
      request: {
        confirm: true,
        proposal,
        sections: [
          {
            section: 'failures',
            entries: [
              {
                id: 'FAIL-001',
                kind: 'failure_mode',
                title: 'Signal lost',
                summary: 'Brake input signal is not received.',
                refs: ['FNC-001'],
              },
            ],
          },
        ],
        notes: [
          {
            section: 'failures',
            note: 'Confirmed by review-apply.',
          },
        ],
      },
    });

    const updated = await readSubtreeDocument(filePath);
    const shard = await readRuntimeShard(projectRoot, 'brake-signal');
    const changeRecords = await listChangeRecords(projectRoot);

    expect(result.proposal.status).toBe('applied');
    expect(updated.sections.find((section) => section.name === 'failures')?.entries[0]?.id).toBe('FAIL-001');
    expect(updated.notes?.[0]?.text).toBe('Confirmed by review-apply.');
    expect(shard?.nodes.some((node) => node.id === 'FAIL-001')).toBe(true);
    expect(changeRecords[0]?.summary).toContain('Apply local failure section updates');
    expect(changeRecords[0]?.status).toBe('applied');
  });
});
