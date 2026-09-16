#include "core/AudioFrame.h"
#include "dsp/TenBandEqualizer.h"
#include "intercept/PreSpeakerInterceptor.h"
#include "routing/SpeakerSelector.h"
#include "system/SystemSoundReplacementManager.h"
#include "ui/ConsoleControlPanel.h"
#include "upmix/StereoTo72Upmixer.h"
#include "../stubs/apo-driver/BossForgeApoStub.h"

#include <filesystem>
#include <fstream>
#include <iostream>

using namespace bossforge;

static AudioBuffer BuildDemoBuffer() {
    AudioBuffer buffer;
    buffer.sampleRateHz = 48000;

    for (int i = 0; i < 8; ++i) {
        const float l = 0.2f + (0.05f * static_cast<float>(i));
        const float r = 0.18f + (0.04f * static_cast<float>(i));
        buffer.stereoFrames.push_back(AudioFrame{l, r});
    }

    return buffer;
}

static void EnsureDummyWav(const std::filesystem::path& path) {
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);

    if (!std::filesystem::exists(path)) {
        std::ofstream out(path, std::ios::binary);
        out << "RIFF....WAVEfmt ";
    }
}

int main() {
    std::cout << "BossForge Sound System Showdown Prototype\n";

    BossForgeApoStub apo;
    std::cout << "APO Stub: " << apo.Name() << " [" << apo.Category() << "]\n";

    PreSpeakerInterceptor interceptor;
    TenBandEqualizer eq;
    eq.SetBandGainDb(0, 2.0f);
    eq.SetBandGainDb(1, 1.5f);
    eq.SetBandGainDb(8, 1.0f);

    interceptor.RegisterHook([&eq](AudioBuffer& buffer) {
        eq.Process(buffer);
    });

    SpeakerSelector selector;
    selector.SetDevices({
        {"dev_speakers_room_a", "BossForge Arena 7.2", true},
        {"dev_headphones_mix", "BossForge Tactical Headset", false},
        {"dev_hdmi_stage", "BossForge HDMI Stage", false},
    });

    ConsoleControlPanel::PrintDeviceList(selector);
    selector.SelectById("dev_headphones_mix");
    ConsoleControlPanel::PrintDeviceList(selector);

    auto buffer = BuildDemoBuffer();
    auto telemetry = interceptor.Intercept(buffer);
    std::cout << "Intercepted frames: " << telemetry.framesIntercepted << "\n";

    StereoTo72Upmixer upmixer;
    auto upmixed = upmixer.Process(buffer);
    std::cout << "Upmixed frame count: " << upmixed.size() << "\n";

    const auto workspace = std::filesystem::current_path();
    SystemSoundReplacementManager soundManager(workspace);

    const auto openApp = workspace / "runtime" / "windows-events" / "open_app.wav";
    const auto closeApp = workspace / "runtime" / "windows-events" / "close_app.wav";
    const auto customOpen = workspace / "runtime" / "custom" / "bossforge_open_app.wav";
    const auto customClose = workspace / "runtime" / "custom" / "bossforge_close_app.wav";

    EnsureDummyWav(openApp);
    EnsureDummyWav(closeApp);
    EnsureDummyWav(customOpen);
    EnsureDummyWav(customClose);

    soundManager.RegisterSystemEvent("open_app", openApp);
    soundManager.RegisterSystemEvent("close_app", closeApp);
    soundManager.BackupAll();

    const bool swappedOpen = soundManager.ReplaceEventSound("open_app", customOpen);
    const bool swappedClose = soundManager.ReplaceEventSound("close_app", customClose);

    std::cout << "System sound swap open_app: " << (swappedOpen ? "ok" : "failed") << "\n";
    std::cout << "System sound swap close_app: " << (swappedClose ? "ok" : "failed") << "\n";

    soundManager.RestoreDefaults();
    std::cout << "Restored defaults from: " << soundManager.BackupRoot().string() << "\n";

    std::cout << "Prototype run complete.\n";
    return 0;
}
