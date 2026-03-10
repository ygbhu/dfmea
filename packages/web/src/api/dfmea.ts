export interface WebDfmeaContextResponse {
  projectRoot: string;
  contentRoot: string;
  runtimeRoot: string;
  changesRoot: string;
  subtreeId: string | null;
}

export interface WebDfmeaProjectActionTemplate {
  id: string;
  name: string;
  command: string;
  icon: string;
}

export interface WebDfmeaRuntimeNodeResult {
  id: string;
  kind: string;
  title: string;
  section: string;
  parentId: string | null;
  refIds: string[];
  anchor: string;
  summary: string;
}

export interface WebDfmeaSearchHit {
  subtreeId: string;
  node: WebDfmeaRuntimeNodeResult;
}

export interface WebDfmeaSearchResponse {
  query: string;
  results: WebDfmeaSearchHit[];
}

export interface WebDfmeaProposalOperation {
  type: 'add_section' | 'update_section' | 'append_note';
  file: string;
  section: string;
  description: string;
}

export interface WebDfmeaProposal {
  proposalId: string;
  actionId: 'complete' | 'review-apply';
  projectId: string;
  subtreeId: string;
  summary: string;
  targetFiles: string[];
  operations: WebDfmeaProposalOperation[];
  status: 'proposed' | 'confirmed' | 'applied' | 'failed';
  createdAt: string;
}

export interface WebDfmeaReviewApplyRequest {
  confirm: boolean;
  proposal: WebDfmeaProposal;
  sections: Array<{
    section: string;
    entries: Array<{
      id: string;
      kind: string;
      title: string;
      summary: string;
      refs: string[];
    }>;
  }>;
  notes?: Array<{
    section: string;
    note: string;
  }>;
}

export interface WebDfmeaReviewApplyResponse {
  proposal: WebDfmeaProposal;
  changeRecords: Array<{
    timestamp: string;
    kind: 'review-apply';
    proposalId: string;
    subtreeId: string;
    summary: string;
    status: 'applied' | 'failed';
    targetFiles: string[];
  }>;
}

const buildDfmeaDirectoryHeaders = (directory?: string): HeadersInit | undefined => {
  if (!directory || !directory.trim()) {
    return undefined;
  }

  return {
    'x-opencode-directory': directory.trim(),
  };
};

export const createWebDfmeaAPI = () => ({
  async context(directory?: string): Promise<WebDfmeaContextResponse> {
    const params = new URLSearchParams();
    if (directory && directory.trim()) {
      params.set('directory', directory.trim());
    }

    const response = await fetch(`/api/dfmea/context${params.toString() ? `?${params.toString()}` : ''}`);
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error((error as { error?: string }).error || 'Failed to load DFMEA context');
    }

    return response.json();
  },

  async actionTemplates(): Promise<{ actions: WebDfmeaProjectActionTemplate[] }> {
    const response = await fetch('/api/dfmea/project-actions-template');
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error((error as { error?: string }).error || 'Failed to load DFMEA project actions');
    }

    return response.json();
  },

  async search(payload: { directory?: string; subtreeId?: string | null; query: string }): Promise<WebDfmeaSearchResponse> {
    const response = await fetch('/api/dfmea/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(buildDfmeaDirectoryHeaders(payload.directory) || {}),
      },
      body: JSON.stringify({
        subtreeId: payload.subtreeId ?? null,
        query: payload.query,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error((error as { error?: string }).error || 'Failed to search DFMEA runtime');
    }

    return response.json();
  },

  async reviewApply(directory: string | undefined, payload: WebDfmeaReviewApplyRequest): Promise<WebDfmeaReviewApplyResponse> {
    const response = await fetch('/api/dfmea/review-apply', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(buildDfmeaDirectoryHeaders(directory) || {}),
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error((error as { error?: string }).error || 'Failed to apply DFMEA review');
    }

    return response.json();
  },
});
