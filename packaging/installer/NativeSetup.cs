using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

namespace SNInsightInstaller
{
    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            if (HasArgument(args, "--smoke-test"))
            {
                RunSmokeTest();
                return;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SetupForm());
        }

        private static bool HasArgument(string[] args, string expected)
        {
            foreach (string arg in args)
            {
                if (string.Equals(arg, expected, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        private static void RunSmokeTest()
        {
            string marker = Environment.GetEnvironmentVariable("SN_SETUP_SMOKE_MARKER");
            if (string.IsNullOrWhiteSpace(marker))
            {
                marker = Path.Combine(Environment.CurrentDirectory, "setup_smoke_ok.txt");
            }

            File.WriteAllText(marker, "ok " + DateTime.Now.ToString("O"));
            Environment.Exit(0);
        }
    }

    internal sealed class SetupForm : Form
    {
        private const string AppName = "SN Insight Terminal";
        private const string VersionLabel = "V2.8 统一融合版";
        private const string AppExe = "SNInsightTerminal.exe";

        private readonly Label _statusLabel;
        private readonly ProgressBar _progressBar;
        private readonly Button _installButton;
        private readonly Button _cancelButton;

        public SetupForm()
        {
            Text = AppName + " 覆盖安装";
            ClientSize = new Size(560, 300);
            MinimumSize = new Size(560, 300);
            MaximumSize = new Size(560, 300);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            TopMost = true;

            var title = new Label
            {
                Text = AppName + " " + VersionLabel,
                AutoSize = false,
                Font = new Font("Microsoft YaHei UI", 15f, FontStyle.Bold),
                Left = 18,
                Top = 18,
                Width = 500,
                Height = 34
            };
            Controls.Add(title);

            var disclaimer = new Label
            {
                Text = "本软件仅用于上海期货交易所沪锡期货量化投研参考，不接入实盘交易，不构成任何投资建议，期货交易有风险。",
                AutoSize = false,
                Left = 18,
                Top = 58,
                Width = 520,
                Height = 52
            };
            Controls.Add(disclaimer);

            var installPath = new Label
            {
                Text = "默认覆盖安装位置：" + GetInstallDir(),
                AutoSize = false,
                Left = 18,
                Top = 116,
                Width = 520,
                Height = 32
            };
            Controls.Add(installPath);

            _statusLabel = new Label
            {
                Text = "点击“安装/覆盖”部署最新版桌面终端。",
                AutoSize = false,
                Left = 18,
                Top = 152,
                Width = 520,
                Height = 28
            };
            Controls.Add(_statusLabel);

            _progressBar = new ProgressBar
            {
                Left = 18,
                Top = 188,
                Width = 520,
                Height = 24,
                Minimum = 0,
                Maximum = 100
            };
            Controls.Add(_progressBar);

            _cancelButton = new Button
            {
                Text = "取消",
                Width = 88,
                Height = 30,
                Left = 450,
                Top = 236
            };
            _cancelButton.Click += delegate { Close(); };
            Controls.Add(_cancelButton);

            _installButton = new Button
            {
                Text = "安装/覆盖",
                Width = 88,
                Height = 30,
                Left = 354,
                Top = 236
            };
            _installButton.Click += InstallButtonOnClick;
            Controls.Add(_installButton);
        }

        private void InstallButtonOnClick(object sender, EventArgs e)
        {
            _installButton.Enabled = false;
            _cancelButton.Enabled = false;

            try
            {
                InstallApplication();
                MessageBox.Show(this, "桌面快捷方式已创建，软件将自动启动。", "安装完成", MessageBoxButtons.OK, MessageBoxIcon.Information);
                Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "安装器错误：\n\n" + ex.Message, "安装失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                _installButton.Enabled = true;
                _cancelButton.Enabled = true;
            }
        }

        private void InstallApplication()
        {
            string targetDir = GetInstallDir();
            string exePath = Path.Combine(targetDir, AppExe);

            UpdateStatus("正在准备覆盖安装目录...", 5);
            if (Directory.Exists(targetDir))
            {
                TryKillRunningApp();
                Directory.Delete(targetDir, true);
            }
            Directory.CreateDirectory(targetDir);

            UpdateStatus("正在解压最新版应用文件...", 10);
            ExtractBundle(targetDir);

            UpdateStatus("正在写入卸载入口...", 90);
            string uninstallPath = WriteUninstallScript(targetDir);

            UpdateStatus("正在创建桌面快捷方式...", 96);
            CreateShortcut(exePath, uninstallPath);

            UpdateStatus("正在启动沪锡终端...", 100);
            Process.Start(new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = "--installed",
                WorkingDirectory = targetDir,
                UseShellExecute = true
            });
        }

        private void ExtractBundle(string targetDir)
        {
            Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("AppBundleZip");
            if (resource == null)
            {
                string setupDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                string[] sidecarCandidates = new string[]
                {
                    Path.Combine(setupDir, "SNInsightTerminal_GPU_AppBundle.zip"),
                    Path.Combine(setupDir, "SNInsightTerminal_AppBundle.zip"),
                    Path.Combine(setupDir, "app_bundle.zip")
                };
                foreach (string candidate in sidecarCandidates)
                {
                    if (File.Exists(candidate))
                    {
                        resource = File.OpenRead(candidate);
                        break;
                    }
                }
                if (resource == null)
                {
                    throw new InvalidOperationException("未找到应用文件包。GPU-Full 安装请把 *_AppBundle.zip 与安装器 exe 放在同一文件夹。");
                }
            }

            using (resource)
            {
                using (var archive = new ZipArchive(resource, ZipArchiveMode.Read))
                {
                    int total = Math.Max(1, archive.Entries.Count);
                    int current = 0;

                    foreach (ZipArchiveEntry entry in archive.Entries)
                    {
                        current++;
                        int progress = 10 + (int)(75.0 * current / total);
                        UpdateStatus("正在解压 " + entry.FullName, progress);

                        string destinationPath = Path.Combine(targetDir, entry.FullName);
                        string fullDestination = Path.GetFullPath(destinationPath);
                        string fullTarget = Path.GetFullPath(targetDir) + Path.DirectorySeparatorChar;
                        if (!fullDestination.StartsWith(fullTarget, StringComparison.OrdinalIgnoreCase))
                        {
                            throw new InvalidOperationException("已阻止不安全的压缩包路径：" + entry.FullName);
                        }

                        if (string.IsNullOrEmpty(entry.Name))
                        {
                            Directory.CreateDirectory(fullDestination);
                            continue;
                        }

                        string directory = Path.GetDirectoryName(fullDestination);
                        if (!string.IsNullOrEmpty(directory))
                        {
                            Directory.CreateDirectory(directory);
                        }

                        entry.ExtractToFile(fullDestination, true);
                        Application.DoEvents();
                    }
                }
            }
        }

        private static string WriteUninstallScript(string targetDir)
        {
            string uninstallPath = Path.Combine(targetDir, "uninstall.cmd");
            string content =
                "@echo off\r\n" +
                "setlocal\r\n" +
                "set \"APP_DIR=%~dp0\"\r\n" +
                "powershell -NoProfile -ExecutionPolicy Bypass -Command \"& { $desktop=[Environment]::GetFolderPath('Desktop'); $desktopShortcut=Join-Path $desktop 'SN Insight Terminal.lnk'; if (Test-Path $desktopShortcut) { Remove-Item -LiteralPath $desktopShortcut -Force }; $folder=Join-Path ([Environment]::GetFolderPath('Programs')) 'SN Insight Terminal'; if (Test-Path $folder) { Remove-Item -LiteralPath $folder -Recurse -Force } }\"\r\n" +
                "taskkill /IM SNInsightTerminal.exe /F >nul 2>nul\r\n" +
                "start \"\" /min cmd /c \"timeout /t 2 /nobreak >nul & rmdir /S /Q \"\"%APP_DIR%\"\"\"\r\n" +
                "exit /b 0\r\n";

            File.WriteAllText(uninstallPath, content);
            return uninstallPath;
        }

        private static void CreateShortcut(string exePath, string uninstallPath)
        {
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            if (shellType == null)
            {
                throw new InvalidOperationException("未找到 WScript.Shell，无法创建快捷方式。");
            }

            dynamic shell = Activator.CreateInstance(shellType);
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string programs = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
            string folder = Path.Combine(programs, "SN Insight Terminal");
            Directory.CreateDirectory(folder);

            dynamic desktopShortcut = shell.CreateShortcut(Path.Combine(desktop, "SN Insight Terminal.lnk"));
            desktopShortcut.TargetPath = exePath;
            desktopShortcut.WorkingDirectory = Path.GetDirectoryName(exePath);
            desktopShortcut.Save();

            dynamic startShortcut = shell.CreateShortcut(Path.Combine(folder, "SN Insight Terminal.lnk"));
            startShortcut.TargetPath = exePath;
            startShortcut.WorkingDirectory = Path.GetDirectoryName(exePath);
            startShortcut.Save();

            dynamic uninstallShortcut = shell.CreateShortcut(Path.Combine(folder, "Uninstall SN Insight Terminal.lnk"));
            uninstallShortcut.TargetPath = uninstallPath;
            uninstallShortcut.WorkingDirectory = Path.GetDirectoryName(exePath);
            uninstallShortcut.Save();
        }

        private static void TryKillRunningApp()
        {
            try
            {
                foreach (Process process in Process.GetProcessesByName("SNInsightTerminal"))
                {
                    process.Kill();
                }
            }
            catch
            {
                // Best effort only.
            }
        }

        private void UpdateStatus(string text, int progress)
        {
            _statusLabel.Text = text;
            _progressBar.Value = Math.Max(_progressBar.Minimum, Math.Min(_progressBar.Maximum, progress));
            Application.DoEvents();
        }

        private static string GetInstallDir()
        {
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(localAppData, "Programs", AppName);
        }
    }
}
