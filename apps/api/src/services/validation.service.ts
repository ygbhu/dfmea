import {
  createJsonSchemaValidator,
  getProjectionFreshness,
  type JsonSchema,
  type JsonValue,
  type ProjectionFreshness,
  type ProjectionStatus,
  type StructuredValidationResult,
  type ValidationFinding,
  type ValidationResult,
  type ValidationSeverity,
} from '@dfmea/shared';

export interface ProjectionFreshnessInput {
  projectionId?: string;
  sourceRevision: number;
  currentWorkspaceRevision: number;
  status: ProjectionStatus;
  consumer: 'ai' | 'ui' | 'export';
}

export class ValidationService {
  private readonly schemaValidator = createJsonSchemaValidator({ strict: false });

  validateJsonSchema(schema: JsonSchema, data: JsonValue): ValidationResult {
    return this.schemaValidator.validate(schema, data);
  }

  validateProjectionFreshness(input: ProjectionFreshnessInput): StructuredValidationResult {
    const freshness = getProjectionFreshness(input.sourceRevision, input.currentWorkspaceRevision);
    const isFresh = freshness === 'fresh' && input.status === 'fresh';

    if (isFresh) {
      return createStructuredValidationResult([]);
    }

    const severity: ValidationSeverity = input.consumer === 'ui' ? 'warning' : 'blocking';
    const finding: ValidationFinding = {
      code: 'PROJECTION_STALE',
      severity,
      targetType: 'projection',
      message: 'Projection is stale for the requested consumer.',
      details: {
        source_revision: input.sourceRevision,
        current_workspace_revision: input.currentWorkspaceRevision,
        projection_status: input.status,
        consumer: input.consumer,
        freshness,
      },
    };

    if (input.projectionId !== undefined) {
      finding.targetId = input.projectionId;
    }

    return createStructuredValidationResult([finding]);
  }

  getProjectionFreshness(sourceRevision: number, currentWorkspaceRevision: number): ProjectionFreshness {
    return getProjectionFreshness(sourceRevision, currentWorkspaceRevision);
  }
}

export function createStructuredValidationResult(
  findings: ValidationFinding[],
): StructuredValidationResult {
  const severity = highestSeverity(findings);

  return {
    status: findings.some((finding) => finding.severity === 'blocking') ? 'failed' : 'passed',
    severity,
    summary: findings.length ? 'Validation completed with findings.' : 'Validation passed.',
    findings,
  };
}

function highestSeverity(findings: ValidationFinding[]): ValidationSeverity {
  if (findings.some((finding) => finding.severity === 'blocking')) {
    return 'blocking';
  }

  if (findings.some((finding) => finding.severity === 'warning')) {
    return 'warning';
  }

  return 'info';
}
