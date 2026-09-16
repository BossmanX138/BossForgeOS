#include "SystemSoundReplacementManager.h"

#include <fstream>

namespace bossforge {

SystemSoundReplacementManager::SystemSoundReplacementManager(std::filesystem::path workspaceRoot)
    : workspaceRoot_(std::move(workspaceRoot)), backupRoot_(workspaceRoot_ / "runtime" / "sound_backups") {
}

void SystemSoundReplacementManager::RegisterSystemEvent(const std::string& eventName, std::filesystem::path currentWavPath) {
    eventToCurrentWav_[eventName] = std::move(currentWavPath);
}

bool SystemSoundReplacementManager::EnsureDirectory(const std::filesystem::path& path) {
    std::error_code ec;
    if (std::filesystem::exists(path, ec)) {
        return true;
    }
    return std::filesystem::create_directories(path, ec);
}

bool SystemSoundReplacementManager::BackupAll() {
    if (!EnsureDirectory(backupRoot_)) {
        return false;
    }

    for (const auto& [eventName, sourcePath] : eventToCurrentWav_) {
        if (!std::filesystem::exists(sourcePath)) {
            continue;
        }

        const auto backupFile = backupRoot_ / (eventName + ".wav");
        std::error_code ec;
        std::filesystem::copy_file(sourcePath, backupFile, std::filesystem::copy_options::overwrite_existing, ec);
        if (!ec) {
            eventToBackupWav_[eventName] = backupFile;
        }
    }

    return true;
}

bool SystemSoundReplacementManager::ReplaceEventSound(const std::string& eventName, const std::filesystem::path& replacementWav) {
    auto it = eventToCurrentWav_.find(eventName);
    if (it == eventToCurrentWav_.end()) {
        return false;
    }
    if (!std::filesystem::exists(replacementWav)) {
        return false;
    }

    rollback_.BeginTransaction("replace-" + eventName);
    const auto targetPath = it->second;
    const auto originalPath = eventToBackupWav_[eventName];

    rollback_.RegisterUndo("restore-original-" + eventName, [targetPath, originalPath]() {
        std::error_code ec;
        if (std::filesystem::exists(originalPath)) {
            std::filesystem::copy_file(originalPath, targetPath, std::filesystem::copy_options::overwrite_existing, ec);
        }
    });

    std::error_code ec;
    std::filesystem::copy_file(replacementWav, targetPath, std::filesystem::copy_options::overwrite_existing, ec);
    if (ec) {
        rollback_.Rollback();
        return false;
    }

    rollback_.Commit();
    return true;
}

bool SystemSoundReplacementManager::RestoreDefaults() {
    for (const auto& [eventName, backupPath] : eventToBackupWav_) {
        auto it = eventToCurrentWav_.find(eventName);
        if (it == eventToCurrentWav_.end()) {
            continue;
        }

        std::error_code ec;
        std::filesystem::copy_file(backupPath, it->second, std::filesystem::copy_options::overwrite_existing, ec);
    }

    return true;
}

std::filesystem::path SystemSoundReplacementManager::BackupRoot() const {
    return backupRoot_;
}

} // namespace bossforge
