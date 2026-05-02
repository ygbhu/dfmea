import { describe, expect, it } from 'vitest';
import { createPluginCapabilityId } from './index';

describe('plugin sdk', () => {
  it('creates plugin capability ids', () => {
    expect(createPluginCapabilityId('dfmea', 'generate_initial_analysis')).toBe(
      'dfmea.generate_initial_analysis',
    );
  });
});
