import { proxyAiRequest } from '../../_ai-proxy';

export function GET(request: Request): Promise<Response> {
  return proxyAiRequest(request, '/ai/conversations', { method: 'GET' });
}
