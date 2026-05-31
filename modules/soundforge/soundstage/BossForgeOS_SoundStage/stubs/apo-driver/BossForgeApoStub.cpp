#include "BossForgeApoStub.h"

namespace bossforge {

std::string BossForgeApoStub::Name() const {
    return "BossForge APO Stub";
}

std::string BossForgeApoStub::Category() const {
    return "LFX/GFX Pre-Speaker Interceptor";
}

bool BossForgeApoStub::ValidateFormat(int sampleRate, int channels) const {
    if (sampleRate <= 0 || channels <= 0) {
        return false;
    }

    return sampleRate >= 44100 && channels <= 10;
}

} // namespace bossforge
