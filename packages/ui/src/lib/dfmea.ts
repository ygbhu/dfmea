import type { OpenChamberConfig, OpenChamberProjectAction } from '@/lib/openchamberConfig'

export interface DfmeaProjectSettings {
  enabled: boolean
  workspaceRoot?: string
  subtreeId?: string
}

export const DEFAULT_DFMEA_ACTIONS: OpenChamberProjectAction[] = [
  {
    id: 'dfmea-query',
    name: 'DFMEA Query',
    command: 'dfmea query --local',
    icon: 'brain',
  },
  {
    id: 'dfmea-complete',
    name: 'DFMEA Complete',
    command: 'dfmea complete --local',
    icon: 'stack',
  },
  {
    id: 'dfmea-review-apply',
    name: 'DFMEA Review Apply',
    command: 'dfmea review-apply --local',
    icon: 'git-merge',
  },
]

export function readDfmeaSettings(config: OpenChamberConfig | null | undefined): DfmeaProjectSettings {
  const raw = (config as OpenChamberConfig & { dfmea?: DfmeaProjectSettings } | null | undefined)?.dfmea
  if (!raw || raw.enabled !== true) {
    return { enabled: false }
  }

  return {
    enabled: true,
    workspaceRoot: typeof raw.workspaceRoot === 'string' ? raw.workspaceRoot : undefined,
    subtreeId: typeof raw.subtreeId === 'string' ? raw.subtreeId : undefined,
  }
}

export function mergeDfmeaActions(existing: OpenChamberProjectAction[] | undefined, enabled: boolean): OpenChamberProjectAction[] {
  const safeExisting = existing ?? []
  if (!enabled) {
    return safeExisting
  }

  const ids = new Set(safeExisting.map((item) => item.id))
  const merged = [...safeExisting]
  for (const action of DEFAULT_DFMEA_ACTIONS) {
    if (!ids.has(action.id)) {
      merged.push(action)
    }
  }
  return merged
}
