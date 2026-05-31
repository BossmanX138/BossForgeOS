#pragma once

#include "../core/AudioFrame.h"

#include <array>
#include <cstddef>

namespace bossforge {

class TenBandEqualizer {
public:
    static constexpr std::size_t kBands = 10;

    TenBandEqualizer();

    void SetBandGainDb(std::size_t band, float gainDb);
    float GetBandGainDb(std::size_t band) const;
    void Process(AudioBuffer& buffer) const;

private:
    std::array<float, kBands> gainsDb_;

    static float DbToLinear(float db);
};

} // namespace bossforge
