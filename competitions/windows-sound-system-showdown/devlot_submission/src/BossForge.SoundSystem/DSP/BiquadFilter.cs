namespace BossForge.SoundSystem.DSP;

public sealed class BiquadFilter
{
    private readonly float _a0;
    private readonly float _a1;
    private readonly float _a2;
    private readonly float _b1;
    private readonly float _b2;

    private float _x1;
    private float _x2;
    private float _y1;
    private float _y2;

    private BiquadFilter(float a0, float a1, float a2, float b1, float b2)
    {
        _a0 = a0;
        _a1 = a1;
        _a2 = a2;
        _b1 = b1;
        _b2 = b2;
    }

    public static BiquadFilter Peak(float sampleRate, float frequency, float q, float gainDb)
    {
        var a = MathF.Pow(10f, gainDb / 40f);
        var w0 = 2f * MathF.PI * frequency / sampleRate;
        var alpha = MathF.Sin(w0) / (2f * q);
        var cosW0 = MathF.Cos(w0);

        var b0 = 1f + alpha * a;
        var b1 = -2f * cosW0;
        var b2 = 1f - alpha * a;
        var a0 = 1f + alpha / a;
        var a1 = -2f * cosW0;
        var a2 = 1f - alpha / a;

        return new BiquadFilter(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0);
    }

    public float Process(float sample)
    {
        var y = _a0 * sample + _a1 * _x1 + _a2 * _x2 - _b1 * _y1 - _b2 * _y2;

        _x2 = _x1;
        _x1 = sample;
        _y2 = _y1;
        _y1 = y;

        return y;
    }
}
