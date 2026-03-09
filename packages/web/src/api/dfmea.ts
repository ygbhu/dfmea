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
});
