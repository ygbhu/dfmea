export type {
  CapabilityDescriptor,
  CapabilityInvocationEnvelope,
  CapabilityInvocationResult,
  CapabilityManifest,
  CapabilityInvocationStatus,
} from '@dfmea/shared';

export { capabilityInvocationStatusValues, isCapabilityInvocationStatus } from '@dfmea/shared';

export function isWorkspaceCapability(capabilityId: string): boolean {
  return capabilityId.startsWith('workspace.');
}

export function isPluginSkillCapability(capabilityId: string): boolean {
  return !isWorkspaceCapability(capabilityId) && capabilityId.includes('.');
}
