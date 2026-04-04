#include "PipelineEngine.h"

namespace bossforge {

PipelineEngine::PipelineEngine() = default;

DeviceManager& PipelineEngine::devices() {
    return devices_;
}

TenBandEqualizer& PipelineEngine::equalizer() {
    return eq_;
}

Frame72 PipelineEngine::processStereo(float left, float right) {
    if (!bypass_) {
        eq_.process(left, right);
    }

    return upmixer_.process(StereoFrame {left, right});
}

void PipelineEngine::setBypass(bool enabled) {
    bypass_ = enabled;
}

bool PipelineEngine::isBypassed() const {
    return bypass_;
}

} // namespace bossforge
