#pragma once
#include <cstdint>
#include <string>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <unordered_set>

struct FlagEvent {
    uint32_t flagId;
    uint8_t  value;

    std::string to_json() const {
        return "{\"type\":\"flag_set\",\"flag_id\":" +
               std::to_string(flagId) + ",\"value\":" +
               std::to_string(value) + "}";
    }
};

class FlagEventQueue {
    std::queue<FlagEvent> queue_;
    std::mutex mtx_;
    std::condition_variable cv_;
public:
    void push(FlagEvent ev) {
        std::lock_guard<std::mutex> lock(mtx_);
        if (queue_.size() > 500) queue_.pop();
        queue_.push(ev);
        cv_.notify_one();
    }

    bool try_pop(FlagEvent& ev, int timeout_ms) {
        std::unique_lock<std::mutex> lock(mtx_);
        if (!cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms),
                          [this] { return !queue_.empty(); }))
            return false;
        ev = queue_.front();
        queue_.pop();
        return true;
    }
};

extern FlagEventQueue           g_flagQueue;
extern uintptr_t                g_eventFlagFunc;
extern bool                     g_flag_hook_installed;
extern std::unordered_set<uint32_t> g_flagWhitelist;

bool ensure_flag_patterns();
void install_flag_hook();
