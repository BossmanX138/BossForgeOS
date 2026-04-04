#include "RollbackSafetyManager.h"

namespace bossforge {

void RollbackSafetyManager::BeginTransaction(const std::string& name) {
    activeName_ = name;
    undoEntries_.clear();
}

void RollbackSafetyManager::RegisterUndo(const std::string& label, UndoAction undo) {
    if (!InTransaction() || !undo) {
        return;
    }

    undoEntries_.push_back(Entry{label, std::move(undo)});
}

void RollbackSafetyManager::Commit() {
    activeName_.clear();
    undoEntries_.clear();
}

void RollbackSafetyManager::Rollback() {
    for (auto it = undoEntries_.rbegin(); it != undoEntries_.rend(); ++it) {
        if (it->undo) {
            it->undo();
        }
    }

    activeName_.clear();
    undoEntries_.clear();
}

bool RollbackSafetyManager::InTransaction() const {
    return !activeName_.empty();
}

std::string RollbackSafetyManager::ActiveTransaction() const {
    return activeName_;
}

} // namespace bossforge
