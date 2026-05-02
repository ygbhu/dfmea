import { eq } from 'drizzle-orm';
import type { JsonObject } from '@dfmea/shared';
import type { AppDatabase } from '../db/client';
import { createId } from '../db/id';
import { projects, sessions, workspaces } from '../db/schema';

export class ScopeRepository {
  constructor(private readonly db: AppDatabase) {}

  async createWorkspace(input: { name: string; metadata?: JsonObject }) {
    const [workspace] = await this.db
      .insert(workspaces)
      .values({
        workspaceId: createId('ws'),
        name: input.name,
        metadata: input.metadata ?? {},
      })
      .returning();

    return workspace;
  }

  async createProject(input: { workspaceId: string; name: string; metadata?: JsonObject }) {
    const [project] = await this.db
      .insert(projects)
      .values({
        projectId: createId('proj'),
        workspaceId: input.workspaceId,
        name: input.name,
        metadata: input.metadata ?? {},
        workspaceRevision: 0,
      })
      .returning();

    return project;
  }

  async createSession(input: {
    workspaceId: string;
    projectId: string;
    userId?: string;
    activePluginId?: string;
    metadata?: JsonObject;
  }) {
    const [session] = await this.db
      .insert(sessions)
      .values({
        sessionId: createId('sess'),
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        userId: input.userId,
        activePluginId: input.activePluginId,
        metadata: input.metadata ?? {},
      })
      .returning();

    return session;
  }

  async getProject(projectId: string) {
    const [project] = await this.db.select().from(projects).where(eq(projects.projectId, projectId));
    return project;
  }
}
