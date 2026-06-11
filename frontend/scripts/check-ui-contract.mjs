import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const scanRoots = [path.join(root, "src"), path.join(root, "index.html")];
const allowedLocalStorageKeys = new Set([
  "firstRunCompleted",
  "showDebug",
  "refreshInterval",
  "theme",
  "showSampleData",
  "autoStopBackendOnClose",
  "SN_ENABLE_DEV_CONSOLE",
  "sn_enable_dev_console"
]);
const forbiddenTerms = [
  ["保证", "盈利"].join(""),
  ["稳", "赚"].join(""),
  ["建议", "买入"].join(""),
  ["建议", "卖出"].join(""),
  ["必", "涨"].join(""),
  ["必", "跌"].join(""),
  ["sure", "profit"].join(" "),
  ["guaranteed", "profit"].join(" "),
  ["buy", "now"].join(" "),
  ["sell", "now"].join(" "),
  ["fake", "probability"].join(" "),
  ["backend", "contract", "complete"].join(" ")
];
const requiredTerms = [
  "不构成投资建议",
  "不承诺收益",
  "不接实盘交易",
  "暂无交易点位",
  "已降级为研究观察",
  "技术明细 / 开发调试信息"
];
const sensitivePatterns = [
  /SN_ALPHA_VANTAGE_KEY=/,
  /SN_NEWSAPI_KEY=/,
  /\bapiKey\s*:/,
  /Authorization\s*:\s*Bearer/i
];

function collectFiles(target) {
  if (!fs.existsSync(target)) return [];
  const stat = fs.statSync(target);
  if (stat.isFile()) return [target];
  const files = [];
  for (const entry of fs.readdirSync(target)) {
    const full = path.join(target, entry);
    const entryStat = fs.statSync(full);
    if (entryStat.isDirectory()) {
      files.push(...collectFiles(full));
    } else if (/\.(ts|tsx|css|html)$/.test(entry)) {
      files.push(full);
    }
  }
  return files;
}

const files = scanRoots.flatMap(collectFiles);
const errors = [];
const combined = files.map((file) => fs.readFileSync(file, "utf8")).join("\n");

for (const file of files) {
  const rel = path.relative(root, file);
  const text = fs.readFileSync(file, "utf8");
  for (const term of forbiddenTerms) {
    if (text.toLowerCase().includes(term.toLowerCase())) {
      errors.push(`发现禁止文案：${term}，文件：${rel}`);
    }
  }
  for (const pattern of sensitivePatterns) {
    if (pattern.test(text)) {
      errors.push(`发现疑似敏感字段写法：${pattern}，文件：${rel}`);
    }
  }
}

for (const term of requiredTerms) {
  if (!combined.includes(term)) {
    errors.push(`缺少必须展示文案：${term}`);
  }
}

const errorBoundaryPath = path.join(root, "src", "components", "common", "ErrorBoundary.tsx");
const firstRunPath = path.join(root, "src", "components", "onboarding", "FirstRunWizard.tsx");
const settingsPath = path.join(root, "src", "pages", "SettingsPage.tsx");
if (!fs.existsSync(errorBoundaryPath)) errors.push("缺少 ErrorBoundary.tsx");
if (!fs.existsSync(firstRunPath)) errors.push("缺少 FirstRunWizard.tsx");
if (fs.existsSync(settingsPath) && fs.readFileSync(settingsPath, "utf8").includes("localStorage")) {
  errors.push("SettingsPage 不应直接访问 localStorage，避免误存密钥。");
}

for (const file of files) {
  const rel = path.relative(root, file);
  const text = fs.readFileSync(file, "utf8");
  const useLocalSettingMatches = text.matchAll(/useLocalSetting\(\s*["'`]([^"'`]+)["'`]/g);
  for (const match of useLocalSettingMatches) {
    if (!allowedLocalStorageKeys.has(match[1])) {
      errors.push(`发现未允许的前端本地偏好键：${match[1]}，文件：${rel}`);
    }
  }
  const directLocalStorageMatches = text.matchAll(/localStorage\.(?:setItem|getItem|removeItem)\(\s*["'`]([^"'`]+)["'`]/g);
  for (const match of directLocalStorageMatches) {
    if (!allowedLocalStorageKeys.has(match[1])) {
      errors.push(`发现未允许的 localStorage 键：${match[1]}，文件：${rel}`);
    }
  }
}

if (errors.length) {
  console.error("UI 合同检查失败：");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log("UI 合同检查通过：中文合规文案、错误边界、密钥安全和本地偏好规则均满足。");
