import { readFile } from 'node:fs/promises';
import {
  createErrorEnvelope,
  type CapabilityDescriptor,
  type CapabilityInvocationResult,
  type CapabilityManifest,
  type JsonObject,
  type JsonSchema,
  type JsonValue,
  type ValidationIssue,
} from '@dfmea/shared';
import { generateInitialAnalysis } from '@dfmea/plugin-dfmea';
import { createId } from '../db/id';
import type { LoadedSkillDefinition, PluginRegistryService } from '../modules/plugin/plugin-registry.service';
import { ValidationService } from './validation.service';

const platformCapabilityDescriptors: CapabilityDescriptor[] = [
  {
    capabilityId: 'workspace.projection.get',
    kind: 'platform',
    title: 'Get Projection',
    description: 'Read a projection through platform freshness policy.',
    requiredScopes: ['workspace', 'project'],
    inputSchema: objectSchema({
      kind: { type: 'string' },
      scope_type: { type: 'string' },
      scope_id: { type: 'string' },
    }),
    outputSchema: objectSchema({}),
  },
  {
    capabilityId: 'workspace.knowledge.retrieve',
    kind: 'platform',
    title: 'Retrieve Knowledge',
    requiredScopes: ['workspace', 'project'],
    inputSchema: objectSchema({
      query: { type: 'string' },
    }),
    outputSchema: objectSchema({}),
  },
  {
    capabilityId: 'workspace.knowledge.get_evidence',
    kind: 'platform',
    title: 'Get Evidence',
    requiredScopes: ['workspace', 'project'],
    inputSchema: objectSchema({
      evidence_ref: { type: 'string' },
    }),
    outputSchema: objectSchema({}),
  },
  {
    capabilityId: 'workspace.ai_draft.propose',
    kind: 'platform',
    title: 'Propose AI Draft',
    requiredScopes: ['workspace', 'project'],
    inputSchema: objectSchema({
      goal: { type: 'string' },
      patches: { type: 'array' },
    }),
    outputSchema: objectSchema({}),
    sideEffect: 'creates_ai_draft_proposal',
  },
  {
    capabilityId: 'workspace.ai_draft.validate',
    kind: 'platform',
    title: 'Validate AI Draft',
    requiredScopes: ['workspace', 'project'],
    inputSchema: objectSchema({
      draft_batch_id: { type: 'string' },
    }),
    outputSchema: objectSchema({}),
  },
  {
    capabilityId: 'workspace.question.ask_user',
    kind: 'platform',
    title: 'Ask User',
    requiredScopes: ['workspace', 'project'],
    inputSchema: objectSchema({
      question: { type: 'string' },
    }),
    outputSchema: objectSchema({}),
    sideEffect: 'asks_user_question',
  },
];

export interface BuildCapabilityManifestInput {
  workspaceId: string;
  projectId?: string;
  pluginIds: string[];
}

export interface CapabilityInvocationInput {
  manifest: CapabilityManifest;
  workspaceId: string;
  projectId?: string;
  runId?: string;
  capabilityId: string;
  arguments: JsonValue;
  invocationId?: string;
}

export class WorkspaceCapabilityService {
  private readonly validationService: ValidationService;

  constructor(
    private readonly pluginRegistry: PluginRegistryService,
    validationService = new ValidationService(),
  ) {
    this.validationService = validationService;
  }

  async buildCapabilityManifest(input: BuildCapabilityManifestInput): Promise<CapabilityManifest> {
    const pluginDescriptors = await Promise.all(
      input.pluginIds.flatMap((pluginId) =>
        this.pluginRegistry.listSkills(pluginId).map((skill) => this.createPluginSkillDescriptor(skill)),
      ),
    );
    const descriptors = [...platformCapabilityDescriptors, ...pluginDescriptors];

    return {
      workspaceId: input.workspaceId,
      ...(input.projectId !== undefined ? { projectId: input.projectId } : {}),
      capabilityIds: descriptors.map((descriptor) => descriptor.capabilityId),
      descriptors,
      createdAt: new Date().toISOString(),
    };
  }

  async invoke(input: CapabilityInvocationInput): Promise<CapabilityInvocationResult> {
    const invocationId = input.invocationId ?? createId('inv');
    const descriptor = input.manifest.descriptors.find(
      (candidate) => candidate.capabilityId === input.capabilityId,
    );

    if (descriptor === undefined) {
      return createCapabilityErrorResult(
        invocationId,
        'denied',
        'CAPABILITY_NOT_IN_MANIFEST',
        'Capability is not in the current manifest.',
        { capability_id: input.capabilityId },
      );
    }

    const scopeError = this.validateScope(input.manifest, input.workspaceId, input.projectId);
    if (scopeError !== undefined) {
      return createCapabilityErrorResult(
        invocationId,
        'denied',
        scopeError.code,
        scopeError.message,
        scopeError.details,
      );
    }

    if (descriptor.inputSchema !== undefined) {
      const validation = this.validationService.validateJsonSchema(descriptor.inputSchema, input.arguments);

      if (validation.status === 'invalid') {
        return createCapabilityErrorResult(
          invocationId,
          'invalid_arguments',
          'CAPABILITY_ARGUMENT_INVALID',
          'Capability arguments do not match the input schema.',
          { capability_id: input.capabilityId, issues: validationIssuesToJson(validation.issues) },
        );
      }
    }

    const result = await this.dispatchCapability(input.capabilityId, input.arguments);

    if (descriptor.outputSchema !== undefined) {
      const validation = this.validationService.validateJsonSchema(descriptor.outputSchema, result);

      if (validation.status === 'invalid') {
        return createCapabilityErrorResult(
          invocationId,
          'failed',
          'CAPABILITY_RESULT_INVALID',
          'Capability result does not match the output schema.',
          { capability_id: input.capabilityId, issues: validationIssuesToJson(validation.issues) },
        );
      }
    }

    return {
      invocationId,
      status: 'completed',
      result,
      error: null,
      completedAt: new Date().toISOString(),
    };
  }

  private async createPluginSkillDescriptor(skill: LoadedSkillDefinition): Promise<CapabilityDescriptor> {
    const descriptor: CapabilityDescriptor = {
      capabilityId: skill.capabilityId,
      kind: 'plugin_skill',
      owner: skill.pluginId,
      title: skill.name,
      inputSchemaId: skill.input_schema,
      outputSchemaId: skill.output_schema,
      inputSchema: await readJsonSchema(skill.inputSchema.schemaPath),
      outputSchema: await readJsonSchema(skill.outputSchema.schemaPath),
      requiredScopes: ['workspace', 'project'],
    };

    if (skill.description !== undefined) {
      descriptor.description = skill.description;
    }

    if (skill.side_effect !== undefined) {
      descriptor.sideEffect = skill.side_effect;
    }

    return descriptor;
  }

  private validateScope(
    manifest: CapabilityManifest,
    workspaceId: string,
    projectId: string | undefined,
  ): { code: string; message: string; details: JsonObject } | undefined {
    if (workspaceId !== manifest.workspaceId) {
      return {
        code: 'CAPABILITY_SCOPE_DENIED',
        message: 'Invocation workspace does not match the manifest workspace.',
        details: { manifest_workspace_id: manifest.workspaceId, workspace_id: workspaceId },
      };
    }

    if (manifest.projectId !== undefined && projectId !== manifest.projectId) {
      return {
        code: 'CAPABILITY_SCOPE_DENIED',
        message: 'Invocation project does not match the manifest project.',
        details: { manifest_project_id: manifest.projectId, project_id: projectId ?? null },
      };
    }

    return undefined;
  }

  private async dispatchCapability(
    capabilityId: string,
    args: JsonValue,
  ): Promise<JsonValue> {
    if (capabilityId.startsWith('workspace.')) {
      return {
        result_type: 'platform_capability_placeholder',
        capability_id: capabilityId,
        accepted: true,
      };
    }

    const skill = this.pluginRegistry.getSkillByCapabilityId(capabilityId);
    if (skill === undefined) {
      throw new Error(`Plugin skill capability is not registered: ${capabilityId}`);
    }

    if (capabilityId === 'dfmea.generate_initial_analysis') {
      return toJsonValue(generateInitialAnalysis({
        project_id: readProjectId(args),
        ...readObject(args),
      }));
    }

    return {
      result_type: 'plugin_skill_placeholder',
      capability_id: capabilityId,
      plugin_id: skill.pluginId,
      skill_id: skill.skill_id,
    };
  }
}

function validationIssuesToJson(issues: ValidationIssue[]): JsonValue {
  return issues.map((issue): JsonObject => ({
    instancePath: issue.instancePath,
    schemaPath: issue.schemaPath,
    message: issue.message,
    keyword: issue.keyword,
    params: issue.params,
  }));
}

async function readJsonSchema(path: string): Promise<JsonSchema> {
  return JSON.parse(await readFile(path, 'utf8')) as JsonSchema;
}

function createCapabilityErrorResult(
  invocationId: string,
  status: 'denied' | 'invalid_arguments' | 'failed',
  code: string,
  message: string,
  details: JsonObject,
): CapabilityInvocationResult {
  return {
    invocationId,
    status,
    result: null,
    error: createErrorEnvelope(code, message, { details }),
    completedAt: new Date().toISOString(),
  };
}

function objectSchema(properties: Record<string, JsonObject>): JsonSchema {
  return {
    type: 'object',
    properties,
    required: Object.keys(properties),
    additionalProperties: true,
  };
}

function readProjectId(value: JsonValue): string {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    const projectId = value.project_id;

    if (typeof projectId === 'string') {
      return projectId;
    }
  }

  return 'unknown';
}

function readObject(value: JsonValue): JsonObject {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value;
  }

  return {};
}

function toJsonValue(value: unknown): JsonValue {
  return JSON.parse(JSON.stringify(value)) as JsonValue;
}
