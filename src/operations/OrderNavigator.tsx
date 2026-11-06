import { useState } from 'react';
import { Search } from 'lucide-react';
import type { World } from '../contracts';
import { useNavigationStore, type OperationsSelection } from './navigation';
import { productLabel } from './presentation';

export function OrderNavigator({ world }: { readonly world: World }) {
  const [query, setQuery] = useState('');
  const { selection, select: selectNavigation, setLevel } = useNavigationStore();
  const select = (next: OperationsSelection): void => { selectNavigation(next); setLevel('overview'); };
  const orders = world.orders.filter(order => `${order.id} ${order.product_id} ${order.grade} ${world.customers.find(customer => customer.id === order.customer_id)?.name ?? ''}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <aside className="ops-orders" aria-label="주문 탐색"><div className="ops-panel-heading"><h2>주문</h2><span>{world.orders.length}건</span></div><label className="ops-search"><Search size={16} /><input aria-label="주문 검색" placeholder="주문·고객·제품 검색" value={query} onChange={event => setQuery(event.target.value)} /></label><div className="ops-order-list">{orders.map(order => <button key={order.id} data-testid={`order-${order.id}`} aria-pressed={selection.order_id === order.id} onClick={() => select({ run_id: world.run.id, order_id: order.id, material_id: order.material_ids.find(id => world.materials.some(material => material.id === id && material.active)) ?? order.material_ids[0] })}><span><strong>{order.id}</strong><b>{productLabel(order.product_id)}</b></span><span>{world.customers.find(customer => customer.id === order.customer_id)?.name ?? order.customer_id}</span><small>{order.quantity_kg.toLocaleString('ko-KR')} kg · {order.grade}</small><span className="ops-order-progress"><progress aria-label={`${order.id} 배송 완료율`} value={order.delivered_kg} max={order.quantity_kg} /><small>{Math.round(order.delivered_kg / order.quantity_kg * 100)}%</small></span></button>)}</div>{orders.length === 0 && <p className="ops-empty" role="status">검색 결과가 없습니다. 주문 ID나 고객명을 확인해 주세요.</p>}</aside>;
}
