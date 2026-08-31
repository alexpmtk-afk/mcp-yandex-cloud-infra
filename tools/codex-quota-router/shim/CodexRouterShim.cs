using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

public static class CodexRouterShim
{
    public static int Main(string[] args)
    {
        try
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string realExe = Environment.GetEnvironmentVariable("CODEX_ROUTER_REAL_EXE");
            if (String.IsNullOrWhiteSpace(realExe))
                realExe = Path.Combine(baseDir, "codex-real.exe");

            if (!File.Exists(realExe))
            {
                Console.Error.WriteLine("Codex Auto Router: real Codex executable not found: " + realExe);
                return 127;
            }

            string codexHome = Environment.GetEnvironmentVariable("CODEX_HOME");
            if (String.IsNullOrWhiteSpace(codexHome))
                codexHome = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".codex");

            string proxyScript = Environment.GetEnvironmentVariable("CODEX_ROUTER_PROXY_JS");
            if (String.IsNullOrWhiteSpace(proxyScript))
                proxyScript = Path.Combine(codexHome, "quota-router", "bin", "app-server-proxy.js");

            if (!File.Exists(proxyScript))
            {
                Console.Error.WriteLine("Codex Auto Router: proxy script not found: " + proxyScript);
                return 127;
            }

            string nodeExe = Environment.GetEnvironmentVariable("CODEX_ROUTER_NODE");
            if (String.IsNullOrWhiteSpace(nodeExe))
            {
                string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
                string candidate = Path.Combine(programFiles, "nodejs", "node.exe");
                nodeExe = File.Exists(candidate) ? candidate : "node.exe";
            }

            StringBuilder command = new StringBuilder();
            command.Append(QuoteArg(proxyScript));
            command.Append(' ');
            command.Append(QuoteArg(realExe));
            foreach (string arg in args)
            {
                command.Append(' ');
                command.Append(QuoteArg(arg));
            }

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = nodeExe;
            psi.Arguments = command.ToString();
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardInput = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;

            Process child = Process.Start(psi);
            if (child == null)
            {
                Console.Error.WriteLine("Codex Auto Router: failed to start proxy process.");
                return 127;
            }

            Thread inputPump = new Thread(delegate()
            {
                try
                {
                    Stream input = Console.OpenStandardInput();
                    input.CopyTo(child.StandardInput.BaseStream);
                    child.StandardInput.Close();
                }
                catch { }
            });
            inputPump.IsBackground = true;

            Thread outputPump = new Thread(delegate()
            {
                try
                {
                    Stream output = Console.OpenStandardOutput();
                    child.StandardOutput.BaseStream.CopyTo(output);
                    output.Flush();
                }
                catch { }
            });
            outputPump.IsBackground = true;

            Thread errorPump = new Thread(delegate()
            {
                try
                {
                    Stream error = Console.OpenStandardError();
                    child.StandardError.BaseStream.CopyTo(error);
                    error.Flush();
                }
                catch { }
            });
            errorPump.IsBackground = true;

            inputPump.Start();
            outputPump.Start();
            errorPump.Start();

            child.WaitForExit();
            outputPump.Join(5000);
            errorPump.Join(5000);
            return child.ExitCode;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("Codex Auto Router shim failed: " + ex.Message);
            return 127;
        }
    }

    private static string QuoteArg(string arg)
    {
        if (arg == null || arg.Length == 0)
            return "\"\"";

        bool needsQuotes = false;
        for (int i = 0; i < arg.Length; i++)
        {
            char c = arg[i];
            if (Char.IsWhiteSpace(c) || c == '"')
            {
                needsQuotes = true;
                break;
            }
        }
        if (!needsQuotes)
            return arg;

        StringBuilder result = new StringBuilder();
        result.Append('"');
        int backslashes = 0;
        for (int i = 0; i < arg.Length; i++)
        {
            char c = arg[i];
            if (c == '\\')
            {
                backslashes++;
                continue;
            }
            if (c == '"')
            {
                result.Append('\\', backslashes * 2 + 1);
                result.Append('"');
                backslashes = 0;
                continue;
            }
            if (backslashes > 0)
            {
                result.Append('\\', backslashes);
                backslashes = 0;
            }
            result.Append(c);
        }
        if (backslashes > 0)
            result.Append('\\', backslashes * 2);
        result.Append('"');
        return result.ToString();
    }
}
