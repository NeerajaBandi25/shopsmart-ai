import { proxyAuthRequest } from '../_proxy';

export function PUT(request: Request): Promise<Response> {
  return proxyAuthRequest(request, '/users/password', {
    method: 'PUT',
    forwardCookie: true,
    forwardCsrfToken: true,
    forwardBody: true,
  });
}
