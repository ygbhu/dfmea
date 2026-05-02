import { useEffect, useMemo, useRef, useState } from 'react';
import {
  applyDraft,
  connectPlatformEvents,
  createProject,
  createSession,
  createWorkspace,
  executeApiPush,
  getDraft,
  getDraftPreview,
  getWorkingProjection,
  rejectDraft,
  startRun,
  validateApiPush,
  type ApiPushResult,
  type DraftPreview,
  type DraftResponse,
  type PlatformEvent,
  type ProjectRecord,
  type ProjectionReadResult,
  type RunStartResult,
  type SessionRecord,
  type WorkspaceRecord,
} from './platformApi';
import {
  buildDraftTree,
  buildWorkingTree,
  eventLabel,
  patchLabel,
  readEventType,
  type TreeNodeStatus,
  type UiTreeNode,
} from './workspaceModel';

type TreeMode = 'working' | 'draft';
type WorkspacePluginId = 'structure' | 'draft-review' | 'runtime-events' | 'api-push';

const defaultGoal = 'Generate passenger vehicle cooling fan controller DFMEA draft';
const runEventTypes = [
  'runtime.started',
  'runtime.message',
  'runtime.capability_invocation.started',
  'runtime.capability_invocation.completed',
  'runtime.result.proposed',
  'runtime.failed',
  'runtime.cancelled',
  'runtime.completed',
  'ai_draft.edited',
  'ai_draft.apply_started',
  'ai_draft.applied',
  'ai_draft.rejected',
];
const draftPreviewEventTypes = [
  'draft.preview.started',
  'draft.preview.node_upserted',
  'draft.preview.node_updated',
  'draft.preview.edge_upserted',
  'draft.preview.edge_updated',
  'draft.preview.node_removed',
  'draft.preview.edge_removed',
  'draft.preview.validation_updated',
  'draft.preview.evidence_linked',
  'draft.preview.completed',
];

export function App() {
  const bootstrappedRef = useRef(false);
  const [workspace, setWorkspace] = useState<WorkspaceRecord | null>(null);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [session, setSession] = useState<SessionRecord | null>(null);
  const [projection, setProjection] = useState<ProjectionReadResult | null>(null);
  const [draft, setDraft] = useState<DraftResponse['draft'] | null>(null);
  const [draftPreview, setDraftPreview] = useState<DraftPreview | null>(null);
  const [activeRun, setActiveRun] = useState<RunStartResult | null>(null);
  const [apiPushResult, setApiPushResult] = useState<ApiPushResult | null>(null);
  const [runtimeEvents, setRuntimeEvents] = useState<PlatformEvent[]>([]);
  const [previewEvents, setPreviewEvents] = useState<PlatformEvent[]>([]);
  const [goal, setGoal] = useState(defaultGoal);
  const [activePluginId, setActivePluginId] = useState<WorkspacePluginId>('structure');
  const [treeMode, setTreeMode] = useState<TreeMode>('working');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('Bootstrapping workspace');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (bootstrappedRef.current) {
      return;
    }

    bootstrappedRef.current = true;
    void bootstrapWorkspace();
  }, []);

  useEffect(() => {
    if (activeRun === null) {
      return undefined;
    }

    return connectPlatformEvents(
      activeRun.eventsUrl,
      runEventTypes,
      (event) => {
        setRuntimeEvents((current) => appendEvent(current, event));

        if (readEventType(event) === 'runtime.completed') {
          setStatus('Draft ready for review');
        }
      },
      () => undefined,
    );
  }, [activeRun]);

  useEffect(() => {
    if (draftPreview === null) {
      return undefined;
    }

    setTreeMode('draft');

    return connectPlatformEvents(
      `/api/ai-drafts/${draftPreview.draftBatchId}/preview/events/stream`,
      draftPreviewEventTypes,
      (event) => {
        setPreviewEvents((current) => appendEvent(current, event));
      },
      () => undefined,
    );
  }, [draftPreview]);

  const workingNodes = useMemo(() => buildWorkingTree(projection), [projection]);
  const draftNodes = useMemo(() => buildDraftTree(draftPreview), [draftPreview]);
  const visibleNodes = treeMode === 'draft' ? draftNodes : workingNodes;
  const canStartRun = session !== null && !busy;
  const canApplyDraft = draft !== null && draft.batch.status === 'pending' && !busy;

  async function bootstrapWorkspace(): Promise<void> {
    try {
      setBusy(true);
      setStatus('Creating workspace scope');
      const createdWorkspace = await createWorkspace('Cooling Fan DFMEA Workspace');
      const createdProject = await createProject(createdWorkspace.workspaceId, 'Cooling Fan Controller DFMEA');
      const createdSession = await createSession(createdProject.projectId);

      setWorkspace(createdWorkspace);
      setProject(createdProject);
      setSession(createdSession);
      await refreshWorkingProjection(createdProject.projectId);
      setStatus('Workspace ready');
    } catch (caught) {
      setError(readErrorMessage(caught));
      setStatus('Workspace setup failed');
    } finally {
      setBusy(false);
    }
  }

  async function refreshWorkingProjection(projectId: string): Promise<void> {
    const nextProjection = await getWorkingProjection(projectId);
    setProjection(nextProjection);
  }

  async function handleStartRun(): Promise<void> {
    if (session === null || project === null) {
      return;
    }

    try {
      setBusy(true);
      setError(null);
      setRuntimeEvents([]);
      setPreviewEvents([]);
      setDraft(null);
      setDraftPreview(null);
      setTreeMode('working');
      setStatus('Starting mock runtime');

      const run = await startRun(session.sessionId, goal);
      setActiveRun(run);
      const preview = await getDraftPreview(run.draftBatchId);
      const nextDraft = await getDraft(run.draftBatchId);

      setDraft(nextDraft);
      setDraftPreview(preview.preview);
      setStatus('Draft ready for review');
      await refreshWorkingProjection(project.projectId);
    } catch (caught) {
      setError(readErrorMessage(caught));
      setStatus('Run failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleApplyDraft(): Promise<void> {
    if (draft === null || project === null) {
      return;
    }

    try {
      setBusy(true);
      setError(null);
      setStatus('Applying draft');
      const result = await applyDraft(draft.batch.draftBatchId);

      setDraft(null);
      setDraftPreview(null);
      setPreviewEvents([]);
      setTreeMode('working');
      setActivePluginId('structure');

      if (result.workingTreeProjection !== null) {
        setProjection(result.workingTreeProjection);
      } else {
        await refreshWorkingProjection(project.projectId);
      }

      setStatus(`Applied revision ${result.applyResult.toRevision}`);
    } catch (caught) {
      setError(readErrorMessage(caught));
      setStatus('Apply failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleRejectDraft(): Promise<void> {
    if (draft === null) {
      return;
    }

    try {
      setBusy(true);
      setError(null);
      setStatus('Rejecting draft');
      await rejectDraft(draft.batch.draftBatchId);
      setDraft(null);
      setDraftPreview(null);
      setPreviewEvents([]);
      setTreeMode('working');
      setActivePluginId('structure');
      setStatus('Draft rejected');
    } catch (caught) {
      setError(readErrorMessage(caught));
      setStatus('Reject failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleValidateApiPush(): Promise<void> {
    if (project === null) {
      return;
    }

    try {
      setBusy(true);
      setError(null);
      setStatus('Validating API Push');
      const result = await validateApiPush(project.projectId);
      setApiPushResult(result);
      setStatus(`API Push validation ${result.validation.status}`);
    } catch (caught) {
      setError(readErrorMessage(caught));
      setStatus('API Push validation failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleExecuteApiPush(): Promise<void> {
    if (project === null) {
      return;
    }

    try {
      setBusy(true);
      setError(null);
      setStatus('Executing API Push');
      const result = await executeApiPush(project.projectId);
      setApiPushResult(result);
      setStatus(`API Push ${result.job.status}`);
    } catch (caught) {
      setError(readErrorMessage(caught));
      setStatus('API Push failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <TopBar
        workspace={workspace}
        project={project}
        projection={projection}
        status={status}
        busy={busy}
      />

      <section className="workspace-grid">
        <PluginWorkspace
          activePluginId={activePluginId}
          onActivePluginChange={setActivePluginId}
          treeMode={treeMode}
          onTreeModeChange={setTreeMode}
          workingCount={workingNodes.length}
          draftCount={draftNodes.length}
          nodes={visibleNodes}
          projection={projection}
          hasDraft={draftPreview !== null}
          draft={draft}
          preview={draftPreview}
          previewEvents={previewEvents}
          canApplyDraft={canApplyDraft}
          busy={busy}
          onApply={() => void handleApplyDraft()}
          onReject={() => void handleRejectDraft()}
          runtimeEvents={runtimeEvents}
          apiPushResult={apiPushResult}
          canUseApiPush={project !== null && !busy}
          onValidateApiPush={() => void handleValidateApiPush()}
          onExecuteApiPush={() => void handleExecuteApiPush()}
        />

        <AgentPanel
          goal={goal}
          onGoalChange={setGoal}
          onStartRun={() => void handleStartRun()}
          canStartRun={canStartRun}
          busy={busy}
          activeRun={activeRun}
          runtimeEvents={runtimeEvents}
          error={error}
        />
      </section>
    </main>
  );
}

function TopBar(props: {
  workspace: WorkspaceRecord | null;
  project: ProjectRecord | null;
  projection: ProjectionReadResult | null;
  status: string;
  busy: boolean;
}) {
  return (
    <header className="top-bar">
      <div>
        <p className="eyebrow">Quality Workspace</p>
        <h1>{props.project?.name ?? 'Cooling Fan Controller DFMEA'}</h1>
      </div>
      <div className="top-meta" aria-label="Workspace status">
        <span>{props.workspace?.name ?? 'Workspace'}</span>
        <span>rev {props.projection?.currentWorkspaceRevision ?? 0}</span>
        <span data-state={props.busy ? 'running' : 'idle'}>{props.status}</span>
      </div>
    </header>
  );
}

function PluginWorkspace(props: {
  activePluginId: WorkspacePluginId;
  onActivePluginChange: (pluginId: WorkspacePluginId) => void;
  treeMode: TreeMode;
  onTreeModeChange: (mode: TreeMode) => void;
  workingCount: number;
  draftCount: number;
  nodes: UiTreeNode[];
  projection: ProjectionReadResult | null;
  hasDraft: boolean;
  draft: DraftResponse['draft'] | null;
  preview: DraftPreview | null;
  previewEvents: PlatformEvent[];
  canApplyDraft: boolean;
  busy: boolean;
  onApply: () => void;
  onReject: () => void;
  runtimeEvents: PlatformEvent[];
  apiPushResult: ApiPushResult | null;
  canUseApiPush: boolean;
  onValidateApiPush: () => void;
  onExecuteApiPush: () => void;
}) {
  return (
    <section className="plugin-workbench" aria-label="Workspace plugins">
      <aside className="plugin-rail" aria-label="Plugin switcher">
        <PluginButton
          active={props.activePluginId === 'structure'}
          label="Structure"
          meta={`${props.workingCount}/${props.draftCount}`}
          onClick={() => props.onActivePluginChange('structure')}
        />
        <PluginButton
          active={props.activePluginId === 'draft-review'}
          label="Draft Review"
          meta={props.draft?.batch.status ?? 'idle'}
          onClick={() => props.onActivePluginChange('draft-review')}
        />
        <PluginButton
          active={props.activePluginId === 'runtime-events'}
          label="Run Events"
          meta={String(props.runtimeEvents.length)}
          onClick={() => props.onActivePluginChange('runtime-events')}
        />
        <PluginButton
          active={props.activePluginId === 'api-push'}
          label="API Push"
          meta={props.apiPushResult?.job.status ?? 'idle'}
          onClick={() => props.onActivePluginChange('api-push')}
        />
      </aside>

      <div className="plugin-content">
        {props.activePluginId === 'structure' ? (
          <StructurePlugin
            treeMode={props.treeMode}
            onTreeModeChange={props.onTreeModeChange}
            workingCount={props.workingCount}
            draftCount={props.draftCount}
            nodes={props.nodes}
            projection={props.projection}
            hasDraft={props.hasDraft}
          />
        ) : null}

        {props.activePluginId === 'draft-review' ? (
          <DraftReviewPlugin
            draft={props.draft}
            preview={props.preview}
            previewEvents={props.previewEvents}
            canApplyDraft={props.canApplyDraft}
            busy={props.busy}
            onApply={props.onApply}
            onReject={props.onReject}
          />
        ) : null}

        {props.activePluginId === 'runtime-events' ? (
          <RuntimeEventsPlugin runtimeEvents={props.runtimeEvents} />
        ) : null}

        {props.activePluginId === 'api-push' ? (
          <ApiPushPlugin
            result={props.apiPushResult}
            canUseApiPush={props.canUseApiPush}
            busy={props.busy}
            onValidate={props.onValidateApiPush}
            onExecute={props.onExecuteApiPush}
          />
        ) : null}
      </div>
    </section>
  );
}

function PluginButton(props: {
  active: boolean;
  label: string;
  meta: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={props.active ? 'plugin-button selected' : 'plugin-button'}
      onClick={props.onClick}
    >
      <span>{props.label}</span>
      <small>{props.meta}</small>
    </button>
  );
}

function StructurePlugin(props: {
  treeMode: TreeMode;
  onTreeModeChange: (mode: TreeMode) => void;
  workingCount: number;
  draftCount: number;
  nodes: UiTreeNode[];
  projection: ProjectionReadResult | null;
  hasDraft: boolean;
}) {
  return (
    <section className="plugin-pane" aria-label="Structure tree plugin">
      <header className="pane-header">
        <div>
          <p className="eyebrow">Structure Plugin</p>
          <h2>{props.treeMode === 'draft' ? 'Draft Preview Tree' : 'Working Tree'}</h2>
        </div>
        <span className="revision" data-freshness={props.projection?.freshness ?? 'fresh'}>
          {props.projection?.freshness ?? 'fresh'}
        </span>
      </header>

      <div className="segmented-control" role="group" aria-label="Tree mode">
        <button
          type="button"
          className={props.treeMode === 'working' ? 'selected' : ''}
          onClick={() => props.onTreeModeChange('working')}
        >
          Working {props.workingCount}
        </button>
        <button
          type="button"
          className={props.treeMode === 'draft' ? 'selected' : ''}
          onClick={() => props.onTreeModeChange('draft')}
          disabled={!props.hasDraft}
        >
          Draft {props.draftCount}
        </button>
      </div>

      <TreeView nodes={props.nodes} emptyText={props.treeMode === 'draft' ? 'No draft preview' : 'No confirmed structure'} />
    </section>
  );
}

function TreeView(props: { nodes: UiTreeNode[]; emptyText: string }) {
  if (!props.nodes.length) {
    return <div className="empty-state">{props.emptyText}</div>;
  }

  return (
    <nav className="tree-list" aria-label="Workspace structure">
      {props.nodes.map((node, index) => (
        <button
          type="button"
          className="tree-row"
          data-status={node.status}
          key={`${node.source}:${node.id}:${index}`}
          style={{ paddingLeft: `${node.depth * 18 + 12}px` }}
        >
          <span className="node-dot" aria-hidden="true" />
          <span className="tree-text">
            <span>{node.label}</span>
            <small>{node.type}</small>
          </span>
          <StatusBadge status={node.status} />
          {node.badgeText.slice(0, 2).map((badge) => (
            <span className="metric-badge" key={badge}>
              {badge}
            </span>
          ))}
        </button>
      ))}
    </nav>
  );
}

function AgentPanel(props: {
  goal: string;
  onGoalChange: (goal: string) => void;
  onStartRun: () => void;
  canStartRun: boolean;
  busy: boolean;
  activeRun: RunStartResult | null;
  runtimeEvents: PlatformEvent[];
  error: string | null;
}) {
  return (
    <section className="agent-pane" aria-label="Agent session">
      <header className="pane-header">
        <div>
          <p className="eyebrow">Mock Runtime</p>
          <h2>{props.activeRun === null ? 'Initial analysis run' : props.activeRun.runId}</h2>
        </div>
        <button
          type="button"
          className="primary-button"
          onClick={props.onStartRun}
          disabled={!props.canStartRun}
        >
          {props.busy ? 'Running' : 'Start Run'}
        </button>
      </header>

      <label className="goal-row">
        <span>Run goal</span>
        <textarea value={props.goal} onChange={(event) => props.onGoalChange(event.target.value)} />
      </label>

      {props.error !== null ? <div className="error-banner">{props.error}</div> : null}

      <ol className="event-list" aria-label="Runtime events">
        {props.runtimeEvents.length ? (
          props.runtimeEvents.map((event, index) => (
            <li key={readEventKey(event, index)}>
              <span className="status-dot" aria-hidden="true" />
              <span>{eventLabel(event)}</span>
            </li>
          ))
        ) : (
          <li className="muted-event">
            <span className="status-dot" aria-hidden="true" />
            <span>Runtime idle</span>
          </li>
        )}
      </ol>
    </section>
  );
}

function DraftReviewPlugin(props: {
  draft: DraftResponse['draft'] | null;
  preview: DraftPreview | null;
  previewEvents: PlatformEvent[];
  canApplyDraft: boolean;
  busy: boolean;
  onApply: () => void;
  onReject: () => void;
}) {
  return (
    <section className="plugin-pane" aria-label="Draft review plugin">
      <header className="pane-header">
        <div>
          <p className="eyebrow">Draft Review Plugin</p>
          <h2>{props.draft?.batch.title ?? 'No active draft'}</h2>
        </div>
        <span className="revision">{props.draft?.batch.status ?? 'idle'}</span>
      </header>

      <div className="draft-summary">
        <Metric label="Nodes" value={String(props.preview?.nodes.length ?? 0)} />
        <Metric label="Edges" value={String(props.preview?.edges.length ?? 0)} />
        <Metric label="Evidence" value={String(props.preview?.evidenceRefs.length ?? 0)} />
      </div>

      <div className="draft-list" aria-label="Draft patches">
        {props.draft === null ? (
          <div className="empty-state">No draft batch</div>
        ) : (
          props.draft.patches.slice(0, 12).map((patch) => (
            <div className="draft-row" key={patch.draftPatchId}>
              <span>
                <strong>{patchLabel(patch)}</strong>
                <small>{patch.patchType}</small>
              </span>
              <small>{patch.status}</small>
            </div>
          ))
        )}
      </div>

      <div className="preview-event-strip" aria-label="Draft preview events">
        {props.previewEvents.slice(-4).map((event, index) => (
          <span key={readEventKey(event, index)}>{readEventType(event)}</span>
        ))}
      </div>

      <div className="action-row">
        <button
          type="button"
          className="secondary-button"
          onClick={props.onReject}
          disabled={props.draft === null || props.busy}
        >
          Reject
        </button>
        <button
          type="button"
          className="primary-button"
          onClick={props.onApply}
          disabled={!props.canApplyDraft}
        >
          Apply
        </button>
      </div>
    </section>
  );
}

function RuntimeEventsPlugin(props: { runtimeEvents: PlatformEvent[] }) {
  return (
    <section className="plugin-pane" aria-label="Runtime events plugin">
      <header className="pane-header">
        <div>
          <p className="eyebrow">Runtime Plugin</p>
          <h2>Run Event Stream</h2>
        </div>
        <span className="revision">{props.runtimeEvents.length}</span>
      </header>

      <ol className="event-list plugin-event-list" aria-label="Plugin runtime events">
        {props.runtimeEvents.length ? (
          props.runtimeEvents.map((event, index) => (
            <li key={readEventKey(event, index)}>
              <span className="status-dot" aria-hidden="true" />
              <span>{eventLabel(event)}</span>
            </li>
          ))
        ) : (
          <li className="muted-event">
            <span className="status-dot" aria-hidden="true" />
            <span>No runtime events</span>
          </li>
        )}
      </ol>
    </section>
  );
}

function ApiPushPlugin(props: {
  result: ApiPushResult | null;
  canUseApiPush: boolean;
  busy: boolean;
  onValidate: () => void;
  onExecute: () => void;
}) {
  const job = props.result?.job ?? null;
  const record = props.result?.record ?? null;
  const summary = record?.responseSummary ?? {};

  return (
    <section className="plugin-pane" aria-label="API Push plugin">
      <header className="pane-header">
        <div>
          <p className="eyebrow">API Push Plugin</p>
          <h2>{job?.adapterId ?? 'Mock Mature FMEA'}</h2>
        </div>
        <span className="revision">{job?.status ?? 'idle'}</span>
      </header>

      <div className="draft-summary">
        <Metric label="Revision" value={String(job?.sourceWorkspaceRevision ?? 0)} />
        <Metric label="Mode" value={job?.mode ?? 'none'} />
        <Metric label="External" value={record?.externalStatus ?? 'none'} />
      </div>

      <div className="draft-list api-push-details" aria-label="API Push result">
        {job === null ? (
          <div className="empty-state">No push job</div>
        ) : (
          <>
            <DetailRow label="Job" value={job.apiPushJobId} />
            <DetailRow label="Projection" value={job.sourceProjectionId} />
            <DetailRow label="Checksum" value={record?.payloadChecksum ?? 'pending'} />
            <DetailRow label="Artifacts" value={String(summary.artifact_count ?? 0)} />
            <DetailRow label="External ID" value={record?.externalRecordId ?? 'pending'} />
          </>
        )}
      </div>

      <div className="preview-event-strip" aria-label="API Push events">
        {props.result?.events.slice(-4).map((eventType) => (
          <span key={eventType}>{eventType}</span>
        ))}
      </div>

      <div className="action-row">
        <button
          type="button"
          className="secondary-button"
          onClick={props.onValidate}
          disabled={!props.canUseApiPush || props.busy}
        >
          Validate
        </button>
        <button
          type="button"
          className="primary-button"
          onClick={props.onExecute}
          disabled={!props.canUseApiPush || props.busy}
        >
          Execute
        </button>
      </div>
    </section>
  );
}

function DetailRow(props: { label: string; value: string }) {
  return (
    <div className="draft-row detail-row">
      <span>
        <strong>{props.label}</strong>
        <small>{props.value}</small>
      </span>
    </div>
  );
}

function Metric(props: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{props.value}</span>
      <small>{props.label}</small>
    </div>
  );
}

function StatusBadge(props: { status: TreeNodeStatus }) {
  return <span className="status-badge" data-status={props.status}>{statusText(props.status)}</span>;
}

function statusText(status: TreeNodeStatus): string {
  const text: Record<TreeNodeStatus, string> = {
    confirmed: 'confirmed',
    candidate_new: 'new',
    candidate_updated: 'updated',
    candidate_deleted: 'deleted',
    applied: 'applied',
    rejected: 'rejected',
    stale: 'stale',
  };

  return text[status];
}

function appendEvent(events: PlatformEvent[], event: PlatformEvent): PlatformEvent[] {
  const eventId = readEventId(event);

  if (eventId !== undefined && events.some((candidate) => readEventId(candidate) === eventId)) {
    return events;
  }

  return [...events, event].slice(-40);
}

function readEventId(event: PlatformEvent): string | undefined {
  if (typeof event.event_id === 'string') {
    return event.event_id;
  }

  if (typeof event.eventId === 'string') {
    return event.eventId;
  }

  return undefined;
}

function readEventKey(event: PlatformEvent, index: number): string {
  return readEventId(event) ?? `${readEventType(event)}:${index}`;
}

function readErrorMessage(caught: unknown): string {
  return caught instanceof Error ? caught.message : 'Unexpected workspace error.';
}
