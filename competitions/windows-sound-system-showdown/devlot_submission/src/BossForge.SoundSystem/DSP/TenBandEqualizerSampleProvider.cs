using BossForge.SoundSystem.Core;
using NAudio.Wave;

namespace BossForge.SoundSystem.DSP;

public sealed class TenBandEqualizerSampleProvider : ISampleProvider
{
    private readonly ISampleProvider _source;
    private readonly List<EqBand> _bands;
    private readonly BiquadFilter[][] _filters;

    public TenBandEqualizerSampleProvider(ISampleProvider source, IReadOnlyList<EqBand> bands)
    {
        _source = source;
        _bands = bands.Select(b => new EqBand { FrequencyHz = b.FrequencyHz, GainDb = b.GainDb, Q = b.Q }).ToList();

        _filters = new BiquadFilter[source.WaveFormat.Channels][];
        for (var c = 0; c < source.WaveFormat.Channels; c++)
        {
            _filters[c] = _bands
                .Select(b => BiquadFilter.Peak(source.WaveFormat.SampleRate, b.FrequencyHz, b.Q, b.GainDb))
                .ToArray();
        }
    }

    public WaveFormat WaveFormat => _source.WaveFormat;

    public int Read(float[] buffer, int offset, int count)
    {
        var read = _source.Read(buffer, offset, count);
        var channels = WaveFormat.Channels;

        for (var n = 0; n < read; n++)
        {
            var channel = n % channels;
            var index = offset + n;
            var sample = buffer[index];

            foreach (var filter in _filters[channel])
            {
                sample = filter.Process(sample);
            }

            buffer[index] = sample;
        }

        return read;
    }
}
