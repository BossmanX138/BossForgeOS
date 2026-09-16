#pragma once

#include "../core/AudioFrame.h"

#include <functional>
#include <string>

namespace bossforge {

struct InterceptionTelemetry {
    std::string stage;
    std::size_t framesIntercepted = 0;
    bool protectionBypassed = false;
};

class PreSpeakerInterceptor {
public:
    using InterceptHook = std::function<void(AudioBuffer&)>;

    PreSpeakerInterceptor();

    void Enable(bool enabled);
    void RegisterHook(InterceptHook hook);
    InterceptionTelemetry Intercept(AudioBuffer& buffer);

private:
    bool enabled_;
    InterceptHook hook_;
};

} // namespace bossforge
