import { proxyAuthRequest } from '../_proxy';

export function POST(request: Request): Promise<Response> {
  return proxyAuthRequest(request, '/auth/logout', {
    method: 'POST',
    forwardCookie: true,
    forwardCsrfToken: true,
  });
}
