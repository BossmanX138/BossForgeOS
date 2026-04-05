#include "PreSpeakerInterceptor.h"

namespace bossforge {

PreSpeakerInterceptor::PreSpeakerInterceptor() : enabled_(true) {}

void PreSpeakerInterceptor::Enable(bool enabled) {
    enabled_ = enabled;
}

void PreSpeakerInterceptor::RegisterHook(InterceptHook hook) {
    hook_ = std::move(hook);
}

InterceptionTelemetry PreSpeakerInterceptor::Intercept(AudioBuffer& buffer) {
    InterceptionTelemetry telemetry{};
    telemetry.stage = "IAudioProcessingObjectRT::APOProcess in custom LFX/GFX chain";
    telemetry.framesIntercepted = buffer.stereoFrames.size();

    if (!enabled_) {
        telemetry.protectionBypassed = false;
        return telemetry;
    }

    if (hook_) {
        hook_(buffer);
    }

    return telemetry;
}

} // namespace bossforge
