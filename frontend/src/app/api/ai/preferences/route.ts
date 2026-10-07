import { proxyAiRequest } from '../../_ai-proxy';

export function GET(request: Request): Promise<Response> {
  return proxyAiRequest(request, '/ai/preferences', { method: 'GET' });
}

export function PUT(request: Request): Promise<Response> {
  return proxyAiRequest(request, '/ai/preferences', { method: 'PUT', forwardBody: true });
}

export function DELETE(request: Request): Promise<Response> {
  return proxyAiRequest(request, '/ai/preferences', { method: 'DELETE' });
}
