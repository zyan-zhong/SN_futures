import { deriveSafeConfigSteps } from "../../utils/guidedSetup";

export function SafeConfigInstructions() {
  return (
    <section aria-label="Safe Config Instructions" className="safe-config-instructions">
      <header>
        <strong>安全配置方式</strong>
        <span>终端不会接收 raw token，也不会把 endpoint/token 写入页面、日志或报告。</span>
      </header>
      <ul>
        {deriveSafeConfigSteps().map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ul>
    </section>
  );
}
