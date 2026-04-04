namespace BossForge.SoundSystem.Audio;

public sealed class SafetyRollbackManager
{
    private readonly SystemSoundManager _soundManager;
    private readonly string _backupPath;

    public SafetyRollbackManager(SystemSoundManager soundManager)
    {
        _soundManager = soundManager;
        var appData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        _backupPath = Path.Combine(appData, "BossForgeSoundSystem", "system-sound-backup.json");
    }

    public string BackupSystemSounds()
    {
        return _soundManager.BackupCurrent(_backupPath);
    }

    public void RestoreSystemSounds()
    {
        if (!File.Exists(_backupPath))
        {
            throw new FileNotFoundException("No backup was found. Create a backup first.", _backupPath);
        }

        _soundManager.RestoreFromBackup(_backupPath);
    }

    public string BackupPath => _backupPath;
}
