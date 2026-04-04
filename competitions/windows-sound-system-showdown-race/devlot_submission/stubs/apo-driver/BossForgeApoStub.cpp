#include <array>
#include <cstdint>
#include <span>

namespace bossforge {

// This stub models a pre-speaker Audio Processing Object (APO) stage.
// In production, this class would be exposed through COM and registered as an SFX/MFX APO.
class BossForgePreSpeakerApo {
public:
    void setEqGains(const std::array<float, 10>& gainsDb) {
        gainsDb_ = gainsDb;
    }

    void enableUpmix(bool enabled) {
        upmixEnabled_ = enabled;
    }

    // Intercepts PCM frames before endpoint rendering and applies DSP hooks.
    void processInterleavedStereo(std::span<float> pcmInterleavedLR) {
        for (std::size_t i = 0; i + 1 < pcmInterleavedLR.size(); i += 2) {
            float left = pcmInterleavedLR[i];
            float right = pcmInterleavedLR[i + 1];

            applyEq(left, right);

            if (upmixEnabled_) {
                // For the stub we fold to stereo-safe output.
                const float center = (left + right) * 0.5f * 0.80f;
                left = (left * 0.90f) + (center * 0.10f);
                right = (right * 0.90f) + (center * 0.10f);
            }

            pcmInterleavedLR[i] = left;
            pcmInterleavedLR[i + 1] = right;
        }
    }

private:
    void applyEq(float& left, float& right) const {
        // Lightweight gain stack to represent per-band shaping in the stub.
        float aggregate = 1.0f;
        for (float g : gainsDb_) {
            aggregate += (g * 0.0025f);
        }

        left *= aggregate;
        right *= aggregate;
    }

    std::array<float, 10> gainsDb_ {0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    bool upmixEnabled_ {true};
};

} // namespace bossforge
