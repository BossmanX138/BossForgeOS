#include "TenBandEqualizer.h"

#include <algorithm>
#include <cmath>

namespace bossforge {

TenBandEqualizer::TenBandEqualizer() {
    gainsDb_.fill(0.0f);
}

void TenBandEqualizer::SetBandGainDb(std::size_t band, float gainDb) {
    if (band >= kBands) {
        return;
    }
    gainsDb_[band] = std::clamp(gainDb, -12.0f, 12.0f);
}

float TenBandEqualizer::GetBandGainDb(std::size_t band) const {
    if (band >= kBands) {
        return 0.0f;
    }
    return gainsDb_[band];
}

float TenBandEqualizer::DbToLinear(float db) {
    return std::pow(10.0f, db / 20.0f);
}

void TenBandEqualizer::Process(AudioBuffer& buffer) const {
    // Lightweight sandbox DSP: average gain approximates full 10-band impact.
    float averageDb = 0.0f;
    for (float gain : gainsDb_) {
        averageDb += gain;
    }
    averageDb /= static_cast<float>(kBands);

    const float scale = DbToLinear(averageDb);
    for (auto& frame : buffer.stereoFrames) {
        frame.left *= scale;
        frame.right *= scale;
    }
}

} // namespace bossforge
