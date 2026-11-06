import ky from 'ky';
import { JourneyCatalogSchema } from './contracts';
import type { ProductDefinition } from './contracts';

const client = ky.create({ prefixUrl: '/api/v1', timeout: 8000, retry: 0 });
export async function getProducts(): Promise<ProductDefinition[]> {
  return JourneyCatalogSchema.parse(await client.get('journey/products').json()).products.map(product => ({ ...product, id: product.id.toLowerCase() }));
}
