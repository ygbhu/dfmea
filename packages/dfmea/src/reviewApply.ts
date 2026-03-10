import type { DfmeaProposal } from './proposal';
import { materializeDfmeaRuntime, recordAppliedProposal, updateSubtreeSections } from './storage';

export interface DfmeaReviewApplyRequest {
  confirm: boolean;
  proposal: DfmeaProposal;
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

export async function applyDfmeaReview(input: {
  projectRoot: string;
  request: DfmeaReviewApplyRequest;
}): Promise<{
  proposal: DfmeaProposal;
}> {
  if (!input.request.confirm) {
    throw new Error('DFMEA review-apply requires explicit confirmation');
  }

  const proposal: DfmeaProposal = {
    ...input.request.proposal,
    status: 'confirmed',
  };

  try {
    await updateSubtreeSections({
      projectRoot: input.projectRoot,
      subtreeId: proposal.subtreeId,
      sections: input.request.sections,
      notes: input.request.notes,
    });

    await materializeDfmeaRuntime(input.projectRoot);

    const appliedProposal: DfmeaProposal = {
      ...proposal,
      status: 'applied',
    };

    await recordAppliedProposal(input.projectRoot, appliedProposal);

    return {
      proposal: appliedProposal,
    };
  } catch (error) {
    const failedProposal: DfmeaProposal = {
      ...proposal,
      status: 'failed',
    };

    await recordAppliedProposal(input.projectRoot, failedProposal);

    throw error;
  }
}
