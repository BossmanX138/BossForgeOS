using BossForge.SoundSystem.Core;
using BossForge.SoundSystem.DSP;
using NAudio.CoreAudioApi;
using NAudio.Wave;

namespace BossForge.SoundSystem.Audio;

public sealed class PreSpeakerInterceptor : IDisposable
{
    private readonly DeviceManager _deviceManager;
    private WasapiLoopbackCapture? _capture;
    private WasapiOut? _renderer;
    private BufferedWaveProvider? _buffered;

    public PreSpeakerInterceptor(DeviceManager deviceManager)
    {
        _deviceManager = deviceManager;
    }

    public bool IsRunning { get; private set; }

    public void Start(AppState state)
    {
        if (IsRunning)
        {
            return;
        }

        var renderDevice = _deviceManager.GetById(state.SelectedOutputDeviceId) ?? _deviceManager.GetDefaultRenderDevice();

        _capture = new WasapiLoopbackCapture();
        _buffered = new BufferedWaveProvider(_capture.WaveFormat)
        {
            DiscardOnBufferOverflow = true,
            BufferDuration = TimeSpan.FromMilliseconds(350)
        };

        _capture.DataAvailable += (_, args) =>
        {
            _buffered?.AddSamples(args.Buffer, 0, args.BytesRecorded);
        };

        var source = _buffered.ToSampleProvider();
        ISampleProvider chain = source;

        if (chain.WaveFormat.Channels > 2)
        {
            chain = new StereoDownmixSampleProvider(chain);
        }

        chain = new TenBandEqualizerSampleProvider(chain, state.EqBands);

        var targetLayoutChannels = LayoutChannels.For(state.Layout);
        chain = new StereoTo72UpmixerSampleProvider(chain, targetLayoutChannels);

        var outputChannels = renderDevice.AudioClient.MixFormat.Channels;
        chain = new ChannelFoldDownSampleProvider(chain, outputChannels);

        _renderer = new WasapiOut(renderDevice, AudioClientShareMode.Shared, true, 40);
        _renderer.Init(chain.ToWaveProvider());

        _capture.StartRecording();
        _renderer.Play();
        IsRunning = true;
    }

    public void Stop()
    {
        if (!IsRunning)
        {
            return;
        }

        _renderer?.Stop();
        _capture?.StopRecording();

        _renderer?.Dispose();
        _capture?.Dispose();

        _renderer = null;
        _capture = null;
        _buffered = null;

        IsRunning = false;
    }

    public void Dispose()
    {
        Stop();
        GC.SuppressFinalize(this);
    }

    private sealed class StereoDownmixSampleProvider : ISampleProvider
    {
        private readonly ISampleProvider _source;
        private readonly int _sourceChannels;
        private float[] _scratch = Array.Empty<float>();

        public StereoDownmixSampleProvider(ISampleProvider source)
        {
            _source = source;
            _sourceChannels = source.WaveFormat.Channels;
            WaveFormat = WaveFormat.CreateIeeeFloatWaveFormat(source.WaveFormat.SampleRate, 2);
        }

        public WaveFormat WaveFormat { get; }

        public int Read(float[] buffer, int offset, int count)
        {
            var frames = count / 2;
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
                var l = _scratch[start];
                var r = _sourceChannels > 1 ? _scratch[start + 1] : l;

                for (var c = 2; c < _sourceChannels; c++)
                {
                    var bleed = _scratch[start + c] * 0.18f;
                    l += bleed;
                    r += bleed;
                }

                buffer[outIndex++] = l;
                buffer[outIndex++] = r;
            }

            return framesRead * 2;
        }
    }
}
