import type { DfmeaRuntimeNode, DfmeaRuntimeShard } from './runtimeIndex';

function scoreNode(node: DfmeaRuntimeNode, query: string): number {
  const lowerQuery = query.trim().toLowerCase();
  if (!lowerQuery) {
    return 0;
  }

  let score = 0;
  const lowerTitle = node.title.toLowerCase();
  const lowerSummary = node.summary.toLowerCase();
  const lowerId = node.id.toLowerCase();
  const lowerSection = node.section.toLowerCase();

  if (lowerTitle === lowerQuery) score += 100;
  if (lowerId === lowerQuery) score += 90;
  if (lowerTitle.includes(lowerQuery)) score += 40;
  if (lowerSummary.includes(lowerQuery)) score += 20;
  if (lowerSection.includes(lowerQuery)) score += 10;

  if (lowerSection.includes('failure')) score += 5;

  return score;
}

export function searchRuntimeShard(shard: DfmeaRuntimeShard, query: string): DfmeaRuntimeNode[] {
  return [...shard.nodes]
    .map((node) => ({ node, score: scoreNode(node, query) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.node.title.localeCompare(b.node.title))
    .map((entry) => entry.node);
}

export function findRuntimeNodeById(shard: DfmeaRuntimeShard, id: string): DfmeaRuntimeNode | null {
  return shard.nodes.find((node) => node.id === id) ?? null;
}
