import { proxyAuthRequest } from '../_proxy';

export function GET(request: Request): Promise<Response> {
  return proxyAuthRequest(request, '/auth/me', {
    method: 'GET',
    forwardCookie: true,
  });
}
