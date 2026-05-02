import { eq } from 'drizzle-orm';
import {
  buildDfmeaExportPayload,
  buildDfmeaWorkingTree,
  type DfmeaArtifactRecord,
  type DfmeaEdgeRecord,
} from '@dfmea/plugin-dfmea';
import { artifactEdges, artifacts } from '../db/schema';
import type { ProjectionService } from './projection.service';

export function registerDfmeaProjectionHandlers(projectionService: ProjectionService): void {
  projectionService.registerHandler('dfmea', 'working_tree', async (context) => {
    const [artifactRows, edgeRows] = await Promise.all([
      context.db.select().from(artifacts).where(eq(artifacts.projectId, context.projectId)),
      context.db.select().from(artifactEdges).where(eq(artifactEdges.projectId, context.projectId)),
    ]);

    return {
      payload: buildDfmeaWorkingTree(toDfmeaArtifacts(artifactRows), toDfmeaEdges(edgeRows)),
      summary: 'DFMEA working tree rebuilt.',
    };
  });

  projectionService.registerHandler('dfmea', 'export_payload', async (context) => {
    const [artifactRows, edgeRows] = await Promise.all([
      context.db.select().from(artifacts).where(eq(artifacts.projectId, context.projectId)),
      context.db.select().from(artifactEdges).where(eq(artifactEdges.projectId, context.projectId)),
    ]);

    return {
      payload: buildDfmeaExportPayload(toDfmeaArtifacts(artifactRows), toDfmeaEdges(edgeRows)),
      summary: 'DFMEA export payload rebuilt.',
    };
  });
}

function toDfmeaArtifacts(rows: (typeof artifacts.$inferSelect)[]): DfmeaArtifactRecord[] {
  return rows
    .filter((row) => row.pluginId === 'dfmea')
    .map((row) => ({
      artifactId: row.artifactId,
      artifactType: row.artifactType,
      status: row.status,
      payload: row.payload,
    }));
}

function toDfmeaEdges(rows: (typeof artifactEdges.$inferSelect)[]): DfmeaEdgeRecord[] {
  return rows
    .filter((row) => row.pluginId === 'dfmea')
    .map((row) => ({
      edgeId: row.edgeId,
      sourceArtifactId: row.sourceArtifactId,
      targetArtifactId: row.targetArtifactId,
      relationType: row.relationType,
      status: row.status,
      payload: row.payload,
    }));
}
