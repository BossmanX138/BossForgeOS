#pragma once

#include <optional>
#include <string>
#include <vector>

namespace bossforge {

struct AudioDevice {
    std::string id;
    std::string displayName;
    bool isDefault {false};
};

class DeviceManager {
public:
    DeviceManager();

    std::vector<AudioDevice> listOutputDevices() const;
    std::optional<AudioDevice> currentDevice() const;
    bool selectDeviceById(const std::string& id);

private:
    std::vector<AudioDevice> devices_;
    std::string selectedId_;
};

} // namespace bossforge
