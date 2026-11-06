import type { ReactNode } from 'react';
import { humanize } from '../format';

export function Badge({ status, children }: { readonly status: string; readonly children?: ReactNode }) {
  const kind = /DELAY|CRITICAL|BLOCKED|AT_RISK/i.test(status) ? 'danger' : /READY|DELIVERED|NORMAL|RESOLVED|AVAILABLE/i.test(status) ? 'success' : /TRANSIT|DISPATCH|PRODUC|RECOVERY/i.test(status) ? 'active' : 'neutral';
  return <span className={`badge badge-${kind}`}><span className="status-dot" />{children ?? humanize(status)}</span>;
}

export function Field({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return <div className="detail-field"><dt>{label}</dt><dd>{children}</dd></div>;
}

export function Empty({ title, children }: { readonly title: string; readonly children: ReactNode }) {
  return <div className="empty-state"><strong>{title}</strong><p>{children}</p></div>;
}
