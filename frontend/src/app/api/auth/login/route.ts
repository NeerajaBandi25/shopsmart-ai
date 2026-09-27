import { proxyAuthRequest } from '../_proxy';

export function POST(request: Request): Promise<Response> {
  return proxyAuthRequest(request, '/auth/login', {
    method: 'POST',
    forwardBody: true,
  });
}
