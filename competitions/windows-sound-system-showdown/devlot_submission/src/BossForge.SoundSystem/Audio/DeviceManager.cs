using NAudio.CoreAudioApi;

namespace BossForge.SoundSystem.Audio;

public sealed class DeviceManager
{
    private readonly MMDeviceEnumerator _enumerator = new();

    public IReadOnlyList<MMDevice> GetRenderDevices()
    {
        return _enumerator.EnumerateAudioEndPoints(DataFlow.Render, DeviceState.Active).ToList();
    }

    public MMDevice GetDefaultRenderDevice()
    {
        return _enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia);
    }

    public MMDevice? GetById(string? id)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return null;
        }

        return GetRenderDevices().FirstOrDefault(d => d.ID.Equals(id, StringComparison.OrdinalIgnoreCase));
    }
}
