export interface DfmeaProposalOperation {
  type: 'add_section' | 'update_section' | 'append_note'
  file: string
  section: string
  description: string
}

export interface DfmeaProposal {
  proposalId: string
  actionId: 'complete' | 'review-apply'
  projectId: string
  subtreeId: string
  summary: string
  targetFiles: string[]
  operations: DfmeaProposalOperation[]
  status: 'proposed' | 'confirmed' | 'applied' | 'failed'
  createdAt: string
}
