import { proxyCommerceRequest } from '../../../_commerce-proxy';

type RouteContext = { params: { productId: string } };

function productEndpoint(productId: string): string {
  return `/cart/items/${encodeURIComponent(productId)}`;
}

export function PUT(request: Request, { params }: RouteContext): Promise<Response> {
  return proxyCommerceRequest(request, productEndpoint(params.productId), {
    method: 'PUT',
    forwardCookie: true,
    forwardCsrfToken: true,
    forwardBody: true,
  });
}

export function DELETE(request: Request, { params }: RouteContext): Promise<Response> {
  return proxyCommerceRequest(request, productEndpoint(params.productId), {
    method: 'DELETE',
    forwardCookie: true,
    forwardCsrfToken: true,
  });
}
