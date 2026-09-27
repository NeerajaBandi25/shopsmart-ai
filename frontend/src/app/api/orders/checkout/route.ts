import { proxyCommerceRequest } from '../../_commerce-proxy';

export function POST(request: Request): Promise<Response> {
  return proxyCommerceRequest(request, '/orders/checkout', {
    method: 'POST',
    forwardCookie: true,
    forwardCsrfToken: true,
    forwardIdempotencyKey: true,
    forwardBody: true,
  });
}
