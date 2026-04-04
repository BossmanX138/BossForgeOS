using NAudio.Wave;

namespace BossForge.SoundSystem.Audio;

public sealed class ChannelFoldDownSampleProvider : ISampleProvider
{
    private readonly ISampleProvider _source;
    private readonly int _sourceChannels;
    private readonly int _targetChannels;
    private float[] _scratch = Array.Empty<float>();

    public ChannelFoldDownSampleProvider(ISampleProvider source, int targetChannels)
    {
        _source = source;
        _sourceChannels = source.WaveFormat.Channels;
        _targetChannels = targetChannels;
        WaveFormat = WaveFormat.CreateIeeeFloatWaveFormat(source.WaveFormat.SampleRate, targetChannels);
    }

    public WaveFormat WaveFormat { get; }

    public int Read(float[] buffer, int offset, int count)
    {
        var frames = count / _targetChannels;
        var needed = frames * _sourceChannels;

        if (_scratch.Length < needed)
        {
            _scratch = new float[needed];
        }

        var read = _source.Read(_scratch, 0, needed);
        var framesRead = read / _sourceChannels;

        var outIndex = offset;
        for (var frame = 0; frame < framesRead; frame++)
        {
            var start = frame * _sourceChannels;
            var left = _scratch[start];
            var right = _sourceChannels > 1 ? _scratch[start + 1] : left;

            // Merge center, surrounds, and LFE energy back into the front pair for commodity devices.
            if (_sourceChannels > 2)
            {
                left += _scratch[start + 2] * 0.35f;
                right += _scratch[start + 2] * 0.35f;
            }
            if (_sourceChannels > 3)
            {
                left += _scratch[start + 3] * 0.30f;
            }
            if (_sourceChannels > 4)
            {
                right += _scratch[start + 4] * 0.30f;
            }
            if (_sourceChannels > 5)
            {
                left += _scratch[start + 5] * 0.22f;
            }
            if (_sourceChannels > 6)
            {
                right += _scratch[start + 6] * 0.22f;
            }
            if (_sourceChannels > 7)
            {
                left += _scratch[start + 7] * 0.20f;
                right += _scratch[start + 7] * 0.20f;
            }
            if (_sourceChannels > 8)
            {
                left += _scratch[start + 8] * 0.12f;
                right += _scratch[start + 8] * 0.12f;
            }

            if (_targetChannels == 1)
            {
                buffer[outIndex++] = (left + right) * 0.5f;
                continue;
            }

            buffer[outIndex++] = left;
            buffer[outIndex++] = right;

            for (var c = 2; c < _targetChannels; c++)
            {
                buffer[outIndex++] = 0f;
            }
        }

        return framesRead * _targetChannels;
    }
}
