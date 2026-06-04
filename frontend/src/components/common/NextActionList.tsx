export function NextActionList({ actions }: { actions: string[] }) {
  return (
    <ul className="next-action-list">
      {actions.slice(0, 4).map((action) => (
        <li key={action}>{action}</li>
      ))}
    </ul>
  );
}

