import { and, eq } from 'drizzle-orm';
import type { JsonObject, ProjectionFreshness, ProjectionStatus } from '@dfmea/shared';
import type { AppDatabase } from '../db/client';
import { createId } from '../db/id';
import { artifactEdges, artifacts, projections, projects } from '../db/schema';
import { ValidationService } from './validation.service';

export type ProjectionConsumer = 'ai' | 'ui' | 'export';

export interface ProjectionHandlerContext {
  db: AppDatabase;
  workspaceId: string;
  projectId: string;
  pluginId: string;
  kind: string;
  category: string;
  scopeType: string;
  scopeId: string;
  currentWorkspaceRevision: number;
}

export interface ProjectionHandlerResult {
  payload: JsonObject;
  summary?: string;
  metadata?: JsonObject;
}

export type ProjectionHandler = (
  context: ProjectionHandlerContext,
) => Promise<ProjectionHandlerResult>;

export interface ProjectionRebuildInput {
  workspaceId: string;
  projectId: string;
  pluginId: string;
  kind: string;
  category: string;
  scopeType: string;
  scopeId: string;
}

export interface ProjectionReadInput extends ProjectionRebuildInput {
  consumer: ProjectionConsumer;
}

export interface ProjectionReadResult {
  projection: typeof projections.$inferSelect;
  freshness: ProjectionFreshness;
  validationStatus: 'passed' | 'failed';
  currentWorkspaceRevision: number;
}

export type ProjectionServiceErrorCode =
  | 'PROJECT_NOT_FOUND'
  | 'PROJECTION_NOT_FOUND'
  | 'PROJECTION_HANDLER_NOT_FOUND'
  | 'PROJECTION_STALE'
  | 'PROJECTION_REBUILD_FAILED';

export class ProjectionServiceError extends Error {
  readonly code: ProjectionServiceErrorCode;
  readonly details: Record<string, unknown>;

  constructor(code: ProjectionServiceErrorCode, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ProjectionServiceError';
    this.code = code;
    this.details = details;
    Object.setPrototypeOf(this, ProjectionServiceError.prototype);
  }
}

export class ProjectionService {
  private readonly handlers = new Map<string, ProjectionHandler>();
  private readonly validationService: ValidationService;
  private readonly events: string[] = [];

  constructor(private readonly db: AppDatabase, validationService = new ValidationService()) {
    this.validationService = validationService;
    this.registerHandler('platform', 'test_project_summary', createPlatformTestProjectionHandler());
  }

  registerHandler(pluginId: string, kind: string, handler: ProjectionHandler): void {
    this.handlers.set(this.handlerKey(pluginId, kind), handler);
  }

  listEvents(): string[] {
    return [...this.events];
  }

  async markProjectProjectionsStale(projectId: string): Promise<void> {
    await this.db
      .update(projections)
      .set({
        status: 'stale',
        updatedAt: new Date(),
      })
      .where(eq(projections.projectId, projectId));
    this.events.push('projection.dirty');
  }

  async getProjection(input: ProjectionReadInput): Promise<ProjectionReadResult> {
    const project = await this.getProject(input.projectId);
    const existingProjection = await this.findProjection(input);

    if (existingProjection === undefined) {
      if (input.consumer === 'ui') {
        return this.rebuildProjectProjection(input);
      }

      return this.rebuildProjectProjection(input);
    }

    const validation = this.validationService.validateProjectionFreshness({
      projectionId: existingProjection.projectionId,
      sourceRevision: existingProjection.sourceRevision,
      currentWorkspaceRevision: project.workspaceRevision,
      status: existingProjection.status,
      consumer: input.consumer,
    });

    if (validation.findings.length === 0) {
      return {
        projection: existingProjection,
        freshness: 'fresh',
        validationStatus: 'passed',
        currentWorkspaceRevision: project.workspaceRevision,
      };
    }

    this.events.push('projection.stale_detected');

    if (input.consumer === 'ui') {
      return {
        projection: existingProjection,
        freshness: 'stale',
        validationStatus: validation.status,
        currentWorkspaceRevision: project.workspaceRevision,
      };
    }

    const rebuiltProjection = await this.rebuildProjectProjection(input);

    if (rebuiltProjection.freshness !== 'fresh') {
      throw new ProjectionServiceError('PROJECTION_STALE', 'Projection remains stale after rebuild.', {
        project_id: input.projectId,
        plugin_id: input.pluginId,
        kind: input.kind,
      });
    }

    return rebuiltProjection;
  }

  async getFreshProjection(input: Omit<ProjectionReadInput, 'consumer'>): Promise<ProjectionReadResult> {
    return this.getProjection({ ...input, consumer: 'ai' });
  }

  async rebuildProjectProjection(input: ProjectionRebuildInput): Promise<ProjectionReadResult> {
    const project = await this.getProject(input.projectId);
    const handler = this.handlers.get(this.handlerKey(input.pluginId, input.kind));

    if (handler === undefined) {
      throw new ProjectionServiceError('PROJECTION_HANDLER_NOT_FOUND', 'Projection handler is not registered.', {
        plugin_id: input.pluginId,
        kind: input.kind,
      });
    }

    const existingProjection = await this.findProjection(input);
    this.events.push('projection.rebuild.started');

    if (existingProjection !== undefined) {
      await this.db
        .update(projections)
        .set({
          status: 'rebuilding',
          updatedAt: new Date(),
        })
        .where(eq(projections.projectionId, existingProjection.projectionId));
    }

    try {
      const handlerResult = await handler({
        db: this.db,
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        pluginId: input.pluginId,
        kind: input.kind,
        category: input.category,
        scopeType: input.scopeType,
        scopeId: input.scopeId,
        currentWorkspaceRevision: project.workspaceRevision,
      });

      const savedProjection = await this.saveProjection(input, {
        existingProjectionId: existingProjection?.projectionId,
        sourceRevision: project.workspaceRevision,
        payload: handlerResult.payload,
        summary: handlerResult.summary,
        metadata: handlerResult.metadata,
      });
      this.events.push('projection.rebuild.completed');

      return {
        projection: savedProjection,
        freshness: 'fresh',
        validationStatus: 'passed',
        currentWorkspaceRevision: project.workspaceRevision,
      };
    } catch (error) {
      if (existingProjection !== undefined) {
        await this.db
          .update(projections)
          .set({
            status: 'failed',
            updatedAt: new Date(),
          })
          .where(eq(projections.projectionId, existingProjection.projectionId));
      }

      this.events.push('projection.rebuild.failed');
      throw new ProjectionServiceError('PROJECTION_REBUILD_FAILED', 'Projection rebuild failed.', {
        project_id: input.projectId,
        plugin_id: input.pluginId,
        kind: input.kind,
        cause: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private async getProject(projectId: string): Promise<typeof projects.$inferSelect> {
    const [project] = await this.db.select().from(projects).where(eq(projects.projectId, projectId));

    if (!project) {
      throw new ProjectionServiceError('PROJECT_NOT_FOUND', 'Project does not exist.', {
        project_id: projectId,
      });
    }

    return project;
  }

  private async findProjection(
    input: ProjectionRebuildInput,
  ): Promise<typeof projections.$inferSelect | undefined> {
    const [projection] = await this.db
      .select()
      .from(projections)
      .where(
        and(
          eq(projections.projectId, input.projectId),
          eq(projections.pluginId, input.pluginId),
          eq(projections.kind, input.kind),
          eq(projections.scopeType, input.scopeType),
          eq(projections.scopeId, input.scopeId),
        ),
      );

    return projection;
  }

  private async saveProjection(
    input: ProjectionRebuildInput,
    data: {
      existingProjectionId: string | undefined;
      sourceRevision: number;
      payload: JsonObject;
      summary: string | undefined;
      metadata: JsonObject | undefined;
    },
  ): Promise<typeof projections.$inferSelect> {
    const values = {
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      pluginId: input.pluginId,
      kind: input.kind,
      category: input.category,
      scopeType: input.scopeType,
      scopeId: input.scopeId,
      sourceRevision: data.sourceRevision,
      status: 'fresh' as ProjectionStatus,
      payload: data.payload,
      summary: data.summary,
      metadata: data.metadata ?? {},
      builtAt: new Date(),
      updatedAt: new Date(),
    };

    if (data.existingProjectionId !== undefined) {
      const [updatedProjection] = await this.db
        .update(projections)
        .set(values)
        .where(eq(projections.projectionId, data.existingProjectionId))
        .returning();

      if (updatedProjection === undefined) {
        throw new ProjectionServiceError('PROJECTION_NOT_FOUND', 'Projection disappeared during rebuild.', {
          projection_id: data.existingProjectionId,
        });
      }

      return updatedProjection;
    }

    const [createdProjection] = await this.db
      .insert(projections)
      .values({
        projectionId: createId('projx'),
        ...values,
      })
      .returning();

    if (createdProjection === undefined) {
      throw new ProjectionServiceError('PROJECTION_REBUILD_FAILED', 'Projection insert returned no row.', {
        project_id: input.projectId,
        plugin_id: input.pluginId,
        kind: input.kind,
      });
    }

    return createdProjection;
  }

  private handlerKey(pluginId: string, kind: string): string {
    return `${pluginId}.${kind}`;
  }
}

function createPlatformTestProjectionHandler(): ProjectionHandler {
  return async (context) => {
    const artifactRows = await context.db
      .select()
      .from(artifacts)
      .where(eq(artifacts.projectId, context.projectId));
    const edgeRows = await context.db
      .select()
      .from(artifactEdges)
      .where(eq(artifactEdges.projectId, context.projectId));

    return {
      payload: {
        projection_kind: context.kind,
        project_id: context.projectId,
        workspace_revision: context.currentWorkspaceRevision,
        artifact_count: artifactRows.length,
        edge_count: edgeRows.length,
      },
      summary: `Project ${context.projectId} has ${artifactRows.length} artifacts and ${edgeRows.length} edges.`,
    };
  };
}
