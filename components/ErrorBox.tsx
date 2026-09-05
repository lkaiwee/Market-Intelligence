export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="error-box">
      <strong>Unable to load data</strong>
      <span>{message}</span>
    </div>
  );
}
