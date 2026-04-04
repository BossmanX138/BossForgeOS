#pragma once

#include <array>
#include <cstddef>

namespace bossforge {

class TenBandEqualizer {
public:
    TenBandEqualizer(double sampleRate = 48000.0);

    void setBandGainDb(std::size_t bandIndex, double gainDb);
    double getBandGainDb(std::size_t bandIndex) const;

    // Process one stereo frame in place.
    void process(float& left, float& right);

private:
    struct Biquad {
        double b0 {1.0};
        double b1 {0.0};
        double b2 {0.0};
        double a1 {0.0};
        double a2 {0.0};

        double z1L {0.0};
        double z2L {0.0};
        double z1R {0.0};
        double z2R {0.0};

        float processLeft(float input);
        float processRight(float input);
    };

    static constexpr std::size_t kBandCount = 10;

    void rebuildBand(std::size_t bandIndex);

    double sampleRate_;
    std::array<double, kBandCount> centerHz_;
    std::array<double, kBandCount> gainsDb_;
    std::array<Biquad, kBandCount> filters_;
};

} // namespace bossforge
