export const tonnes = (kg: number): string => `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(kg / 1000)}`;
export const kilograms = (kg: number): string => `${new Intl.NumberFormat('en-US').format(kg)} kg`;
export const humanize = (value: string): string => value.toLowerCase().replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase());
export function timeUTC(value: string): string {
  return new Date(value).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
}
export function dateUTC(value: string): string {
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' });
}
