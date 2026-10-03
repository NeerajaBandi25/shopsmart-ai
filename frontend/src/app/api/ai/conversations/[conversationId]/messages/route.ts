import { proxyAiRequest } from '../../../../_ai-proxy';

export function GET(
  request: Request,
  { params }: { params: { conversationId: string } }
): Promise<Response> {
  return proxyAiRequest(
    request,
    `/ai/conversations/${encodeURIComponent(params.conversationId)}/messages`,
    { method: 'GET' }
  );
}
