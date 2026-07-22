// Type declarations for optional modules
declare module '@mlc-ai/web-llm' {
  export function CreateWebWorkerMLCEngine(
    model: string,
    options?: { initProgressCallback?: (p: { text: string; progress: number }) => void },
  ): Promise<any>;
}
