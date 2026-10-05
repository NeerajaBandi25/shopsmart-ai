import { proxyCommerceRequest } from '../../_commerce-proxy';

export function GET(request: Request, context: { params: { orderId: string } }): Promise<Response> {
  const { orderId } = context.params;
  if (!/^[0-9a-f-]{36}$/i.test(orderId)) {
    return Promise.resolve(
      Response.json(
        { detail: 'Order not found', error_code: 'not_found', status_code: 404 },
        { status: 404, headers: { 'Cache-Control': 'no-store' } }
      )
    );
  }
  return proxyCommerceRequest(request, `/orders/${encodeURIComponent(orderId)}`, {
    method: 'GET',
    forwardCookie: true,
  });
}
