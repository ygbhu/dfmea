import { createPluginCapabilityId } from '@dfmea/plugin-sdk';
import type { DraftPatchOperation, DraftPatchTargetType, JsonObject, JsonValue } from '@dfmea/shared';

export const dfmeaPluginId = 'dfmea';
export const generateInitialAnalysisCapabilityId = createPluginCapabilityId(
  dfmeaPluginId,
  'generate_initial_analysis',
);

export const dfmeaArtifactTypes = [
  'dfmea.system',
  'dfmea.subsystem',
  'dfmea.component',
  'dfmea.function',
  'dfmea.requirement',
  'dfmea.characteristic',
  'dfmea.failure_mode',
  'dfmea.failure_effect',
  'dfmea.failure_cause',
  'dfmea.action',
] as const;

export type DfmeaArtifactType = (typeof dfmeaArtifactTypes)[number];
export type DfmeaActionPriority = 'High' | 'Medium' | 'Low';

export interface DfmeaArtifactRecord {
  artifactId: string;
  artifactType: string;
  status?: string;
  payload: JsonObject;
}

export interface DfmeaEdgeRecord {
  edgeId: string;
  sourceArtifactId: string;
  targetArtifactId: string;
  relationType: string;
  status?: string;
  payload: JsonObject;
}

export interface DfmeaDraftOperation {
  patchType: DraftPatchOperation;
  targetType: DraftPatchTargetType;
  tempRef?: string;
  artifactType?: string;
  relationType?: string;
  sourceTempRef?: string;
  targetTempRef?: string;
  afterPayload?: JsonObject;
}

export interface GenerateInitialAnalysisInput {
  project_id: string;
  goal?: string;
  focus?: string;
  scope?: {
    system?: string;
    subsystem?: string;
    components?: string[];
  };
  knowledge_refs?: string[];
}

export interface GenerateInitialAnalysisOutput {
  result_type: 'ai_draft_proposal';
  summary: string;
  draft_batch: {
    title: string;
    goal: string;
    operations: DfmeaDraftOperation[];
  };
  warnings: string[];
  evidence_refs: string[];
}

export interface DfmeaTreeNode extends JsonObject {
  artifact_id: string;
  type: string;
  title: string;
  display_id?: string;
  badges: JsonObject;
  children: DfmeaTreeNode[];
}

export interface DfmeaWorkingTreePayload extends JsonObject {
  kind: 'dfmea.working_tree';
  roots: DfmeaTreeNode[];
  artifact_count: number;
  edge_count: number;
}

export interface DfmeaExportPayload extends JsonObject {
  kind: 'dfmea.export_payload';
  artifacts: JsonObject[];
  edges: JsonObject[];
  summary: JsonObject;
}

export interface DfmeaValidationFinding extends JsonObject {
  code: string;
  severity: 'blocking' | 'warning' | 'info';
  target_type: string;
  target_id?: string;
  message: string;
}

export interface DfmeaValidationResult extends JsonObject {
  status: 'passed' | 'failed';
  findings: DfmeaValidationFinding[];
}

export function calculateActionPriority(
  severity: number,
  occurrence: number,
  detection: number,
): DfmeaActionPriority {
  if (severity >= 9 || (severity >= 8 && occurrence >= 4 && detection >= 5)) {
    return 'High';
  }

  if (severity >= 6 || (occurrence >= 4 && detection >= 4)) {
    return 'Medium';
  }

  return 'Low';
}

export function generateInitialAnalysis(
  input: GenerateInitialAnalysisInput,
): GenerateInitialAnalysisOutput {
  const systemName = input.scope?.system ?? 'Engine Thermal Management System';
  const subsystemName = input.scope?.subsystem ?? 'Cooling Fan System';
  const componentName = input.scope?.components?.[0] ?? 'Electronic Cooling Fan Controller';
  const goal = input.goal ?? input.focus ?? 'Generate passenger vehicle cooling fan controller DFMEA draft';
  const failureModeScores = { severity: 8, occurrence: 4, detection: 6 };
  const ap = calculateActionPriority(
    failureModeScores.severity,
    failureModeScores.occurrence,
    failureModeScores.detection,
  );

  return {
    result_type: 'ai_draft_proposal',
    summary:
      'Generated a minimum DFMEA draft for the cooling fan controller with structure, function, requirement, characteristic, failure chain, and action.',
    draft_batch: {
      title: 'Cooling fan controller DFMEA initial draft',
      goal,
      operations: [
        createArtifact('temp:sys:thermal-management', 'dfmea.system', {
          title: systemName,
          display_id: 'SYS-001',
          description: 'Vehicle system responsible for thermal control.',
        }),
        createArtifact('temp:sub:cooling-fan', 'dfmea.subsystem', {
          title: subsystemName,
          display_id: 'SUB-001',
          description: 'Subsystem that provides forced airflow for heat rejection.',
        }),
        createArtifact('temp:comp:fan-controller', 'dfmea.component', {
          title: componentName,
          display_id: 'COMP-001',
          description: 'Controller that commands fan operation based on thermal demand.',
        }),
        createArtifact('temp:fn:control-speed', 'dfmea.function', {
          title: 'Control fan speed based on thermal demand',
          display_id: 'FN-001',
          description: 'Interpret thermal request and command the cooling fan.',
        }),
        createArtifact('temp:req:coolant-temp', 'dfmea.requirement', {
          title: 'Maintain coolant temperature within target range',
          display_id: 'REQ-001',
          description: 'Fan control shall support controller cooling under high thermal load.',
        }),
        createArtifact('temp:char:pwm-output', 'dfmea.characteristic', {
          title: 'Fan PWM command output',
          display_id: 'CHAR-001',
          description: 'Command output must match requested cooling demand.',
        }),
        createArtifact('temp:fm:fan-not-started', 'dfmea.failure_mode', {
          title: 'Fan not started when cooling requested',
          display_id: 'FM-001',
          description: 'Controller does not command fan operation during high thermal demand.',
          severity: failureModeScores.severity,
          occurrence: failureModeScores.occurrence,
          detection: failureModeScores.detection,
          ap,
        }),
        createArtifact('temp:fe:overtemperature', 'dfmea.failure_effect', {
          title: 'Engine temperature exceeds target range',
          display_id: 'FE-001',
          description: 'Reduced cooling can increase thermal stress and trigger derating.',
          severity: 8,
        }),
        createArtifact('temp:fc:sensor-biased-low', 'dfmea.failure_cause', {
          title: 'Temperature signal biased low',
          display_id: 'FC-001',
          description: 'Input signal under-reports temperature and suppresses fan request.',
          occurrence: 4,
          detection: 6,
          ap,
        }),
        createArtifact('temp:act:plausibility-monitor', 'dfmea.action', {
          title: 'Add sensor input plausibility monitor',
          display_id: 'ACT-001',
          description: 'Add diagnostics to detect biased-low temperature input.',
          action_type: 'detection',
          owner: 'Controls engineering',
          due: 'MVP sample',
        }),
        createEdge('temp:sys:thermal-management', 'temp:sub:cooling-fan', 'dfmea.contains'),
        createEdge('temp:sub:cooling-fan', 'temp:comp:fan-controller', 'dfmea.contains'),
        createEdge('temp:comp:fan-controller', 'temp:fn:control-speed', 'dfmea.contains'),
        createEdge('temp:req:coolant-temp', 'temp:fn:control-speed', 'dfmea.requirement_of_function'),
        createEdge('temp:char:pwm-output', 'temp:fn:control-speed', 'dfmea.characteristic_of_function'),
        createEdge('temp:fm:fan-not-started', 'temp:fn:control-speed', 'dfmea.failure_mode_of_function'),
        createEdge('temp:fe:overtemperature', 'temp:fm:fan-not-started', 'dfmea.failure_effect_of_mode'),
        createEdge('temp:fc:sensor-biased-low', 'temp:fm:fan-not-started', 'dfmea.failure_cause_of_mode'),
        createEdge('temp:act:plausibility-monitor', 'temp:fm:fan-not-started', 'dfmea.action_of_failure_mode'),
        createEdge('temp:act:plausibility-monitor', 'temp:fc:sensor-biased-low', 'dfmea.action_targets_cause'),
      ],
    },
    warnings: input.knowledge_refs?.length
      ? []
      : ['No external knowledge references were provided; generated from built-in cooling fan fixture.'],
    evidence_refs: input.knowledge_refs ?? [],
  };
}

export function validateDfmeaGraph(
  artifacts: DfmeaArtifactRecord[],
  edges: DfmeaEdgeRecord[],
): DfmeaValidationResult {
  const activeArtifacts = artifacts.filter((artifact) => artifact.status !== 'logically_deleted');
  const activeEdges = edges.filter((edge) => edge.status !== 'logically_deleted');
  const artifactById = new Map(activeArtifacts.map((artifact) => [artifact.artifactId, artifact]));
  const findings: DfmeaValidationFinding[] = [];
  const displayIds = new Map<string, string>();

  for (const artifact of activeArtifacts) {
    const displayId = readString(artifact.payload.display_id);

    if (displayId !== undefined) {
      const existingArtifactId = displayIds.get(displayId);

      if (existingArtifactId !== undefined) {
        findings.push({
          code: 'DFMEA_DISPLAY_ID_DUPLICATED',
          severity: 'blocking',
          target_type: 'artifact',
          target_id: artifact.artifactId,
          message: `Display id ${displayId} is duplicated.`,
        });
      } else {
        displayIds.set(displayId, artifact.artifactId);
      }
    }

    for (const key of ['severity', 'occurrence', 'detection']) {
      const score = artifact.payload[key];

      if (typeof score === 'number' && (!Number.isInteger(score) || score < 1 || score > 10)) {
        findings.push({
          code: 'DFMEA_SCORE_OUT_OF_RANGE',
          severity: 'blocking',
          target_type: 'artifact',
          target_id: artifact.artifactId,
          message: `${key} must be an integer from 1 to 10.`,
        });
      }
    }
  }

  for (const edge of activeEdges) {
    const source = artifactById.get(edge.sourceArtifactId);
    const target = artifactById.get(edge.targetArtifactId);

    if (source === undefined || target === undefined) {
      findings.push({
        code: 'DFMEA_EDGE_TARGET_MISSING',
        severity: 'blocking',
        target_type: 'edge',
        target_id: edge.edgeId,
        message: 'Edge source or target artifact does not exist.',
      });
      continue;
    }

    const allowed = isAllowedRelation(edge.relationType, source.artifactType, target.artifactType);
    if (!allowed) {
      findings.push({
        code: 'DFMEA_EDGE_TYPE_INVALID',
        severity: 'blocking',
        target_type: 'edge',
        target_id: edge.edgeId,
        message: `Relation ${edge.relationType} is invalid for ${source.artifactType} -> ${target.artifactType}.`,
      });
    }
  }

  return {
    status: findings.some((finding) => finding.severity === 'blocking') ? 'failed' : 'passed',
    findings,
  };
}

export function buildDfmeaWorkingTree(
  artifacts: DfmeaArtifactRecord[],
  edges: DfmeaEdgeRecord[],
): DfmeaWorkingTreePayload {
  const activeArtifacts = artifacts.filter((artifact) => artifact.status !== 'logically_deleted');
  const activeEdges = edges.filter((edge) => edge.status !== 'logically_deleted');
  const nodeByArtifactId = new Map(activeArtifacts.map((artifact) => [artifact.artifactId, createTreeNode(artifact)]));
  const childIds = new Set<string>();

  for (const edge of activeEdges) {
    const parentId = getParentArtifactId(edge);
    const childId = getChildArtifactId(edge);
    const parent = nodeByArtifactId.get(parentId);
    const child = nodeByArtifactId.get(childId);

    if (parent !== undefined && child !== undefined) {
      parent.children.push(child);
      childIds.add(child.artifact_id);
    }
  }

  const roots = [...nodeByArtifactId.values()]
    .filter((node) => !childIds.has(node.artifact_id))
    .sort(compareTreeNodes);

  sortTreeNodes(roots);

  return {
    kind: 'dfmea.working_tree',
    roots,
    artifact_count: activeArtifacts.length,
    edge_count: activeEdges.length,
  };
}

export function buildDfmeaExportPayload(
  artifacts: DfmeaArtifactRecord[],
  edges: DfmeaEdgeRecord[],
): DfmeaExportPayload {
  const activeArtifacts = artifacts.filter((artifact) => artifact.status !== 'logically_deleted');
  const activeEdges = edges.filter((edge) => edge.status !== 'logically_deleted');
  const validation = validateDfmeaGraph(activeArtifacts, activeEdges);

  return {
    kind: 'dfmea.export_payload',
    artifacts: activeArtifacts.map((artifact) => ({
      artifact_id: artifact.artifactId,
      artifact_type: artifact.artifactType,
      payload: artifact.payload,
    })),
    edges: activeEdges.map((edge) => ({
      edge_id: edge.edgeId,
      relation_type: edge.relationType,
      source_artifact_id: edge.sourceArtifactId,
      target_artifact_id: edge.targetArtifactId,
      payload: edge.payload,
    })),
    summary: {
      artifact_count: activeArtifacts.length,
      edge_count: activeEdges.length,
      validation_status: validation.status,
    },
  };
}

function createArtifact(
  tempRef: string,
  artifactType: DfmeaArtifactType,
  afterPayload: JsonObject,
): DfmeaDraftOperation {
  return {
    patchType: 'create_artifact',
    targetType: 'artifact',
    tempRef,
    artifactType,
    afterPayload,
  };
}

function createEdge(
  sourceTempRef: string,
  targetTempRef: string,
  relationType: string,
): DfmeaDraftOperation {
  return {
    patchType: 'create_edge',
    targetType: 'edge',
    relationType,
    sourceTempRef,
    targetTempRef,
    afterPayload: {},
  };
}

function createTreeNode(artifact: DfmeaArtifactRecord): DfmeaTreeNode {
  const displayId = readString(artifact.payload.display_id);
  const node: DfmeaTreeNode = {
    artifact_id: artifact.artifactId,
    type: artifact.artifactType,
    title: readString(artifact.payload.title) ?? artifact.artifactType,
    badges: createBadges(artifact.payload),
    children: [],
  };

  if (displayId !== undefined) {
    node.display_id = displayId;
  }

  return node;
}

function createBadges(payload: JsonObject): JsonObject {
  const badges: JsonObject = {};

  for (const key of ['severity', 'occurrence', 'detection', 'ap']) {
    const value = payload[key];

    if (isJsonValue(value)) {
      badges[key] = value;
    }
  }

  return badges;
}

function getParentArtifactId(edge: DfmeaEdgeRecord): string {
  if (edge.relationType === 'dfmea.contains') {
    return edge.sourceArtifactId;
  }

  return edge.targetArtifactId;
}

function getChildArtifactId(edge: DfmeaEdgeRecord): string {
  if (edge.relationType === 'dfmea.contains') {
    return edge.targetArtifactId;
  }

  return edge.sourceArtifactId;
}

function isAllowedRelation(relationType: string, sourceType: string, targetType: string): boolean {
  return (
    (relationType === 'dfmea.contains' &&
      ((sourceType === 'dfmea.system' && targetType === 'dfmea.subsystem') ||
        (sourceType === 'dfmea.subsystem' && targetType === 'dfmea.component') ||
        (sourceType === 'dfmea.component' && targetType === 'dfmea.function'))) ||
    (relationType === 'dfmea.requirement_of_function' &&
      sourceType === 'dfmea.requirement' &&
      targetType === 'dfmea.function') ||
    (relationType === 'dfmea.characteristic_of_function' &&
      sourceType === 'dfmea.characteristic' &&
      targetType === 'dfmea.function') ||
    (relationType === 'dfmea.failure_mode_of_function' &&
      sourceType === 'dfmea.failure_mode' &&
      targetType === 'dfmea.function') ||
    (relationType === 'dfmea.failure_effect_of_mode' &&
      sourceType === 'dfmea.failure_effect' &&
      targetType === 'dfmea.failure_mode') ||
    (relationType === 'dfmea.failure_cause_of_mode' &&
      sourceType === 'dfmea.failure_cause' &&
      targetType === 'dfmea.failure_mode') ||
    (relationType === 'dfmea.action_of_failure_mode' &&
      sourceType === 'dfmea.action' &&
      targetType === 'dfmea.failure_mode') ||
    (relationType === 'dfmea.action_targets_cause' &&
      sourceType === 'dfmea.action' &&
      targetType === 'dfmea.failure_cause')
  );
}

function sortTreeNodes(nodes: DfmeaTreeNode[]): void {
  nodes.sort(compareTreeNodes);

  for (const node of nodes) {
    sortTreeNodes(node.children);
  }
}

function compareTreeNodes(left: DfmeaTreeNode, right: DfmeaTreeNode): number {
  return (left.display_id ?? left.title).localeCompare(right.display_id ?? right.title);
}

function readString(value: JsonValue | undefined): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function isJsonValue(value: JsonValue | undefined): value is JsonValue {
  return value !== undefined;
}
