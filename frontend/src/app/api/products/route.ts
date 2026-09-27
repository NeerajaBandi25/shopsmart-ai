import { proxyCommerceRequest } from '../_commerce-proxy';

export function GET(request: Request): Promise<Response> {
  const query = new URL(request.url).searchParams.toString();
  return proxyCommerceRequest(request, '/products', {
    method: 'GET',
    query,
  });
}
