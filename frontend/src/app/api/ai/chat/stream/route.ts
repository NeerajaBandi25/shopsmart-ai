import { proxyAiRequest } from '../../../_ai-proxy';

export function POST(request: Request): Promise<Response> {
  return proxyAiRequest(request, '/ai/chat/stream', {
    method: 'POST',
    forwardBody: true,
    streamResponse: true,
  });
}
