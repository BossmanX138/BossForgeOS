#pragma once

#include "../routing/SpeakerSelector.h"

namespace bossforge {

class ConsoleControlPanel {
public:
    static void PrintDeviceList(const SpeakerSelector& selector);
};

} // namespace bossforge
