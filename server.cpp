#include "server.h"
#include "game.h"
#include "hook.h"
#include "flag.h"
#include "types.h"
#include <string>
#include <unordered_set>
#include <cstdlib>
#include <thread>
#include <atomic>

#define CPPHTTPLIB_NO_EXCEPTIONS
#include "httplib.h"

// --- Parsing de messages JSON minimal ---

static void extract_int_array(const std::string& s, std::unordered_set<uint32_t>& out) {
    out.clear();
    auto start = s.find('[');
    auto end   = s.find(']');
    if (start == std::string::npos || end == std::string::npos || end <= start) return;
    size_t i = start + 1;
    while (i < end) {
        while (i < end && (s[i] == ' ' || s[i] == ',')) i++;
        if (i >= end) break;
        int neg = 0;
        if (s[i] == '-') { neg = 1; i++; }
        uint32_t val = 0;
        while (i < end && s[i] >= '0' && s[i] <= '9') { val = val * 10 + (uint32_t)(s[i] - '0'); i++; }
        if (!neg) out.insert(val);
    }
}

static int extract_int(const std::string& s, const char* key, int def) {
    auto p = s.find(key);
    if (p == std::string::npos) return def;
    p = s.find(':', p);
    if (p == std::string::npos) return def;
    p++;
    while (p < s.size() && (s[p] == ' ' || s[p] == '\t')) p++;
    int neg = 0, val = 0;
    if (p < s.size() && s[p] == '-') { neg = 1; p++; }
    while (p < s.size() && s[p] >= '0' && s[p] <= '9') { val = val * 10 + (s[p] - '0'); p++; }
    return neg ? -val : val;
}

// --- Handlers ---

static void handle_give(const httplib::Request& req, httplib::Response& res) {
    if (!ensure_patterns()) {
        res.set_content("{\"error\":\"patterns not found\"}", "application/json");
        return;
    }
    void* mgr = get_inventory_manager();
    if (!mgr) {
        res.set_content("{\"error\":\"not in-game\"}", "application/json");
        return;
    }
    uint8_t* buf = get_buffer();
    if (!buf) {
        res.set_content("{\"error\":\"buffer alloc failed\"}", "application/json");
        return;
    }

    uint32_t base_id = (uint32_t)std::stoul(req.get_param_value("base_id"));
    uint32_t type    = (uint32_t)std::stoul(req.get_param_value("type"));
    uint32_t qty     = (uint32_t)std::stoul(req.get_param_value("qty"));
    uint32_t upgrade = req.has_param("upgrade") ? (uint32_t)std::stoul(req.get_param_value("upgrade")) : 0;
    int32_t  ash     = req.has_param("ash")     ? (int32_t)std::stol(req.get_param_value("ash"))       : -1;

    ItemData item{};
    item.entryCount = 1;
    item.encodedID  = encode_item_id(base_id, type, upgrade);
    item.quantity   = qty;
    item.ashOfWarID = ash;

    dbg("[give] encodedID=0x%08X qty=%u ash=%d\n", item.encodedID, qty, ash);
    do_give(mgr, &item, buf);

    res.set_content("{\"status\":\"ok\"}", "application/json");
}

static void ws_handle(httplib::ws::WebSocket& w, const std::string& msg) {
    if (msg.find("set_flag_whitelist") != std::string::npos) {
        extract_int_array(msg, g_flagWhitelist);
        if (ensure_patterns()) {
            install_hook();
            install_flag_hook();
        }
        dbg("[ws] flag whitelist updated (%zu items)\n", g_flagWhitelist.size());
        w.send("{\"status\":\"flag_whitelist_updated\"}");
        return;
    }

    if (!ensure_patterns()) {
        w.send("{\"error\":\"patterns not found\"}");
        return;
    }
    void* mgr = get_inventory_manager();
    if (!mgr) {
        w.send("{\"error\":\"not in-game\"}");
        return;
    }
    uint8_t* buf = get_buffer();
    if (!buf) {
        w.send("{\"error\":\"buffer alloc failed\"}");
        return;
    }

    int base_id = extract_int(msg, "base_id", 0);
    int type    = extract_int(msg, "type",    0);
    int qty     = extract_int(msg, "qty",     1);
    int upgrade = extract_int(msg, "upgrade", 0);
    int ash     = extract_int(msg, "ash",    -1);

    ItemData item{};
    item.entryCount = 1;
    item.encodedID  = encode_item_id((uint32_t)base_id, (uint32_t)type, (uint32_t)upgrade);
    item.quantity   = (uint32_t)qty;
    item.ashOfWarID = ash;

    dbg("[ws] encodedID=0x%08X qty=%u ash=%d\n", item.encodedID, qty, ash);
    do_give(mgr, &item, buf);

    w.send("{\"status\":\"ok\"}");
}

// --- Serveur HTTP/WebSocket ---

void run_server() {
    httplib::Server svr;

    svr.Get("/test", [](const httplib::Request&, httplib::Response& res) {
        res.set_content("Serveur DLL Elden Ring actif !", "text/plain");
    });

    svr.Get("/give", handle_give);

    svr.WebSocket("/ws", [](const httplib::Request&, httplib::ws::WebSocket& w) {
        std::atomic<bool> done{false};

        std::thread writer([&]() {
            while (!done) {
                FlagEvent ev;
                if (g_flagQueue.try_pop(ev, 100)) {
                    if (w.is_open()) {
                        w.send(ev.to_json());
                        dbg("[ws] flag sent: id=%u val=%u\n", ev.flagId, ev.value);
                    }
                }
            }
        });

        std::string msg;
        auto r = w.read(msg);
        while (r == httplib::ws::ReadResult::Text || r == httplib::ws::ReadResult::Binary) {
            dbg("[ws] recv: %s\n", msg.c_str());
            ws_handle(w, msg);
            r = w.read(msg);
        }

        done = true;
        writer.join();
        dbg("[ws] disconnected\n");
    });

    dbg("[give] server listening on port 12999\n");
    svr.listen("0.0.0.0", 12999);
}
