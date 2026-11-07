#ifndef SMASH360_LOG_SINK_H
#define SMASH360_LOG_SINK_H
// libultraship's spdlog lines join game:\smash360.log instead of a rotating file under game:\logs,
// so the console writes one log. The sink forwards the message text only; the platform log adds no
// timestamps, and its queue is thread safe, so no formatter or mutex is needed.
#include "runtime.h"
#include <spdlog/sinks/sink.h>

class Smash360LogSink : public spdlog::sinks::sink {
public:
    void log(const spdlog::details::log_msg& msg) {
        Smash360_LogLevel(static_cast<int>(msg.level), "%.*s", static_cast<int>(msg.payload.size()), msg.payload.data());
    }
    void flush() {}
    void set_pattern(const std::string&) {}
    void set_formatter(std::unique_ptr<spdlog::formatter>) {}
};
#endif
