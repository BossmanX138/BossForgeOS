using System.Text.Json;
using Microsoft.Win32;

namespace BossForge.SoundSystem.Audio;

public sealed class SystemSoundManager
{
    private const string AppEventsRoot = "AppEvents\\Schemes\\Apps\\.Default";

    private static readonly Dictionary<string, string> EventMap = new(StringComparer.OrdinalIgnoreCase)
    {
        ["OpenApp"] = "Open",
        ["CloseApp"] = "Close",
        ["Notification"] = ".Default",
        ["Info"] = "SystemAsterisk",
        ["Warning"] = "SystemExclamation",
        ["Error"] = "SystemHand",
        ["Mail"] = "MailBeep",
        ["Reminder"] = "Notification.Reminder"
    };

    public string BackupCurrent(string backupFilePath)
    {
        var snapshot = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);

        foreach (var eventName in EventMap.Values)
        {
            var keyPath = $"{AppEventsRoot}\\{eventName}\\.Current";
            using var key = Registry.CurrentUser.OpenSubKey(keyPath, false);
            snapshot[eventName] = key?.GetValue(null)?.ToString();
        }

        Directory.CreateDirectory(Path.GetDirectoryName(backupFilePath)!);
        var json = JsonSerializer.Serialize(snapshot, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(backupFilePath, json);

        return backupFilePath;
    }

    public void ApplyProfileFolder(string profileFolder)
    {
        foreach (var mapping in EventMap)
        {
            var waveFile = Path.Combine(profileFolder, $"{mapping.Key}.wav");
            if (!File.Exists(waveFile))
            {
                continue;
            }

            var keyPath = $"{AppEventsRoot}\\{mapping.Value}\\.Current";
            using var key = Registry.CurrentUser.CreateSubKey(keyPath, true);
            key?.SetValue(null, waveFile, RegistryValueKind.String);
        }
    }

    public void RestoreFromBackup(string backupFilePath)
    {
        var payload = File.ReadAllText(backupFilePath);
        var snapshot = JsonSerializer.Deserialize<Dictionary<string, string?>>(payload)
            ?? throw new InvalidOperationException("Invalid backup file.");

        foreach (var pair in snapshot)
        {
            var keyPath = $"{AppEventsRoot}\\{pair.Key}\\.Current";
            using var key = Registry.CurrentUser.CreateSubKey(keyPath, true);
            key?.SetValue(null, pair.Value ?? string.Empty, RegistryValueKind.String);
        }
    }

    public IReadOnlyDictionary<string, string> SupportedEvents() => EventMap;
}
