#include "SpeakerSelector.h"

namespace bossforge {

void SpeakerSelector::SetDevices(std::vector<SpeakerDevice> devices) {
    devices_ = std::move(devices);
    for (const auto& device : devices_) {
        if (device.isDefault) {
            currentId_ = device.id;
            break;
        }
    }

    if (currentId_.empty() && !devices_.empty()) {
        currentId_ = devices_[0].id;
    }
}

const std::vector<SpeakerDevice>& SpeakerSelector::Devices() const {
    return devices_;
}

bool SpeakerSelector::SelectById(const std::string& id) {
    for (const auto& device : devices_) {
        if (device.id == id) {
            currentId_ = id;
            return true;
        }
    }
    return false;
}

const SpeakerDevice* SpeakerSelector::CurrentDevice() const {
    for (const auto& device : devices_) {
        if (device.id == currentId_) {
            return &device;
        }
    }
    return nullptr;
}

} // namespace bossforge
