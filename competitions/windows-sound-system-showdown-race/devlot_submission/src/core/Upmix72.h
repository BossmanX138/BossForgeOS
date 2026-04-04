#pragma once

namespace bossforge {

struct StereoFrame {
    float left {0.0f};
    float right {0.0f};
};

struct Frame72 {
    float frontLeft {0.0f};
    float frontRight {0.0f};
    float center {0.0f};
    float lfe1 {0.0f};
    float sideLeft {0.0f};
    float sideRight {0.0f};
    float rearLeft {0.0f};
    float rearRight {0.0f};
    float lfe2 {0.0f};
};

class StereoTo72Upmixer {
public:
    Frame72 process(const StereoFrame& in) const;
};

} // namespace bossforge
