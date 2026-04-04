using NAudio.Wave;

namespace BossForge.SoundSystem.DSP;

public sealed class StereoTo72UpmixerSampleProvider : ISampleProvider
{
    private readonly ISampleProvider _source;
    private readonly int _targetChannels;
    private float[] _readBuffer;

    public StereoTo72UpmixerSampleProvider(ISampleProvider source, int targetChannels)
    {
        if (source.WaveFormat.Channels != 2)
        {
            throw new ArgumentException("Stereo source required for upmix.");
        }

        if (targetChannels < 2)
        {
            throw new ArgumentException("Target channels must be 2 or greater.");
        }

        _source = source;
        _targetChannels = targetChannels;
        _readBuffer = new float[4096 * 2];

        WaveFormat = WaveFormat.CreateIeeeFloatWaveFormat(source.WaveFormat.SampleRate, targetChannels);
    }

    public WaveFormat WaveFormat { get; }

    public int Read(float[] buffer, int offset, int count)
    {
        var framesRequested = count / _targetChannels;
        var sourceSamplesRequested = framesRequested * 2;

        if (_readBuffer.Length < sourceSamplesRequested)
        {
            Array.Resize(ref _readBuffer, sourceSamplesRequested);
        }

        var read = _source.Read(_readBuffer, 0, sourceSamplesRequested);
        var framesRead = read / 2;
        var outIndex = offset;

        for (var frame = 0; frame < framesRead; frame++)
        {
            var l = _readBuffer[frame * 2];
            var r = _readBuffer[frame * 2 + 1];
            var mono = (l + r) * 0.5f;

            var channels = UpmixFrame(l, r, mono);
            for (var c = 0; c < _targetChannels; c++)
            {
                buffer[outIndex++] = channels[c];
            }
        }

        return framesRead * _targetChannels;
    }

    private float[] UpmixFrame(float l, float r, float mono)
    {
        var outChannels = new float[_targetChannels];

        // Routing model for 7.2: FL, FR, FC, BL, BR, SL, SR, LFE1, LFE2.
        outChannels[0] = l;
        if (_targetChannels > 1) outChannels[1] = r;
        if (_targetChannels > 2) outChannels[2] = mono * 0.75f;
        if (_targetChannels > 3) outChannels[3] = l * 0.55f;
        if (_targetChannels > 4) outChannels[4] = r * 0.55f;
        if (_targetChannels > 5) outChannels[5] = l * 0.40f;
        if (_targetChannels > 6) outChannels[6] = r * 0.40f;
        if (_targetChannels > 7) outChannels[7] = mono * 0.30f;
        if (_targetChannels > 8) outChannels[8] = mono * 0.18f;

        return outChannels;
    }
}
