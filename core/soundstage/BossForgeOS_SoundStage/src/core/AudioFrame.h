#pragma once

#include <array>
#include <cstddef>
#include <string>
#include <vector>

namespace bossforge {

enum class OutputChannel {
    FrontLeft = 0,
    FrontRight,
    Center,
    Lfe1,
    SideLeft,
    SideRight,
    RearLeft,
    RearRight,
    Lfe2,
    Count
};

constexpr std::size_t kMaxOutputChannels = static_cast<std::size_t>(OutputChannel::Count);

struct AudioFrame {
    float left = 0.0f;
    float right = 0.0f;
};

struct UpmixedFrame72 {
    std::array<float, kMaxOutputChannels> channels{};
};

struct AudioBuffer {
    int sampleRateHz = 48000;
    std::vector<AudioFrame> stereoFrames;
};

inline std::string ChannelName(OutputChannel channel) {
    switch (channel) {
    case OutputChannel::FrontLeft:
        return "Front Left";
    case OutputChannel::FrontRight:
        return "Front Right";
    case OutputChannel::Center:
        return "Center";
    case OutputChannel::Lfe1:
        return "LFE 1";
    case OutputChannel::SideLeft:
        return "Side Left";
    case OutputChannel::SideRight:
        return "Side Right";
    case OutputChannel::RearLeft:
        return "Rear Left";
    case OutputChannel::RearRight:
        return "Rear Right";
    case OutputChannel::Lfe2:
        return "LFE 2";
    case OutputChannel::Count:
    default:
        return "Unknown";
    }
}

} // namespace bossforge
