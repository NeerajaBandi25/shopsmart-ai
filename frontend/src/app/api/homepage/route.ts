import { proxyCommerceRequest } from '../_commerce-proxy';

export function GET(request: Request): Promise<Response> {
  return proxyCommerceRequest(request, '/products/homepage', { method: 'GET' });
}
