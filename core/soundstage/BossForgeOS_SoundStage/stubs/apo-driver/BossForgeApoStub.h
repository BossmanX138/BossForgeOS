#pragma once

#include <string>

namespace bossforge {

class BossForgeApoStub {
public:
    std::string Name() const;
    std::string Category() const;
    bool ValidateFormat(int sampleRate, int channels) const;
};

} // namespace bossforge
