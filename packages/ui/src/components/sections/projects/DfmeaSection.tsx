import React from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { ButtonSmall } from '@/components/ui/button-small';
import { toast } from '@/components/ui';
import { useRuntimeAPIs } from '@/hooks/useRuntimeAPIs';
import {
  getDfmeaProjectSettings,
  getProjectActionsState,
  saveDfmeaProjectSettings,
  saveProjectActionsState,
  type ProjectRef,
} from '@/lib/openchamberConfig';
import { mergeDfmeaActions } from '@/lib/dfmea';

interface DfmeaSectionProps {
  projectRef: ProjectRef;
}

export const DfmeaSection: React.FC<DfmeaSectionProps> = ({ projectRef }) => {
  const { dfmea } = useRuntimeAPIs();
  const [enabled, setEnabled] = React.useState(false);
  const [workspaceRoot, setWorkspaceRoot] = React.useState('');
  const [subtreeId, setSubtreeId] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    setIsLoading(true);

    void getDfmeaProjectSettings(projectRef)
      .then((settings) => {
        if (cancelled) {
          return;
        }
        setEnabled(settings.enabled);
        setWorkspaceRoot(settings.workspaceRoot);
        setSubtreeId(settings.subtreeId);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [projectRef]);

  const handleSave = React.useCallback(async () => {
    setIsSaving(true);
    try {
      const ok = await saveDfmeaProjectSettings(projectRef, {
        enabled,
        workspaceRoot,
        subtreeId,
      });

      if (!ok) {
        toast.error('Failed to save DFMEA settings');
        return;
      }

      if (enabled && dfmea) {
        const [currentActions, templates] = await Promise.all([
          getProjectActionsState(projectRef),
          dfmea.actionTemplates(),
        ]);

        await saveProjectActionsState(projectRef, {
          actions: mergeDfmeaActions(currentActions.actions, true, templates.actions),
          primaryActionId: currentActions.primaryActionId,
        });
      }

      toast.success('DFMEA settings saved');
    } catch {
      toast.error('Failed to save DFMEA settings');
    } finally {
      setIsSaving(false);
    }
  }, [dfmea, enabled, projectRef, subtreeId, workspaceRoot]);

  return (
    <div className="mb-8">
      <section className="px-2 pb-2 pt-0 space-y-3">
        <div>
          <h3 className="typography-ui-header font-medium text-foreground">DFMEA</h3>
          <p className="typography-meta text-muted-foreground">Project-scoped DFMEA settings and action presets.</p>
        </div>

        {isLoading ? (
          <p className="typography-meta text-muted-foreground">Loading...</p>
        ) : (
          <>
            <div className="flex items-center gap-2 py-1">
              <Checkbox
                checked={enabled}
                onChange={(checked) => setEnabled(Boolean(checked))}
                ariaLabel="Enable DFMEA for this project"
              />
              <span className="typography-ui-label text-foreground">Enable DFMEA</span>
            </div>

            <div className="py-1">
              <p className="typography-meta mb-0.5 text-muted-foreground">Workspace Root</p>
              <Input
                value={workspaceRoot}
                onChange={(event) => setWorkspaceRoot(event.target.value)}
                placeholder="/path/to/dfmea/workspace"
                className="h-7 max-w-[30rem]"
              />
            </div>

            <div className="py-1">
              <p className="typography-meta mb-0.5 text-muted-foreground">Default Subtree ID</p>
              <Input
                value={subtreeId}
                onChange={(event) => setSubtreeId(event.target.value)}
                placeholder="brake-signal"
                className="h-7 max-w-[16rem]"
              />
            </div>

            <ButtonSmall
              type="button"
              size="xs"
              className="!font-normal"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? 'Saving...' : 'Save DFMEA Settings'}
            </ButtonSmall>
          </>
        )}
      </section>
    </div>
  );
};
