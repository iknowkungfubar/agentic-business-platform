/* Edge LLM — in-browser inference via WebGPU for zero-latency classification.
 * Routes simple queries locally, only calling backend for complex tasks.
 * Gracefully falls back when WebGPU/@mlc-ai/web-llm is unavailable. */

let webllmLoaded = false;
let webllmModel: any = null;

export interface EdgeInferenceResult {
  handled: boolean;
  response?: string;
  intent?: string;
}

export async function initEdgeLLM(): Promise<boolean> {
  if (webllmLoaded) return true;
  try {
    const { CreateWebWorkerMLCEngine } = await import('@mlc-ai/web-llm');
    webllmModel = await CreateWebWorkerMLCEngine('Qwen2.5-1.5B-Instruct-q4f16_1-MLC', {
      initProgressCallback: (p: { text: string; progress: number }) => {
        console.log(`[EdgeLLM] ${p.text} (${(p.progress * 100).toFixed(0)}%)`);
      },
    });
    webllmLoaded = true;
    return true;
  } catch {
    return false;
  }
}

export async function classifyEdge(prompt: string): Promise<EdgeInferenceResult> {
  if (!webllmLoaded && !(await initEdgeLLM())) return { handled: false };
  try {
    const r = await webllmModel.chat.completions.create({
      messages: [
        { role: 'system', content: 'Respond concisely. If the user asks about specific data, respond with just NEEDS_BACKEND.' },
        { role: 'user', content: prompt },
      ],
      max_tokens: 256,
    });
    const text = r.choices?.[0]?.message?.content || '';
    if (text.includes('NEEDS_BACKEND')) return { handled: false };
    return { handled: true, response: text, intent: 'local_chat' };
  } catch {
    return { handled: false };
  }
}

export function isWebGPUSupported(): boolean {
  return typeof navigator !== 'undefined' && 'gpu' in navigator;
}
