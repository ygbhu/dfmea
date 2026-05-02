import { describe, expect, it } from 'vitest';
import { isWorkspaceCapability } from './index';

describe('capability sdk', () => {
  it('identifies platform workspace capabilities', () => {
    expect(isWorkspaceCapability('workspace.projection.get')).toBe(true);
    expect(isWorkspaceCapability('dfmea.generate_initial_analysis')).toBe(false);
  });
});
