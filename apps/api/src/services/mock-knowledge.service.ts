import { eq } from 'drizzle-orm';
import type { JsonObject } from '@dfmea/shared';
import type { AppDatabase } from '../db/client';
import { createId } from '../db/id';
import { evidenceRefs } from '../db/schema';

export interface MockEvidence {
  evidenceRef: string;
  knowledgeBaseType: 'project' | 'historical_fmea';
  title: string;
  contentPreview: string;
  metadata: JsonObject;
}

export class MockKnowledgeService {
  constructor(private readonly db: AppDatabase) {}

  async retrieve(input: {
    workspaceId: string;
    projectId: string;
    sessionId?: string | undefined;
    query: string;
    knowledgeBaseTypes?: ('project' | 'historical_fmea')[];
  }): Promise<MockEvidence[]> {
    const allowedTypes = input.knowledgeBaseTypes ?? ['project', 'historical_fmea'];
    const fixtures = createCoolingFanEvidence().filter((fixture) =>
      allowedTypes.includes(fixture.knowledgeBaseType),
    );

    for (const fixture of fixtures) {
      await this.db.insert(evidenceRefs).values({
        evidenceRefId: createId('evid'),
        evidenceRef: fixture.evidenceRef,
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        sessionId: input.sessionId,
        knowledgeBaseType: fixture.knowledgeBaseType,
        sourceType: 'mock_fixture',
        providerId: 'mock_knowledge',
        providerRef: fixture.evidenceRef,
        title: fixture.title,
        contentPreview: fixture.contentPreview,
        metadata: {
          ...fixture.metadata,
          query: input.query,
        },
      });
    }

    return fixtures;
  }

  async getEvidence(evidenceRef: string): Promise<MockEvidence | undefined> {
    const [row] = await this.db
      .select()
      .from(evidenceRefs)
      .where(eq(evidenceRefs.evidenceRef, evidenceRef));

    if (row === undefined) {
      return undefined;
    }

    return {
      evidenceRef: row.evidenceRef,
      knowledgeBaseType: row.knowledgeBaseType as 'project' | 'historical_fmea',
      title: row.title,
      contentPreview: row.contentPreview ?? '',
      metadata: row.metadata,
    };
  }
}

function createCoolingFanEvidence(): MockEvidence[] {
  return [
    {
      evidenceRef: 'mock:project:cooling-fan-controller',
      knowledgeBaseType: 'project',
      title: 'Cooling fan controller project brief',
      contentPreview: 'Passenger vehicle controller commands fan speed from thermal demand.',
      metadata: {
        system: 'Engine Thermal Management System',
        subsystem: 'Cooling Fan System',
      },
    },
    {
      evidenceRef: 'mock:historical_fmea:temperature-signal-biased-low',
      knowledgeBaseType: 'historical_fmea',
      title: 'Historical FMEA: temperature signal biased low',
      contentPreview: 'Biased-low temperature input can suppress fan request and delay cooling response.',
      metadata: {
        failure_mode: 'fan not started',
        recommended_action: 'sensor input plausibility monitor',
      },
    },
  ];
}
