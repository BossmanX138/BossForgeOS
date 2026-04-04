#pragma once

#include "../safety/RollbackSafetyManager.h"

#include <filesystem>
#include <string>
#include <unordered_map>

namespace bossforge {

class SystemSoundReplacementManager {
public:
    explicit SystemSoundReplacementManager(std::filesystem::path workspaceRoot);

    void RegisterSystemEvent(const std::string& eventName, std::filesystem::path currentWavPath);
    bool BackupAll();
    bool ReplaceEventSound(const std::string& eventName, const std::filesystem::path& replacementWav);
    bool RestoreDefaults();

    std::filesystem::path BackupRoot() const;

private:
    std::filesystem::path workspaceRoot_;
    std::filesystem::path backupRoot_;
    std::unordered_map<std::string, std::filesystem::path> eventToCurrentWav_;
    std::unordered_map<std::string, std::filesystem::path> eventToBackupWav_;
    RollbackSafetyManager rollback_;

    static bool EnsureDirectory(const std::filesystem::path& path);
};

} // namespace bossforge
