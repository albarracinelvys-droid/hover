// Build-only stub: Windhawk injects these symbols during an actual mod build.
#define _WIN32_WINNT 0x0A00
#define WINVER 0x0A00
inline int Wh_GetIntSetting(const wchar_t*) { return 0; }
inline void Wh_Log(const wchar_t*, ...) {}
#include "../../HOVER_v4_6_GOOGLE_OAUTH_WINDHAWK.wh.cpp"
