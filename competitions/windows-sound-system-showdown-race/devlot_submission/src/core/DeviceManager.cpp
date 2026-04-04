#include "DeviceManager.h"

namespace bossforge {

DeviceManager::DeviceManager()
    : devices_ {
          {"endpoint-default", "Default Speakers (WASAPI Shared)", true},
          {"endpoint-headset", "BossForge USB Headset", false},
          {"endpoint-hdmi", "HDMI AVR 7.2", false}} ,
      selectedId_("endpoint-default") {}

std::vector<AudioDevice> DeviceManager::listOutputDevices() const {
    return devices_;
}

std::optional<AudioDevice> DeviceManager::currentDevice() const {
    for (const auto& d : devices_) {
        if (d.id == selectedId_) {
            return d;
        }
    }
    return std::nullopt;
}

bool DeviceManager::selectDeviceById(const std::string& id) {
    for (const auto& d : devices_) {
        if (d.id == id) {
            selectedId_ = id;
            return true;
        }
    }
    return false;
}

} // namespace bossforge
