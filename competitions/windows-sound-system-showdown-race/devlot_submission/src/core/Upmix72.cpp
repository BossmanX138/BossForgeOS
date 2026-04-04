#include "Upmix72.h"

namespace bossforge {

Frame72 StereoTo72Upmixer::process(const StereoFrame& in) const {
    const float mid = (in.left + in.right) * 0.5f;
    const float side = (in.left - in.right) * 0.5f;

    Frame72 out;
    out.frontLeft = in.left;
    out.frontRight = in.right;

    // Center carries dialog and anchored content derived from stereo mid.
    out.center = mid * 0.80f;

    // Side/rear channels preserve width and motion cues.
    out.sideLeft = (in.left * 0.55f) + (side * 0.30f);
    out.sideRight = (in.right * 0.55f) - (side * 0.30f);
    out.rearLeft = (in.left * 0.30f) + (side * 0.55f);
    out.rearRight = (in.right * 0.30f) - (side * 0.55f);

    // Dual LFE channels share summed bass energy.
    out.lfe1 = mid * 0.22f;
    out.lfe2 = mid * 0.22f;

    return out;
}

} // namespace bossforge
