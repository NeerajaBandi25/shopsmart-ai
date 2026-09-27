import { proxyCommerceRequest } from '../../_commerce-proxy';

export function POST(request: Request): Promise<Response> {
  return proxyCommerceRequest(request, '/cart/items', {
    method: 'POST',
    forwardCookie: true,
    forwardCsrfToken: true,
    forwardBody: true,
  });
}
