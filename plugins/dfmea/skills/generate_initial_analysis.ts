import type { PluginExecutionContext } from '@dfmea/plugin-sdk';
import { generateInitialAnalysis } from '../src/index';
import type { GenerateInitialAnalysisInput, GenerateInitialAnalysisOutput } from '../src/index';

export async function handleGenerateInitialAnalysis(
  input: GenerateInitialAnalysisInput,
  context: PluginExecutionContext,
): Promise<GenerateInitialAnalysisOutput> {
  void context;
  return generateInitialAnalysis(input);
}
