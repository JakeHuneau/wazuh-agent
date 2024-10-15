#pragma once

#include <stdarg.h>

// Extract file name from path (inline function for C++ and macro for C)
#ifdef __cplusplus
#include <spdlog/spdlog.h>
inline const char* GetFileName(const char* path)
{
    const char* file = strrchr(path, '/');
    return file ? file + 1 : path;
}
#else
#define GetFileName(path) (strrchr((path), '/') ? strrchr((path), '/') + 1 : (path))
#endif

#define LOG_FILE_NAME GetFileName(__FILE__)

#ifdef __cplusplus
extern "C" {
#endif

#define LOG_BUFFER_SIZE 1024 // Buffer size for formatted log messages

void LogTrace_C(const char* file, int line, const char* func, const char* message, ...);
void LogDebug_C(const char* file, int line, const char* func, const char* message, ...);
void LogInfo_C(const char* file, int line, const char* func, const char* message, ...);
void LogWarn_C(const char* file, int line, const char* func, const char* message, ...);
void LogError_C(const char* file, int line, const char* func, const char* message, ...);
void LogCritical_C(const char* file, int line, const char* func, const char* message, ...);

#ifdef __cplusplus
}
#endif

#ifdef __cplusplus

#include <ilogger.hpp>

#define LogTrace(message, ...) spdlog::trace("[TRACE] [{}:{}] [{}] " message, LOG_FILE_NAME, __LINE__, __func__ __VA_OPT__(, ) __VA_ARGS__)
#define LogDebug(message, ...) spdlog::debug("[DEBUG] [{}:{}] [{}] " message, LOG_FILE_NAME, __LINE__, __func__ __VA_OPT__(, ) __VA_ARGS__)
#define LogInfo(message, ...)  spdlog::info("[INFO] [{}:{}] [{}] " message, LOG_FILE_NAME, __LINE__, __func__ __VA_OPT__(, ) __VA_ARGS__)
#define LogWarn(message, ...)  spdlog::warn("[WARN] [{}:{}] [{}] " message, LOG_FILE_NAME, __LINE__, __func__ __VA_OPT__(, ) __VA_ARGS__)
#define LogError(message, ...) spdlog::error("[ERROR] [{}:{}] [{}] " message, LOG_FILE_NAME, __LINE__, __func__ __VA_OPT__(, ) __VA_ARGS__)
#define LogCritical(message, ...) spdlog::critical("[CRITICAL] [{}:{}] [{}] " message, LOG_FILE_NAME, __LINE__, __func__ __VA_OPT__(, ) __VA_ARGS__)

class Logger : public Ilogger
{
public:
    Logger();
};

#else

#define LogTrace(message, ...) LogTrace_C(LOG_FILE_NAME, __LINE__, __func__, message, ##__VA_ARGS__)
#define LogDebug(message, ...) LogDebug_C(LOG_FILE_NAME, __LINE__, __func__, message, ##__VA_ARGS__)
#define LogInfo(message, ...)  LogInfo_C(LOG_FILE_NAME, __LINE__, __func__, message, ##__VA_ARGS__)
#define LogWarn(message, ...)  LogWarn_C(LOG_FILE_NAME, __LINE__, __func__, message, ##__VA_ARGS__)
#define LogError(message, ...) LogError_C(LOG_FILE_NAME, __LINE__, __func__, message, ##__VA_ARGS__)
#define LogCritical(message, ...) LogCritical_C(LOG_FILE_NAME, __LINE__, __func__, message, ##__VA_ARGS__)

#endif

#define LOG_FILE_NAME GetFileName(__FILE__)
