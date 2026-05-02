import { eq } from 'drizzle-orm';
import type { JsonObject } from '@dfmea/shared';
import type { AppDatabase } from '../db/client';
import { createId } from '../db/id';
import { artifactEdges, artifacts } from '../db/schema';

export class ArtifactRepository {
  constructor(private readonly db: AppDatabase) {}

  async createArtifact(input: {
    workspaceId: string;
    projectId: string;
    pluginId: string;
    artifactType: string;
    schemaVersion: string;
    revision: number;
    payload: JsonObject;
    createdBy?: string;
  }) {
    const [artifact] = await this.db
      .insert(artifacts)
      .values({
        artifactId: createId('art'),
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        pluginId: input.pluginId,
        artifactType: input.artifactType,
        schemaVersion: input.schemaVersion,
        revision: input.revision,
        payload: input.payload,
        createdBy: input.createdBy,
        updatedBy: input.createdBy,
      })
      .returning();

    return artifact;
  }

  async createEdge(input: {
    workspaceId: string;
    projectId: string;
    pluginId: string;
    sourceArtifactId: string;
    targetArtifactId: string;
    relationType: string;
    schemaVersion: string;
    revision: number;
    payload?: JsonObject;
    createdBy?: string;
  }) {
    const [edge] = await this.db
      .insert(artifactEdges)
      .values({
        edgeId: createId('edge'),
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        pluginId: input.pluginId,
        sourceArtifactId: input.sourceArtifactId,
        targetArtifactId: input.targetArtifactId,
        relationType: input.relationType,
        schemaVersion: input.schemaVersion,
        revision: input.revision,
        payload: input.payload ?? {},
        createdBy: input.createdBy,
        updatedBy: input.createdBy,
      })
      .returning();

    return edge;
  }

  async listProjectArtifacts(projectId: string) {
    return this.db.select().from(artifacts).where(eq(artifacts.projectId, projectId));
  }

  async listProjectEdges(projectId: string) {
    return this.db.select().from(artifactEdges).where(eq(artifactEdges.projectId, projectId));
  }
}
