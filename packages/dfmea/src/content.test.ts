import { describe, expect, test } from 'bun:test';
import { buildDfmeaStorageLayout, getCanonicalSubtreePath } from './content';

describe('dfmea content helpers', () => {
  test('derives canonical storage layout from a workspace root', () => {
    const result = buildDfmeaStorageLayout('/tmp/demo-brake');

    expect(result.projectRoot).toBe('/tmp/demo-brake');
    expect(result.contentRoot).toBe('/tmp/demo-brake/content');
    expect(result.runtimeRoot).toBe('/tmp/demo-brake/runtime');
    expect(result.changesRoot).toBe('/tmp/demo-brake/changes');
  });

  test('derives a canonical subtree markdown path', () => {
    const path = getCanonicalSubtreePath('/tmp/demo-brake', 'braking', 'brake-signal');
    expect(path).toBe('/tmp/demo-brake/content/braking/brake-signal.md');
  });
});
