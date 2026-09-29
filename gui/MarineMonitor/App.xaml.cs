using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace MarineMonitor;
public partial class App : Application
{
    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        var window = new MainWindow(); MainWindow = window;
        if (e.Args.Length >= 2 && e.Args[0] == "--preview")
        {
            window.Model.LoadPreview();
            Capture(window, e.Args[1]); await window.Model.CloseAsync(); Shutdown(); return;
        }
        if (e.Args.Length >= 3 && e.Args[0] == "--smoke")
        {
            string output = Path.GetFullPath(e.Args[2]);
            try
            {
                async Task WaitFor(Func<bool> condition)
                {
                    var until = DateTime.UtcNow.AddSeconds(50);
                    while (!condition()) { if (DateTime.UtcNow > until) throw new TimeoutException("WPF smoke condition timed out"); await Task.Delay(50); }
                }
                window.Model.Port = e.Args[1]; window.Model.Connect.Execute(null);
                var a = window.Model.Equipment[0]; var b = window.Model.Equipment[1];
                await WaitFor(() => a.State == "재생 중" && b.State == "재생 중");
                await WaitFor(() => a.CurrentTrend.Points.Count >= 15);
                a.Control.Execute("pause");
                await WaitFor(() => a.State == "일시정지" && a.LastCommand.StartsWith("성공"));
                if (b.State != "재생 중") throw new Exception("B must keep playing");
                a.Control.Execute("resume");
                await WaitFor(() => a.State == "재생 중" && a.Control.CanExecute("pause"));
                await WaitFor(() => window.Model.MissionControl.CanExecute("mission_start"));
                window.Model.MissionControl.Execute("mission_start");
                await WaitFor(() => window.Model.Inspections.Count == 1 &&
                    window.Model.Inspections[0].Status != "진단 대기 / 분석 중");
                if (window.Model.Inspections[0].Predictions.Count != 4)
                    throw new Exception(window.Model.Inspections[0].Details);
                await Task.Delay(300);
                if (window.Model.Inspections.Count != 1) throw new Exception("Duplicate inspection result");
                if (window.Model.MissionControl.CanExecute("mission_start")) throw new Exception("Repeated start must be disabled");
                Capture(window, output + ".png");
                window.Model.Connect.Execute(null);
                await WaitFor(() => !a.Control.CanExecute("pause") && a.CurrentValues.Contains("—"));
                Directory.CreateDirectory(Path.GetDirectoryName(output)!);
                await File.WriteAllTextAsync(output + ".txt", "PASS: WPF receives A/B, plots, pauses/resumes, sends mission start to TEST SERVER, processes one inspection once, runs all four REAL models, disables repeated start, clears live values on disconnect. Unity driving is not exercised.");
                await window.Model.CloseAsync(); Shutdown(0);
            }
            catch (Exception ex)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(output)!);
                await File.WriteAllTextAsync(output + ".txt", ex.ToString());
                await window.Model.CloseAsync(); Shutdown(1);
            }
            return;
        }
        window.Show();
    }
    public static void Capture(MainWindow window, string path)
    {
        window.Root.Measure(new Size(1440, 960)); window.Root.Arrange(new Rect(0, 0, 1440, 960)); window.Root.UpdateLayout();
        var image = new RenderTargetBitmap(1440, 960, 96, 96, PixelFormats.Pbgra32); image.Render(window.Root);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(image));
        using var output = File.Create(path); encoder.Save(output);
    }
}
