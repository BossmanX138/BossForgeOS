#pragma once

#include "../core/AudioFrame.h"

#include <vector>

namespace bossforge {

class StereoTo72Upmixer {
public:
    std::vector<UpmixedFrame72> Process(const AudioBuffer& stereo) const;
};

} // namespace bossforge
