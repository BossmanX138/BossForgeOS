#pragma once

#include "DeviceManager.h"
#include "Equalizer.h"
#include "Upmix72.h"

#include <cstddef>

namespace bossforge {

class PipelineEngine {
public:
    PipelineEngine();

    DeviceManager& devices();
    TenBandEqualizer& equalizer();

    Frame72 processStereo(float left, float right);
    void setBypass(bool enabled);
    bool isBypassed() const;

private:
    DeviceManager devices_;
    TenBandEqualizer eq_;
    StereoTo72Upmixer upmixer_;
    bool bypass_ {false};
};

} // namespace bossforge
