#include "StereoTo72Upmixer.h"

namespace bossforge {

std::vector<UpmixedFrame72> StereoTo72Upmixer::Process(const AudioBuffer& stereo) const {
    std::vector<UpmixedFrame72> out;
    out.reserve(stereo.stereoFrames.size());

    for (const auto& frame : stereo.stereoFrames) {
        const float mono = (frame.left + frame.right) * 0.5f;
        const float side = (frame.left - frame.right) * 0.5f;

        UpmixedFrame72 routed{};
        routed.channels[static_cast<std::size_t>(OutputChannel::FrontLeft)] = frame.left;
        routed.channels[static_cast<std::size_t>(OutputChannel::FrontRight)] = frame.right;
        routed.channels[static_cast<std::size_t>(OutputChannel::Center)] = mono * 0.8f;
        routed.channels[static_cast<std::size_t>(OutputChannel::Lfe1)] = mono * 0.35f;
        routed.channels[static_cast<std::size_t>(OutputChannel::SideLeft)] = (frame.left * 0.7f) + (side * 0.2f);
        routed.channels[static_cast<std::size_t>(OutputChannel::SideRight)] = (frame.right * 0.7f) - (side * 0.2f);
        routed.channels[static_cast<std::size_t>(OutputChannel::RearLeft)] = (frame.left * 0.45f) + (mono * 0.1f);
        routed.channels[static_cast<std::size_t>(OutputChannel::RearRight)] = (frame.right * 0.45f) + (mono * 0.1f);
        routed.channels[static_cast<std::size_t>(OutputChannel::Lfe2)] = mono * 0.25f;

        out.push_back(routed);
    }

    return out;
}

} // namespace bossforge
