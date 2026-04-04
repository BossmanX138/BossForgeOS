#include "Equalizer.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace bossforge {
namespace {

constexpr double kPi = 3.14159265358979323846;

} // namespace

float TenBandEqualizer::Biquad::processLeft(float input) {
    const double out = b0 * input + z1L;
    z1L = b1 * input - a1 * out + z2L;
    z2L = b2 * input - a2 * out;
    return static_cast<float>(out);
}

float TenBandEqualizer::Biquad::processRight(float input) {
    const double out = b0 * input + z1R;
    z1R = b1 * input - a1 * out + z2R;
    z2R = b2 * input - a2 * out;
    return static_cast<float>(out);
}

TenBandEqualizer::TenBandEqualizer(double sampleRate)
    : sampleRate_(sampleRate),
      centerHz_ {31.25, 62.5, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0},
      gainsDb_ {0, 0, 0, 0, 0, 0, 0, 0, 0, 0} {
    for (std::size_t i = 0; i < kBandCount; ++i) {
        rebuildBand(i);
    }
}

void TenBandEqualizer::setBandGainDb(std::size_t bandIndex, double gainDb) {
    if (bandIndex >= kBandCount) {
        throw std::out_of_range("bandIndex out of range");
    }
    gainsDb_[bandIndex] = std::clamp(gainDb, -18.0, 18.0);
    rebuildBand(bandIndex);
}

double TenBandEqualizer::getBandGainDb(std::size_t bandIndex) const {
    if (bandIndex >= kBandCount) {
        throw std::out_of_range("bandIndex out of range");
    }
    return gainsDb_[bandIndex];
}

void TenBandEqualizer::process(float& left, float& right) {
    float l = left;
    float r = right;

    for (auto& filter : filters_) {
        l = filter.processLeft(l);
        r = filter.processRight(r);
    }

    left = l;
    right = r;
}

void TenBandEqualizer::rebuildBand(std::size_t bandIndex) {
    const double gain = std::pow(10.0, gainsDb_[bandIndex] / 40.0);
    const double omega = 2.0 * kPi * centerHz_[bandIndex] / sampleRate_;
    const double sn = std::sin(omega);
    const double cs = std::cos(omega);
    const double q = 1.1;
    const double alpha = sn / (2.0 * q);

    const double b0 = 1.0 + alpha * gain;
    const double b1 = -2.0 * cs;
    const double b2 = 1.0 - alpha * gain;
    const double a0 = 1.0 + alpha / gain;
    const double a1 = -2.0 * cs;
    const double a2 = 1.0 - alpha / gain;

    auto& f = filters_[bandIndex];
    f.b0 = b0 / a0;
    f.b1 = b1 / a0;
    f.b2 = b2 / a0;
    f.a1 = a1 / a0;
    f.a2 = a2 / a0;
}

} // namespace bossforge
