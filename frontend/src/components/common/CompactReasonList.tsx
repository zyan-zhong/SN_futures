export interface CompactReasonItem {
  label?: string;
  reason?: string;
  next?: string;
}

export function CompactReasonList({ items }: { items: CompactReasonItem[] }) {
  const visibleItems = items.filter((item) => item.label || item.reason || item.next);

  if (!visibleItems.length) {
    return null;
  }

  return (
    <ul className="compact-reason-list">
      {visibleItems.map((item, index) => (
        <li key={`${item.label || "reason"}-${index}`}>
          {item.label ? <strong>{item.label}</strong> : null}
          {item.reason ? <span>{item.reason}</span> : null}
          {item.next ? <em>{item.next}</em> : null}
        </li>
      ))}
    </ul>
  );
}
