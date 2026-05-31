#pragma once

#include <string>
#include <vector>

namespace bossforge {

struct SpeakerDevice {
    std::string id;
    std::string displayName;
    bool isDefault = false;
};

class SpeakerSelector {
public:
    void SetDevices(std::vector<SpeakerDevice> devices);
    const std::vector<SpeakerDevice>& Devices() const;

    bool SelectById(const std::string& id);
    const SpeakerDevice* CurrentDevice() const;

private:
    std::vector<SpeakerDevice> devices_;
    std::string currentId_;
};

} // namespace bossforge
