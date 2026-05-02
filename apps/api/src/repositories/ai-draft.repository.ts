import { and, eq } from 'drizzle-orm';
import type { JsonObject } from '@dfmea/shared';
import type { AppDatabase } from '../db/client';
import { createId } from '../db/id';
import {
  aiDraftBatches,
  artifactEdges,
  artifacts,
  draftPatches,
  projects,
  projections,
  workspaceRevisionEvents,
} from '../db/schema';

export interface ApplyDraftResult {
  draftBatchId: string;
  fromRevision: number;
  toRevision: number;
  artifactIds: string[];
  edgeIds: string[];
}

export type AiDraftRepositoryErrorCode =
  | 'DRAFT_BATCH_NOT_FOUND'
  | 'DRAFT_BATCH_NOT_PENDING'
  | 'DRAFT_BASE_REVISION_CONFLICT'
  | 'DRAFT_PATCH_INVALID'
  | 'DRAFT_TARGET_NOT_FOUND'
  | 'PROJECT_NOT_FOUND';

export class AiDraftRepositoryError extends Error {
  readonly code: AiDraftRepositoryErrorCode;
  readonly details: Record<string, unknown>;

  constructor(code: AiDraftRepositoryErrorCode, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'AiDraftRepositoryError';
    this.code = code;
    this.details = details;
    Object.setPrototypeOf(this, AiDraftRepositoryError.prototype);
  }
}

export class AiDraftRepository {
  constructor(private readonly db: AppDatabase) {}

  async createDraftBatch(input: {
    workspaceId: string;
    projectId: string;
    pluginId: string;
    title: string;
    goal: string;
    baseWorkspaceRevision: number;
    sessionId?: string | undefined;
    runId?: string | undefined;
    createdBy?: string | undefined;
    summary?: JsonObject | undefined;
  }) {
    const [batch] = await this.db
      .insert(aiDraftBatches)
      .values({
        draftBatchId: createId('draft'),
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        pluginId: input.pluginId,
        title: input.title,
        goal: input.goal,
        baseWorkspaceRevision: input.baseWorkspaceRevision,
        sessionId: input.sessionId,
        runId: input.runId,
        createdBy: input.createdBy,
        summary: input.summary ?? {},
      })
      .returning();

    return batch;
  }

  async createDraftPatch(input: {
    draftBatchId: string;
    workspaceId: string;
    projectId: string;
    pluginId: string;
    patchType: 'create_artifact' | 'update_artifact' | 'create_edge' | 'update_edge' | 'logical_delete';
    targetType: 'artifact' | 'edge';
    artifactType?: string | undefined;
    relationType?: string | undefined;
    targetId?: string | undefined;
    tempRef?: string | undefined;
    sourceTempRef?: string | undefined;
    targetTempRef?: string | undefined;
    sourceArtifactId?: string | undefined;
    targetArtifactId?: string | undefined;
    beforePayload?: JsonObject | undefined;
    afterPayload?: JsonObject | undefined;
    payloadPatch?: JsonObject | undefined;
  }) {
    const [patch] = await this.db
      .insert(draftPatches)
      .values({
        draftPatchId: createId('patch'),
        draftBatchId: input.draftBatchId,
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        pluginId: input.pluginId,
        patchType: input.patchType,
        targetType: input.targetType,
        targetId: input.targetId,
        tempRef: input.tempRef,
        artifactType: input.artifactType,
        relationType: input.relationType,
        sourceTempRef: input.sourceTempRef,
        targetTempRef: input.targetTempRef,
        sourceArtifactId: input.sourceArtifactId,
        targetArtifactId: input.targetArtifactId,
        beforePayload: input.beforePayload,
        afterPayload: input.afterPayload,
        payloadPatch: input.payloadPatch,
      })
      .returning();

    return patch;
  }

  async getDraftBatch(draftBatchId: string) {
    const [batch] = await this.db
      .select()
      .from(aiDraftBatches)
      .where(eq(aiDraftBatches.draftBatchId, draftBatchId));

    return batch;
  }

  async listDraftPatches(draftBatchId: string) {
    return this.db.select().from(draftPatches).where(eq(draftPatches.draftBatchId, draftBatchId));
  }

  async editDraftPatch(input: { draftPatchId: string; afterPayload: JsonObject; editedBy?: string }) {
    return this.db.transaction(async (tx) => {
      const [patch] = await tx
        .select()
        .from(draftPatches)
        .where(eq(draftPatches.draftPatchId, input.draftPatchId));

      if (!patch) {
        throw new AiDraftRepositoryError('DRAFT_PATCH_INVALID', 'Draft patch does not exist.', {
          draft_patch_id: input.draftPatchId,
        });
      }

      const [batch] = await tx
        .select()
        .from(aiDraftBatches)
        .where(eq(aiDraftBatches.draftBatchId, patch.draftBatchId));

      assertPendingBatch(batch, patch.draftBatchId);

      if (patch.status !== 'pending') {
        throw new AiDraftRepositoryError('DRAFT_PATCH_INVALID', 'Draft patch must be pending to edit.', {
          draft_patch_id: patch.draftPatchId,
          status: patch.status,
        });
      }

      const [updatedPatch] = await tx
        .update(draftPatches)
        .set({
          afterPayload: input.afterPayload,
          editedBy: input.editedBy,
          updatedAt: new Date(),
        })
        .where(eq(draftPatches.draftPatchId, patch.draftPatchId))
        .returning();

      return updatedPatch;
    });
  }

  async rejectDraftBatch(input: { draftBatchId: string; rejectedBy?: string }) {
    return this.db.transaction(async (tx) => {
      const [batch] = await tx
        .select()
        .from(aiDraftBatches)
        .where(eq(aiDraftBatches.draftBatchId, input.draftBatchId));

      assertPendingBatch(batch, input.draftBatchId);

      await tx
        .update(draftPatches)
        .set({
          status: 'rejected',
          updatedAt: new Date(),
        })
        .where(eq(draftPatches.draftBatchId, batch.draftBatchId));

      const [updatedBatch] = await tx
        .update(aiDraftBatches)
        .set({
          status: 'rejected',
          rejectedBy: input.rejectedBy,
          rejectedAt: new Date(),
          updatedAt: new Date(),
        })
        .where(eq(aiDraftBatches.draftBatchId, batch.draftBatchId))
        .returning();

      return updatedBatch;
    });
  }

  async rejectDraftPatch(input: { draftPatchId: string; rejectedBy?: string }) {
    return this.db.transaction(async (tx) => {
      const [patch] = await tx
        .select()
        .from(draftPatches)
        .where(eq(draftPatches.draftPatchId, input.draftPatchId));

      if (!patch) {
        throw new AiDraftRepositoryError('DRAFT_PATCH_INVALID', 'Draft patch does not exist.', {
          draft_patch_id: input.draftPatchId,
        });
      }

      const [batch] = await tx
        .select()
        .from(aiDraftBatches)
        .where(eq(aiDraftBatches.draftBatchId, patch.draftBatchId));

      assertPendingBatch(batch, patch.draftBatchId);

      if (patch.status !== 'pending') {
        throw new AiDraftRepositoryError('DRAFT_PATCH_INVALID', 'Draft patch must be pending to reject.', {
          draft_patch_id: patch.draftPatchId,
          status: patch.status,
        });
      }

      const [updatedPatch] = await tx
        .update(draftPatches)
        .set({
          status: 'rejected',
          editedBy: input.rejectedBy,
          updatedAt: new Date(),
        })
        .where(eq(draftPatches.draftPatchId, patch.draftPatchId))
        .returning();

      return updatedPatch;
    });
  }

  async applyDraftBatch(input: { draftBatchId: string; appliedBy?: string }): Promise<ApplyDraftResult> {
    return this.db.transaction(async (tx) => {
      const [batch] = await tx
        .select()
        .from(aiDraftBatches)
        .where(eq(aiDraftBatches.draftBatchId, input.draftBatchId));

      assertPendingBatch(batch, input.draftBatchId);

      const [project] = await tx.select().from(projects).where(eq(projects.projectId, batch.projectId));
      if (!project) {
        throw new AiDraftRepositoryError('PROJECT_NOT_FOUND', 'Project does not exist.', {
          project_id: batch.projectId,
        });
      }

      if (project.workspaceRevision !== batch.baseWorkspaceRevision) {
        throw new AiDraftRepositoryError('DRAFT_BASE_REVISION_CONFLICT', 'Draft base revision is stale.', {
          draft_batch_id: batch.draftBatchId,
          base_workspace_revision: batch.baseWorkspaceRevision,
          current_workspace_revision: project.workspaceRevision,
        });
      }

      const patches = await tx
        .select()
        .from(draftPatches)
        .where(eq(draftPatches.draftBatchId, batch.draftBatchId));
      const pendingPatches = patches.filter((patch) => patch.status === 'pending');
      const nextRevision = project.workspaceRevision + 1;
      const tempRefToArtifactId = new Map<string, string>();
      const artifactIds: string[] = [];
      const edgeIds: string[] = [];

      if (!pendingPatches.length) {
        throw new AiDraftRepositoryError('DRAFT_PATCH_INVALID', 'Draft batch has no pending patches.', {
          draft_batch_id: batch.draftBatchId,
        });
      }

      for (const patch of pendingPatches) {
        if (patch.patchType !== 'create_artifact') {
          continue;
        }

        if (!patch.artifactType || !patch.afterPayload) {
          throw new AiDraftRepositoryError(
            'DRAFT_PATCH_INVALID',
            'create_artifact patch requires artifact_type and after_payload.',
            { draft_patch_id: patch.draftPatchId },
          );
        }

        const artifactId = patch.targetId ?? createId('art');
        await tx.insert(artifacts).values({
          artifactId,
          workspaceId: batch.workspaceId,
          projectId: batch.projectId,
          pluginId: batch.pluginId,
          artifactType: patch.artifactType,
          schemaVersion: '1.0.0',
          revision: nextRevision,
          payload: patch.afterPayload,
          createdBy: input.appliedBy,
          updatedBy: input.appliedBy,
        });

        if (patch.tempRef) {
          tempRefToArtifactId.set(patch.tempRef, artifactId);
        }
        artifactIds.push(artifactId);

        await tx
          .update(draftPatches)
          .set({
            status: 'applied',
            targetId: artifactId,
            appliedResult: { artifactId },
            updatedAt: new Date(),
          })
          .where(eq(draftPatches.draftPatchId, patch.draftPatchId));
      }

      for (const patch of pendingPatches) {
        if (patch.patchType === 'create_artifact') {
          continue;
        }

        if (patch.patchType === 'update_artifact') {
          if (!patch.targetId || !patch.afterPayload) {
            throw new AiDraftRepositoryError(
              'DRAFT_PATCH_INVALID',
              'update_artifact patch requires target_id and after_payload.',
              { draft_patch_id: patch.draftPatchId },
            );
          }

          const [updatedArtifact] = await tx
            .update(artifacts)
            .set({
              payload: patch.afterPayload,
              revision: nextRevision,
              status: 'active',
              updatedBy: input.appliedBy,
              updatedAt: new Date(),
            })
            .where(
              and(
                eq(artifacts.artifactId, patch.targetId),
                eq(artifacts.projectId, batch.projectId),
              ),
            )
            .returning();

          if (!updatedArtifact) {
            throw new AiDraftRepositoryError('DRAFT_TARGET_NOT_FOUND', 'Artifact target does not exist.', {
              draft_patch_id: patch.draftPatchId,
              target_id: patch.targetId,
            });
          }

          artifactIds.push(updatedArtifact.artifactId);

          await tx
            .update(draftPatches)
            .set({
              status: 'applied',
              appliedResult: { artifactId: updatedArtifact.artifactId },
              updatedAt: new Date(),
            })
            .where(eq(draftPatches.draftPatchId, patch.draftPatchId));

          continue;
        }

        if (patch.patchType === 'create_edge') {
          const sourceArtifactId = resolveArtifactReference(
            patch.sourceArtifactId,
            patch.sourceTempRef,
            tempRefToArtifactId,
          );
          const targetArtifactId = resolveArtifactReference(
            patch.targetArtifactId,
            patch.targetTempRef,
            tempRefToArtifactId,
          );

          if (!sourceArtifactId || !targetArtifactId || !patch.relationType) {
            throw new AiDraftRepositoryError(
              'DRAFT_PATCH_INVALID',
              'create_edge patch requires source, target, and relation_type.',
              { draft_patch_id: patch.draftPatchId },
            );
          }

          const edgeId = patch.targetId ?? createId('edge');
          await tx.insert(artifactEdges).values({
            edgeId,
            workspaceId: batch.workspaceId,
            projectId: batch.projectId,
            pluginId: batch.pluginId,
            sourceArtifactId,
            targetArtifactId,
            relationType: patch.relationType,
            schemaVersion: '1.0.0',
            revision: nextRevision,
            payload: patch.afterPayload ?? {},
            createdBy: input.appliedBy,
            updatedBy: input.appliedBy,
          });

          edgeIds.push(edgeId);

          await tx
            .update(draftPatches)
            .set({
              status: 'applied',
              targetId: edgeId,
              appliedResult: { edgeId, sourceArtifactId, targetArtifactId },
              updatedAt: new Date(),
            })
            .where(eq(draftPatches.draftPatchId, patch.draftPatchId));

          continue;
        }

        if (patch.patchType === 'update_edge') {
          if (!patch.targetId) {
            throw new AiDraftRepositoryError(
              'DRAFT_PATCH_INVALID',
              'update_edge patch requires target_id.',
              { draft_patch_id: patch.draftPatchId },
            );
          }

          const [existingEdge] = await tx
            .select()
            .from(artifactEdges)
            .where(
              and(
                eq(artifactEdges.edgeId, patch.targetId),
                eq(artifactEdges.projectId, batch.projectId),
              ),
            );

          if (!existingEdge) {
            throw new AiDraftRepositoryError('DRAFT_TARGET_NOT_FOUND', 'Edge target does not exist.', {
              draft_patch_id: patch.draftPatchId,
              target_id: patch.targetId,
            });
          }

          const sourceArtifactId =
            resolveArtifactReference(patch.sourceArtifactId, patch.sourceTempRef, tempRefToArtifactId) ??
            existingEdge.sourceArtifactId;
          const targetArtifactId =
            resolveArtifactReference(patch.targetArtifactId, patch.targetTempRef, tempRefToArtifactId) ??
            existingEdge.targetArtifactId;

          const [updatedEdge] = await tx
            .update(artifactEdges)
            .set({
              sourceArtifactId,
              targetArtifactId,
              relationType: patch.relationType ?? existingEdge.relationType,
              payload: patch.afterPayload ?? existingEdge.payload,
              revision: nextRevision,
              status: 'active',
              updatedBy: input.appliedBy,
              updatedAt: new Date(),
            })
            .where(eq(artifactEdges.edgeId, existingEdge.edgeId))
            .returning();

          if (!updatedEdge) {
            throw new AiDraftRepositoryError('DRAFT_TARGET_NOT_FOUND', 'Edge target does not exist.', {
              draft_patch_id: patch.draftPatchId,
              target_id: patch.targetId,
            });
          }

          edgeIds.push(updatedEdge.edgeId);

          await tx
            .update(draftPatches)
            .set({
              status: 'applied',
              appliedResult: { edgeId: updatedEdge.edgeId, sourceArtifactId, targetArtifactId },
              updatedAt: new Date(),
            })
            .where(eq(draftPatches.draftPatchId, patch.draftPatchId));

          continue;
        }

        if (patch.patchType === 'logical_delete') {
          if (!patch.targetId) {
            throw new AiDraftRepositoryError(
              'DRAFT_PATCH_INVALID',
              'logical_delete patch requires target_id.',
              { draft_patch_id: patch.draftPatchId },
            );
          }

          if (patch.targetType === 'artifact') {
            const [deletedArtifact] = await tx
              .update(artifacts)
              .set({
                status: 'logically_deleted',
                revision: nextRevision,
                updatedBy: input.appliedBy,
                updatedAt: new Date(),
              })
              .where(
                and(
                  eq(artifacts.artifactId, patch.targetId),
                  eq(artifacts.projectId, batch.projectId),
                ),
              )
              .returning();

            if (!deletedArtifact) {
              throw new AiDraftRepositoryError('DRAFT_TARGET_NOT_FOUND', 'Artifact target does not exist.', {
                draft_patch_id: patch.draftPatchId,
                target_id: patch.targetId,
              });
            }

            artifactIds.push(deletedArtifact.artifactId);

            await tx
              .update(draftPatches)
              .set({
                status: 'applied',
                appliedResult: { artifactId: deletedArtifact.artifactId },
                updatedAt: new Date(),
              })
              .where(eq(draftPatches.draftPatchId, patch.draftPatchId));

            continue;
          }

          if (patch.targetType === 'edge') {
            const [deletedEdge] = await tx
              .update(artifactEdges)
              .set({
                status: 'logically_deleted',
                revision: nextRevision,
                updatedBy: input.appliedBy,
                updatedAt: new Date(),
              })
              .where(
                and(
                  eq(artifactEdges.edgeId, patch.targetId),
                  eq(artifactEdges.projectId, batch.projectId),
                ),
              )
              .returning();

            if (!deletedEdge) {
              throw new AiDraftRepositoryError('DRAFT_TARGET_NOT_FOUND', 'Edge target does not exist.', {
                draft_patch_id: patch.draftPatchId,
                target_id: patch.targetId,
              });
            }

            edgeIds.push(deletedEdge.edgeId);

            await tx
              .update(draftPatches)
              .set({
                status: 'applied',
                appliedResult: { edgeId: deletedEdge.edgeId },
                updatedAt: new Date(),
              })
              .where(eq(draftPatches.draftPatchId, patch.draftPatchId));

            continue;
          }

          throw new AiDraftRepositoryError('DRAFT_PATCH_INVALID', 'logical_delete target_type is invalid.', {
            draft_patch_id: patch.draftPatchId,
            target_type: patch.targetType,
          });
        }

        throw new AiDraftRepositoryError('DRAFT_PATCH_INVALID', 'Unsupported draft patch type.', {
          draft_patch_id: patch.draftPatchId,
          patch_type: patch.patchType,
        });
      }

      await tx
        .update(projects)
        .set({
          workspaceRevision: nextRevision,
          updatedAt: new Date(),
        })
        .where(eq(projects.projectId, batch.projectId));

      await tx
        .update(projections)
        .set({
          status: 'stale',
          updatedAt: new Date(),
        })
        .where(eq(projections.projectId, batch.projectId));

      await tx.insert(workspaceRevisionEvents).values({
        eventId: createId('rev'),
        workspaceId: batch.workspaceId,
        projectId: batch.projectId,
        fromRevision: project.workspaceRevision,
        toRevision: nextRevision,
        draftBatchId: batch.draftBatchId,
        runId: batch.runId,
        summary: `Applied AI draft batch ${batch.draftBatchId}`,
        createdBy: input.appliedBy,
      });

      await tx
        .update(aiDraftBatches)
        .set({
          status: 'applied',
          targetWorkspaceRevision: nextRevision,
          appliedBy: input.appliedBy,
          appliedAt: new Date(),
          updatedAt: new Date(),
        })
        .where(eq(aiDraftBatches.draftBatchId, batch.draftBatchId));

      return {
        draftBatchId: batch.draftBatchId,
        fromRevision: project.workspaceRevision,
        toRevision: nextRevision,
        artifactIds,
        edgeIds,
      };
    });
  }
}

function assertPendingBatch(
  batch: typeof aiDraftBatches.$inferSelect | undefined,
  draftBatchId: string,
): asserts batch is typeof aiDraftBatches.$inferSelect {
  if (!batch) {
    throw new AiDraftRepositoryError('DRAFT_BATCH_NOT_FOUND', 'AI draft batch does not exist.', {
      draft_batch_id: draftBatchId,
    });
  }

  if (batch.status !== 'pending') {
    throw new AiDraftRepositoryError('DRAFT_BATCH_NOT_PENDING', 'AI draft batch must be pending.', {
      draft_batch_id: batch.draftBatchId,
      status: batch.status,
    });
  }
}

function resolveArtifactReference(
  artifactId: string | null,
  tempRef: string | null,
  tempRefToArtifactId: Map<string, string>,
): string | undefined {
  return artifactId ?? (tempRef ? tempRefToArtifactId.get(tempRef) : undefined);
}
