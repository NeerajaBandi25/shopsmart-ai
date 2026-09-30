import { proxyAiRequest } from '../../_ai-proxy';

export function GET(request: Request): Promise<Response> {
  return proxyAiRequest(request, '/ai/documents', { method: 'GET' });
}

export function POST(request: Request): Promise<Response> {
  return proxyAiRequest(request, '/ai/documents', { method: 'POST', forwardBody: true });
}
