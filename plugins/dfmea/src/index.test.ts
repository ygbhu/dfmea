import { describe, expect, it } from 'vitest';
import {
  buildDfmeaExportPayload,
  buildDfmeaWorkingTree,
  calculateActionPriority,
  dfmeaPluginId,
  generateInitialAnalysis,
  generateInitialAnalysisCapabilityId,
  validateDfmeaGraph,
  type DfmeaArtifactRecord,
  type DfmeaEdgeRecord,
} from './index';

describe('dfmea plugin', () => {
  it('uses the locked plugin id and initial skill capability id', () => {
    expect(dfmeaPluginId).toBe('dfmea');
    expect(generateInitialAnalysisCapabilityId).toBe('dfmea.generate_initial_analysis');
  });

  it('calculates simplified action priority', () => {
    expect(calculateActionPriority(8, 4, 6)).toBe('High');
    expect(calculateActionPriority(6, 3, 3)).toBe('Medium');
    expect(calculateActionPriority(3, 2, 2)).toBe('Low');
  });

  it('generates the cooling fan initial analysis draft operations', () => {
    const result = generateInitialAnalysis({
      project_id: 'proj_1',
      goal: 'Generate passenger vehicle cooling fan controller DFMEA draft',
    });

    const artifactTypes = result.draft_batch.operations
      .filter((operation) => operation.patchType === 'create_artifact')
      .map((operation) => operation.artifactType);

    expect(result.result_type).toBe('ai_draft_proposal');
    expect(artifactTypes).toContain('dfmea.system');
    expect(artifactTypes).toContain('dfmea.failure_mode');
    expect(artifactTypes).toContain('dfmea.action');
    expect(result.draft_batch.operations.filter((operation) => operation.patchType === 'create_edge')).toHaveLength(10);
  });

  it('builds working tree and export payload from canonical records', () => {
    const artifacts: DfmeaArtifactRecord[] = [
      artifact('art_system', 'dfmea.system', 'SYS-001', 'Engine Thermal Management System'),
      artifact('art_subsystem', 'dfmea.subsystem', 'SUB-001', 'Cooling Fan System'),
      artifact('art_component', 'dfmea.component', 'COMP-001', 'Electronic Cooling Fan Controller'),
      artifact('art_function', 'dfmea.function', 'FN-001', 'Control fan speed'),
      artifact('art_failure', 'dfmea.failure_mode', 'FM-001', 'Fan not started', {
        severity: 8,
        occurrence: 4,
        detection: 6,
        ap: 'High',
      }),
    ];
    const edges: DfmeaEdgeRecord[] = [
      edge('edge_1', 'art_system', 'art_subsystem', 'dfmea.contains'),
      edge('edge_2', 'art_subsystem', 'art_component', 'dfmea.contains'),
      edge('edge_3', 'art_component', 'art_function', 'dfmea.contains'),
      edge('edge_4', 'art_failure', 'art_function', 'dfmea.failure_mode_of_function'),
    ];

    const validation = validateDfmeaGraph(artifacts, edges);
    const workingTree = buildDfmeaWorkingTree(artifacts, edges);
    const exportPayload = buildDfmeaExportPayload(artifacts, edges);

    expect(validation.status).toBe('passed');
    expect(workingTree.roots[0]?.children[0]?.children[0]?.children[0]?.children[0]?.type).toBe(
      'dfmea.failure_mode',
    );
    expect(exportPayload.summary).toMatchObject({
      artifact_count: 5,
      edge_count: 4,
      validation_status: 'passed',
    });
  });
});

function artifact(
  artifactId: string,
  artifactType: string,
  displayId: string,
  title: string,
  extraPayload = {},
): DfmeaArtifactRecord {
  return {
    artifactId,
    artifactType,
    payload: {
      display_id: displayId,
      title,
      ...extraPayload,
    },
  };
}

function edge(
  edgeId: string,
  sourceArtifactId: string,
  targetArtifactId: string,
  relationType: string,
): DfmeaEdgeRecord {
  return {
    edgeId,
    sourceArtifactId,
    targetArtifactId,
    relationType,
    payload: {},
  };
}
