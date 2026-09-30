import { proxyAiRequest } from '../../../_ai-proxy';

export function POST(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const title = url.searchParams.get('title');
  const sourceName = url.searchParams.get('source_name');
  const endpoint = `/ai/documents/upload?title=${encodeURIComponent(title ?? '')}&source_name=${encodeURIComponent(sourceName ?? '')}`;
  return proxyAiRequest(request, endpoint, { method: 'POST', forwardBody: true });
}