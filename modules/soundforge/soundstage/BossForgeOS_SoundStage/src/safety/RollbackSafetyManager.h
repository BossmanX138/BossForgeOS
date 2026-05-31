#pragma once

#include <functional>
#include <string>
#include <vector>

namespace bossforge {

class RollbackSafetyManager {
public:
    using UndoAction = std::function<void()>;

    void BeginTransaction(const std::string& name);
    void RegisterUndo(const std::string& label, UndoAction undo);
    void Commit();
    void Rollback();

    bool InTransaction() const;
    std::string ActiveTransaction() const;

private:
    struct Entry {
        std::string label;
        UndoAction undo;
    };

    std::string activeName_;
    std::vector<Entry> undoEntries_;
};

} // namespace bossforge
