import { describe, expect, it } from 'vitest';
import { buildDraftTree, buildWorkingTree, eventLabel, patchLabel } from './workspaceModel';
import type { DraftPatchRecord, DraftPreview, PlatformEvent, ProjectionReadResult } from './platformApi';

describe('workspaceModel', () => {
  it('maps working projection roots to UI tree nodes', () => {
    const projection: ProjectionReadResult = {
      freshness: 'fresh',
      validationStatus: 'passed',
      currentWorkspaceRevision: 1,
      projection: {
        projectionId: 'projx_1',
        workspaceId: 'ws_1',
        projectId: 'proj_1',
        pluginId: 'dfmea',
        kind: 'working_tree',
        category: 'working',
        scopeType: 'project',
        scopeId: 'proj_1',
        sourceRevision: 1,
        status: 'fresh',
        summary: null,
        payload: {
          roots: [
            {
              artifact_id: 'art_1',
              type: 'dfmea.system',
              title: 'Cooling fan system',
              badges: {},
              children: [
                {
                  artifact_id: 'art_2',
                  type: 'dfmea.component',
                  title: 'Fan controller',
                  badges: { severity: 8 },
                  children: [],
                },
              ],
            },
          ],
        },
      },
    };

    expect(buildWorkingTree(projection)).toMatchObject([
      { id: 'art_1', label: 'Cooling fan system', depth: 0, status: 'confirmed' },
      { id: 'art_2', label: 'Fan controller', depth: 1, status: 'confirmed' },
    ]);
  });

  it('maps draft preview nodes and timeline events', () => {
    const preview: DraftPreview = {
      draftBatchId: 'draft_1',
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      sessionId: 'sess_1',
      runId: 'run_1',
      pluginId: 'dfmea',
      status: 'pending',
      baseWorkspaceRevision: 0,
      targetWorkspaceRevision: null,
      evidenceRefs: ['mock://evidence/1'],
      validation: {
        status: 'not_validated',
        pendingPatchCount: 1,
        rejectedPatchCount: 0,
      },
      edges: [],
      nodes: [
        {
          draftPatchId: 'patch_1',
          operation: 'create_artifact',
          status: 'pending',
          targetType: 'artifact',
          targetId: null,
          tempRef: 'temp:system',
          artifactType: 'dfmea.system',
          payload: { title: 'Draft system' },
        },
      ],
    };
    const event: PlatformEvent = {
      event_type: 'runtime.result.proposed',
      payload: { draft_batch_id: 'draft_1' },
    };
    const patch: DraftPatchRecord = {
      draftPatchId: 'patch_1',
      draftBatchId: 'draft_1',
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      targetId: null,
      tempRef: 'temp:system',
      artifactType: 'dfmea.system',
      relationType: null,
      sourceTempRef: null,
      targetTempRef: null,
      sourceArtifactId: null,
      targetArtifactId: null,
      afterPayload: { title: 'Draft system' },
      payloadPatch: null,
      status: 'pending',
    };

    expect(buildDraftTree(preview)[0]).toMatchObject({
      id: 'temp:system',
      label: 'Draft system',
      status: 'candidate_new',
    });
    expect(eventLabel(event)).toBe('Draft proposed: draft_1');
    expect(patchLabel(patch)).toBe('Draft system');
  });
});
