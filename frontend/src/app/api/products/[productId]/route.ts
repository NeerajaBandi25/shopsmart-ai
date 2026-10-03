import { proxyCommerceRequest } from '../../_commerce-proxy';

export function GET(
  request: Request,
  context: { params: { productId: string } }
): Promise<Response> {
  return proxyCommerceRequest(
    request,
    `/products/${encodeURIComponent(context.params.productId)}`,
    { method: 'GET' }
  );
}