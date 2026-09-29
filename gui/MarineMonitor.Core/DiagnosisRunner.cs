using System.Diagnostics;
using System.Text.Json;

namespace MarineMonitor.Core;

public sealed record FaultPrediction
{
    public string Key { get; init; } = "";
    public string Title { get; init; } = "";
    public double AbnormalProbability { get; init; }
    public double Threshold { get; init; }
    public bool Abnormal { get; init; }
    public string ModelSha256 { get; init; } = "";
    public string Display => $"{Title}   {(Abnormal ? "비정상" : "정상")}  ·  비정상 확률 {AbnormalProbability:P1}";
}
public sealed record DiagnosisResult
{
    public string FileName { get; init; } = "";
    public string Mode { get; init; } = "";
    public int SampleCount { get; init; }
    public double SamplingFrequency { get; init; }
    public FaultPrediction[] Results { get; init; } = [];
}

public sealed class DiagnosisRunner
{
    private readonly SemaphoreSlim gate = new(1);
    public static string FindProjectRoot()
    {
        string? configured = Environment.GetEnvironmentVariable("SHIP_ROBOT_PROJECT");
        if (!string.IsNullOrWhiteSpace(configured)) return Path.GetFullPath(configured);
        foreach (string origin in new[] { AppContext.BaseDirectory, Environment.CurrentDirectory })
            for (var directory = new DirectoryInfo(origin); directory != null; directory = directory.Parent)
                if (File.Exists(Path.Combine(directory.FullName, "tools", "diagnosis", "diagnose.py"))) return directory.FullName;
        throw new DirectoryNotFoundException("프로젝트 폴더를 찾을 수 없습니다. SHIP_ROBOT_PROJECT를 지정하세요.");
    }

    public async Task<DiagnosisResult> RunAsync(string csvPath, CancellationToken cancellation = default)
    {
        await gate.WaitAsync(cancellation);
        try
        {
            string root = FindProjectRoot();
            string python = Environment.GetEnvironmentVariable("SHIP_DIAGNOSIS_PYTHON") ??
                Path.Combine(root, ".venv-diagnosis", "Scripts", "python.exe");
            if (!File.Exists(python)) throw new FileNotFoundException("진단 Python이 없습니다. tools/diagnosis/README.md의 설치 절차를 확인하세요.");
            var start = new ProcessStartInfo(python)
            {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            start.Environment["PYTHONIOENCODING"] = "utf-8";
            foreach (string argument in new[] { Path.Combine(root, "tools", "diagnosis", "diagnose.py"),
                "--csv", csvPath, "--data-root", Path.Combine(root, "data") }) start.ArgumentList.Add(argument);
            using var process = Process.Start(start) ?? throw new IOException("진단 프로세스 시작 실패");
            using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            deadline.CancelAfter(TimeSpan.FromSeconds(45));
            Task<string> output = process.StandardOutput.ReadToEndAsync();
            Task<string> error = process.StandardError.ReadToEndAsync();
            try { await process.WaitForExitAsync(deadline.Token); }
            catch (OperationCanceledException)
            {
                if (!process.HasExited) process.Kill(true);
                await process.WaitForExitAsync();
                throw new IOException("진단이 취소되었거나 45초 제한을 초과했습니다.");
            }
            string stdout = await output, stderr = await error;
            if (process.ExitCode != 0) throw new IOException("진단 실패: " + stderr.Trim());
            var result = JsonSerializer.Deserialize<DiagnosisResult>(stdout, Telemetry.JsonOptions)
                ?? throw new JsonException("진단 결과가 비어 있습니다.");
            if (result.Results == null || result.Results.Length != 4 || result.Mode != "offline_csv_replay" ||
                result.Results.Select(x => x.Key).Distinct().Count() != 4 ||
                result.Results.Any(x => !double.IsFinite(x.AbnormalProbability) || x.AbnormalProbability < 0 ||
                    x.AbnormalProbability > 1 || x.Threshold != 0.5 || x.Abnormal != (x.AbnormalProbability >= x.Threshold)))
                throw new JsonException("진단 결과 형식 오류");
            return result;
        }
        finally { gate.Release(); }
    }
}
