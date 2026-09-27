import { proxyAuthRequest } from '../_proxy';

export function GET(request: Request): Promise<Response> {
  return proxyAuthRequest(request, '/auth/csrf', {
    method: 'GET',
    forwardCookie: true,
  });
}
