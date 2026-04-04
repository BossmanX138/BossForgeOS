#include "PipelineEngine.h"

#include <iomanip>
#include <iostream>

using bossforge::Frame72;
using bossforge::PipelineEngine;

namespace {

void printFrame(const Frame72& f) {
    std::cout << std::fixed << std::setprecision(4)
              << "FL=" << f.frontLeft << " FR=" << f.frontRight
              << " C=" << f.center
              << " LFE1=" << f.lfe1
              << " SL=" << f.sideLeft << " SR=" << f.sideRight
              << " RL=" << f.rearLeft << " RR=" << f.rearRight
              << " LFE2=" << f.lfe2 << '\n';
}

} // namespace

int main() {
    PipelineEngine engine;

    engine.equalizer().setBandGainDb(0, 2.5);
    engine.equalizer().setBandGainDb(4, -1.0);
    engine.equalizer().setBandGainDb(8, 3.0);

    const bool switched = engine.devices().selectDeviceById("endpoint-hdmi");
    std::cout << "Device switch: " << (switched ? "ok" : "failed") << '\n';

    auto selected = engine.devices().currentDevice();
    if (selected.has_value()) {
        std::cout << "Current output: " << selected->displayName << '\n';
    }

    const Frame72 frame = engine.processStereo(0.42f, 0.31f);
    printFrame(frame);

    return 0;
}
