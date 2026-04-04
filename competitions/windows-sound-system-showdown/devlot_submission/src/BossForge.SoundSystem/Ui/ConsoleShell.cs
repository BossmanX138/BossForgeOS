using BossForge.SoundSystem.Audio;
using BossForge.SoundSystem.Core;

namespace BossForge.SoundSystem.Ui;

public sealed class ConsoleShell
{
    private readonly AppState _state;
    private readonly DeviceManager _deviceManager;
    private readonly PreSpeakerInterceptor _interceptor;
    private readonly SystemSoundManager _systemSoundManager;
    private readonly SafetyRollbackManager _rollback;

    public ConsoleShell(AppState state)
    {
        _state = state;
        _deviceManager = new DeviceManager();
        _interceptor = new PreSpeakerInterceptor(_deviceManager);
        _systemSoundManager = new SystemSoundManager();
        _rollback = new SafetyRollbackManager(_systemSoundManager);
    }

    public async Task RunAsync()
    {
        Console.WriteLine("BossForge Windows Sound System Prototype");
        Console.WriteLine("User-mode DSP path: Loopback capture -> EQ -> Stereo to 7.2 model -> Output fold-down");
        Console.WriteLine();

        var keepRunning = true;
        while (keepRunning)
        {
            PrintMenu();
            Console.Write("> ");
            var cmd = Console.ReadLine()?.Trim();

            try
            {
                switch (cmd)
                {
                    case "1":
                        ListDevices();
                        break;
                    case "2":
                        SelectDevice();
                        break;
                    case "3":
                        StartInterceptor();
                        break;
                    case "4":
                        StopInterceptor();
                        break;
                    case "5":
                        ConfigureEq();
                        break;
                    case "6":
                        ConfigureLayout();
                        break;
                    case "7":
                        BackupSystemSounds();
                        break;
                    case "8":
                        ReplaceSystemSounds();
                        break;
                    case "9":
                        RestoreSystemSounds();
                        break;
                    case "0":
                        keepRunning = false;
                        break;
                    default:
                        Console.WriteLine("Unknown command.");
                        break;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }

            await Task.Delay(100);
            Console.WriteLine();
        }

        _interceptor.Dispose();
    }

    private void PrintMenu()
    {
        Console.WriteLine("1) List output devices");
        Console.WriteLine("2) Select output device");
        Console.WriteLine("3) Start pre-speaker interception");
        Console.WriteLine("4) Stop interception");
        Console.WriteLine("5) Load EQ preset (10-band)");
        Console.WriteLine("6) Set layout (stereo/5.1/7.1/7.2)");
        Console.WriteLine("7) Backup current Windows system sounds");
        Console.WriteLine("8) Apply replacement system sound profile folder");
        Console.WriteLine("9) Restore system sounds from backup");
        Console.WriteLine("0) Exit");
    }

    private void ListDevices()
    {
        var devices = _deviceManager.GetRenderDevices();
        for (var i = 0; i < devices.Count; i++)
        {
            var selected = devices[i].ID.Equals(_state.SelectedOutputDeviceId, StringComparison.OrdinalIgnoreCase) ? "*" : " ";
            Console.WriteLine($"[{i}] {selected} {devices[i].FriendlyName}");
        }
    }

    private void SelectDevice()
    {
        var devices = _deviceManager.GetRenderDevices();
        ListDevices();
        Console.Write("Device index: ");
        if (!int.TryParse(Console.ReadLine(), out var index) || index < 0 || index >= devices.Count)
        {
            Console.WriteLine("Invalid device index.");
            return;
        }

        _state.SelectedOutputDeviceId = devices[index].ID;
        Console.WriteLine($"Selected: {devices[index].FriendlyName}");

        if (_interceptor.IsRunning)
        {
            Console.WriteLine("Hot-switching output device.");
            _interceptor.Stop();
            _interceptor.Start(_state);
        }
    }

    private void StartInterceptor()
    {
        _interceptor.Start(_state);
        _state.IsRunning = true;
        Console.WriteLine("Interception running.");
    }

    private void StopInterceptor()
    {
        _interceptor.Stop();
        _state.IsRunning = false;
        Console.WriteLine("Interception stopped.");
    }

    private void ConfigureEq()
    {
        Console.WriteLine("Presets: flat, bass, vocal, bright");
        Console.Write("Preset: ");
        var preset = (Console.ReadLine() ?? string.Empty).Trim().ToLowerInvariant();

        var values = preset switch
        {
            "bass" => new[] { 5f, 4f, 3f, 2f, 1f, 0f, -1f, -1f, -1f, -2f },
            "vocal" => new[] { -2f, -1f, 0f, 1f, 2f, 3f, 3f, 2f, 1f, 0f },
            "bright" => new[] { -2f, -2f, -1f, 0f, 0f, 1f, 2f, 3f, 4f, 4f },
            _ => new[] { 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f }
        };

        for (var i = 0; i < _state.EqBands.Count; i++)
        {
            _state.EqBands[i].GainDb = values[i];
        }

        Console.WriteLine("EQ updated.");

        if (_interceptor.IsRunning)
        {
            Console.WriteLine("Applying EQ by restarting interceptor.");
            _interceptor.Stop();
            _interceptor.Start(_state);
        }
    }

    private void ConfigureLayout()
    {
        Console.Write("Layout (2, 6, 8, 9): ");
        if (!int.TryParse(Console.ReadLine(), out var channels))
        {
            Console.WriteLine("Invalid layout.");
            return;
        }

        _state.Layout = channels switch
        {
            2 => OutputLayout.Stereo,
            6 => OutputLayout.Surround51,
            8 => OutputLayout.Surround71,
            9 => OutputLayout.Surround72,
            _ => _state.Layout
        };

        Console.WriteLine($"Layout set to {_state.Layout} ({(int)_state.Layout} channels model).");

        if (_interceptor.IsRunning)
        {
            Console.WriteLine("Applying layout by restarting interceptor.");
            _interceptor.Stop();
            _interceptor.Start(_state);
        }
    }

    private void BackupSystemSounds()
    {
        var path = _rollback.BackupSystemSounds();
        Console.WriteLine($"Backup created: {path}");
    }

    private void ReplaceSystemSounds()
    {
        Console.WriteLine("Provide folder containing wav files named: OpenApp.wav, CloseApp.wav, Notification.wav, Info.wav, Warning.wav, Error.wav, Mail.wav, Reminder.wav");
        Console.Write("Profile folder: ");
        var folder = (Console.ReadLine() ?? string.Empty).Trim('"', ' ');

        if (!Directory.Exists(folder))
        {
            Console.WriteLine("Folder not found.");
            return;
        }

        _systemSoundManager.ApplyProfileFolder(folder);
        Console.WriteLine("System sound profile applied to HKCU AppEvents.");
    }

    private void RestoreSystemSounds()
    {
        _rollback.RestoreSystemSounds();
        Console.WriteLine("System sounds restored from backup.");
    }
}
