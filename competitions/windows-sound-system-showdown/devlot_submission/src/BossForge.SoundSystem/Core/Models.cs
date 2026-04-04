namespace BossForge.SoundSystem.Core;

public enum OutputLayout
{
    Stereo = 2,
    Surround51 = 6,
    Surround71 = 8,
    Surround72 = 9
}

public sealed class EqBand
{
    public required float FrequencyHz { get; init; }
    public float GainDb { get; set; }
    public float Q { get; set; } = 1.1f;
}

public sealed class AppState
{
    public List<EqBand> EqBands { get; } =
    [
        new() { FrequencyHz = 31.25f, GainDb = 0f },
        new() { FrequencyHz = 62.5f, GainDb = 0f },
        new() { FrequencyHz = 125f, GainDb = 0f },
        new() { FrequencyHz = 250f, GainDb = 0f },
        new() { FrequencyHz = 500f, GainDb = 0f },
        new() { FrequencyHz = 1000f, GainDb = 0f },
        new() { FrequencyHz = 2000f, GainDb = 0f },
        new() { FrequencyHz = 4000f, GainDb = 0f },
        new() { FrequencyHz = 8000f, GainDb = 0f },
        new() { FrequencyHz = 16000f, GainDb = 0f }
    ];

    public string? SelectedOutputDeviceId { get; set; }
    public OutputLayout Layout { get; set; } = OutputLayout.Surround72;
    public bool IsRunning { get; set; }

    public static AppState CreateDefault() => new();
}

public static class LayoutChannels
{
    public static int For(OutputLayout layout) => (int)layout;
}
