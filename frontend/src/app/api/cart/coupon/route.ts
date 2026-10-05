import { proxyCommerceRequest } from '../../_commerce-proxy';

export function POST(request: Request): Promise<Response> {
  return proxyCommerceRequest(request, '/cart/coupon', {
    method: 'POST',
    forwardCookie: true,
    forwardCsrfToken: true,
    forwardBody: true,
  });
}

export function DELETE(request: Request): Promise<Response> {
  return proxyCommerceRequest(request, '/cart/coupon', {
    method: 'DELETE',
    forwardCookie: true,
    forwardCsrfToken: true,
  });
}
