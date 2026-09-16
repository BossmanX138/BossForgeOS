#include "ConsoleControlPanel.h"

#include <iostream>

namespace bossforge {

void ConsoleControlPanel::PrintDeviceList(const SpeakerSelector& selector) {
    std::cout << "=== BossForge Output Devices ===\n";

    const auto* current = selector.CurrentDevice();
    for (const auto& device : selector.Devices()) {
        const bool active = current && current->id == device.id;
        std::cout << (active ? "[*] " : "[ ] ") << device.displayName << " (" << device.id << ")\n";
    }
}

} // namespace bossforge
