const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
});

export function formatInr(minorUnits: number): string {
  return inrFormatter.format(minorUnits / 100);
}