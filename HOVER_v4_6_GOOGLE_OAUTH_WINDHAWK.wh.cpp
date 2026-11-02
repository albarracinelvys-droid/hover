// ==WindhawkMod==
// @id hover-island-v38-hardware
// @name HOVER v4.9.1 - Arrastre real desde los ojos
// @description Calendario interactivo con eventos de Google, detalles por día y enlaces, vía motor Python local.
// @version 4.9.2
// @author HOVER - version de prueba
// @include explorer.exe
// @architecture x86-64
// @compilerOptions -lgdiplus -lgdi32 -luser32 -lshell32 -lole32
// @license MIT
// ==/WindhawkMod==

// ==WindhawkModReadme==
/*
# HOVER v3.9 - notch premium con puntos y carpeta arrastrable

- NOTCH: union curva con borde superior (sin cabeza de robot ni boca).
- OJOS: solamente blancos e iris color Windows, sin aureolas, con seguimiento visible y parpadeo.
- REPOSO: negro opaco, reloj, ojos y texto discreto HOVER, sin titulo de cancion.
- APERTURA: por hover, colapsa al salir el cursor.
- PAGINAS: musica, copias, calendario, atajos y equipo con transicion VERTICAL.
- GESTOS: rueda vertical/horizontal, desplazamiento de dos dedos del trackpad, WM_GESTURE y flechas con cursor sobre HOVER.
- ARRASTRAR: sostener entre los ojos y mover la isla libremente por la pantalla. No se interpreta como cambio de pagina.
- MEDIA: teclas multimedia globales; el puente v3.9.2 trae caratula si Windows la ofrece, o ecualizador animado.
- MONITOR: CPU, RAM, GPU si PDH lo ofrece, NET UP/DOWN y disco en 6 tarjetas.
- SIN BORDES: contorno exterior eliminado, iconos vectoriales mejorados.
- CINCO MODULOS sin titulo ni barra horizontal. Cinco puntos VERTICALES; el activo crece.
- OJOS aumentan hasta 75% al abrir la isla, con transicion suave.
- ATAJOS: 6 (sin Musica ni Historial). Carpeta permite soltar archivos: COPIA sin borrar origen.
- Carpeta favorita se guarda en AppData\HOVER, clic derecho sobre Carpeta para cambiar.
- VOZ: asistente Python 4.1 con alias foneticos para nombres ingleses (requiere Vosk espanol).
- PESTANAS: adicionales configurables por voz (maximo 5), enlaces HTTP(S) seguros.
- CALENDARIO: sincroniza metadatos de Google Calendar desde HOVER Python, marca dias, permite ver y abrir eventos y crear nuevos en Google Calendar.

Desactiva otros mods de isla para evitar dos superposiciones.
La visualizacion del portapapeles puede desactivarse por privacidad.
*/
// ==/WindhawkModReadme==

// ==WindhawkModSettings==
/*
- topGap: 0
  $name: Separacion superior en pixeles
- xOffset: 0
  $name: Desplazamiento horizontal en pixeles
- use24Hour: false
  $name: Hora en formato 24 horas
- expandedOpacity: 242
  $name: Opacidad del panel abierto entre 170 y 252
- clipboardPreview: true
  $name: Mostrar vista previa del texto copiado
- hoverToExpand: true
  $name: Expandir al pasar el mouse
- useManualPupilColor: false
  $name: Usar color manual de pupila
  $description: "Desactivado utiliza el acento de Windows, no el RGB fisico del teclado."
- pupilRed: 150
  $name: Rojo de pupila entre 0 y 255
- pupilGreen: 104
  $name: Verde de pupila entre 0 y 255
- pupilBlue: 255
  $name: Azul de pupila entre 0 y 255
- autoOpenSpotify: false
  $name: Abrir Spotify cuando no hay sesiones detectadas
  $description: "Desactivado recomendado para que los botones controlen otras aplicaciones."
- swipeSensitivity: 32
  $name: Sensibilidad de desplazamiento entre 15 y 160
  $description: "32 recomendado. Menor valor = responde antes a movimientos de dos dedos."
- gestureDiagnostics: false
  $name: Registrar eventos de navegacion en el log
  $description: "Activar solo para diagnosticar el touchpad desde el registro de Windhawk."
*/
// ==/WindhawkModSettings==

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <objidl.h> // Requerido por GDI+ para IStream y GUID en MSVC.
#include <gdiplus.h>
#include <shlobj.h>
#include <shellapi.h>
#include <objbase.h>
#include <ole2.h>
#include <oleidl.h>
#include <windowsx.h>
#include <memory>
#include <algorithm>
#include <cstdlib>
#include <atomic>
#include <cmath>
#include <cstring>
#include <cwchar>
#include <cwctype>
#include <mutex>
#include <string>
#include <vector>
#include <unordered_map>
#include <utility>
#include <cstdint>
#include <cstdio>
#include <iphlpapi.h>
#include <ifdef.h>
#include <pdh.h>
#include <pdhmsg.h>
#ifndef WM_POINTERWHEEL
#define WM_POINTERWHEEL 0x024E
#endif
#ifndef WM_POINTERHWHEEL
#define WM_POINTERHWHEEL 0x024F
#endif
#define ISLAND_HAS_MEDIA_API 0 // Spotify se conecta mediante el puente local.

using namespace Gdiplus;
namespace {
constexpr wchar_t kClass[] = L"WindhawkIslandPremiumFourZero";
constexpr int kMiniWidth = 224, kMiniHeight = 46;
constexpr int kToastWidth = 408, kToastHeight = 101;
constexpr int kPanelWidth = 536, kPanelHeight = 350;
constexpr UINT_PTR kTimer = 41;
constexpr UINT kSettingsChanged = WM_APP+21;
constexpr UINT kWheelMessage = WM_APP+22;
constexpr UINT kWheelHorizontalMessage = WM_APP+24;
constexpr UINT kFilesCopiedMessage = WM_APP+25;
constexpr UINT kArrowNavigation = WM_APP+26;
constexpr UINT kEyeGripBegin = WM_APP+27;
constexpr UINT kEyeGripEnd = WM_APP+28;
constexpr int kBuiltInPages = 5;
constexpr int kMaxVoiceTabs = 5;
constexpr float kContentLift=31.0f;
constexpr ULONGLONG kToastMs = 6800;
constexpr ULONGLONG kChargeToastMs = 2600;

std::atomic<HWND> g_hwnd{nullptr};
std::atomic<bool> g_stopping{false};
HANDLE g_uiThread=nullptr, g_mutexHandle=nullptr;
HHOOK g_wheelHook=nullptr;
HHOOK g_keyboardHook=nullptr;
bool g_gestureActive=false;
POINT g_lastGesturePos{};
std::atomic<int> g_topGap{0}, g_xOffset{0}, g_expandedOpacity{243};
std::atomic<bool> g_24h{false}, g_hover{true}, g_showClipboard{true};
std::atomic<bool> g_manualPupil{false};
std::atomic<bool> g_autoOpenSpotify{false};
std::atomic<int> g_swipeSensitivity{25};
std::atomic<bool> g_gestureDiagnostics{false};
std::atomic<int> g_pupilR{150},g_pupilG{104},g_pupilB{255};
std::atomic<bool> g_bridgeOnline{false};
int g_pendingMediaAction=0;
ULONGLONG g_pendingMediaExpires=0;
float g_open=0, g_openV=0, g_eyeX=0, g_eyeY=0, g_eyeVX=0, g_eyeVY=0;
float g_pageEase=1.0f;
int g_pageDirection=1;
int g_currentPage=0, g_previousPage=0;
bool g_clipDirty=false;
ULONGLONG g_lastMediaRead=0;
float g_wheelAccumV=0,g_wheelAccumH=0;
ULONGLONG g_lastSwipeMs=0;
ULONGLONG g_lastWheelAt=0;
DWORD g_lastWheelTick=0;
int g_lastWheelValue=0;
bool g_lastWheelHorizontal=false;
ULONGLONG g_lastGestureTick=0;
unsigned long g_bridgeCommandSerial=0;
bool g_drag=false;
bool g_eyeGripDrag=false;
bool g_eyeGripMoved=false;
// The LL mouse hook catches the click even when per-pixel transparency stops
// the non-activating layered window from receiving WM_LBUTTONDOWN.
std::atomic<bool> g_hookGripActive{false};
POINT g_dragOrigin{};
int g_islandShiftX=0, g_islandShiftY=0;
int g_grabStartShiftX=0, g_grabStartShiftY=0;
int g_clipAttempts=0, g_monthOffset=0;
int g_calendarSelectedDay=0,g_calendarSelectedIndex=0;
bool g_calendarDetailsOpen=false;
ULONGLONG g_calendarLastRead=0;
int g_hoverAction=-1;
std::wstring g_lastClip;
ULONGLONG g_clipTick=0;
std::wstring g_favFolder;
bool g_fileDragActive=false;
bool g_fileDragCanCopy=false;
bool g_dropHoverFolder=false;
ULONGLONG g_copyToastUntil=0;
std::wstring g_copyToastText;
std::wstring g_voiceMessage;
std::wstring g_voiceState;
ULONGLONG g_voiceNoticeUntil=0, g_voiceExpandUntil=0, g_lastVoiceRead=0;
ULONGLONG g_voiceQuietUntil=0;
ULONGLONG g_lastTabsRead=0;
int g_feedbackAction=-1;
ULONGLONG g_feedbackUntil=0;

std::string g_lastVoiceSerial;
struct VoiceTab {std::wstring title; std::wstring url;};
std::vector<VoiceTab> g_voiceTabs;
struct CalendarEvent {
    int year=0,month=0,day=0;
    std::wstring title,url;
};
std::vector<CalendarEvent> g_calendarEvents;
std::wstring g_calendarStatus=L"sin datos";
std::vector<HANDLE> g_copyThreads; // se esperan antes de descargar el mod


BYTE g_lastACLineStatus=255;
ULONGLONG g_chargeToastUntil=0;
ULONGLONG g_lastHardwareRead=0;

struct MediaState {
    std::wstring title, artist, source;
    bool spotify=false, playing=false, shuffle=false, repeat=false;
    float progress=-1.0f;
    std::wstring artwork;
};
MediaState g_media;
std::mutex g_mediaGuard;
std::unique_ptr<Bitmap> g_albumCover;
std::wstring g_currentCoverName;


// Hardware monitor: all values are sampled locally once per second.
// GPU uses an optional PDH GPU Engine counter; no fake percentage.
struct HardwareState {
    float cpu = -1.0f;
    float ram = -1.0f;
    float gpu = -1.0f;
    float disk = -1.0f;
    double netUp = -1.0;
    double netDown = -1.0;
    double usedRamGiB = 0.0;
    double totalRamGiB = 0.0;
};
HardwareState g_hw;
ULONGLONG g_prevCPUIdle=0, g_prevCPUKernel=0, g_prevCPUUser=0;
ULONGLONG g_prevNetUp=0, g_prevNetDown=0;
ULONGLONG g_prevNetTick=0;
bool g_hasNetworkSample=false;

ULONGLONG FtToU64(const FILETIME& v) {
    return (ULONGLONG(v.dwHighDateTime)<<32)|v.dwLowDateTime;
}

// DLLs are resolved dynamically: no extra linker library is required.
// Windhawk's compiler provides MIB_IFTABLE / MIB_IFROW, but may not provide
// MIB_IF_TABLE2 / MIB_IF_ROW2. Use the legacy GetIfTable API for portability.
// Legacy in/out octet fields are 32-bit: accumulate per-adapter unsigned deltas
// in 64-bit totals, including normal counter rollover.
using GetTableFn = DWORD (WINAPI*)(PMIB_IFTABLE, PULONG, BOOL);

struct NetworkAdapterSample {
    DWORD received = 0;
    DWORD sent = 0;
};

bool ReadNetworkCounters(ULONGLONG& uploaded, ULONGLONG& downloaded) {
    static HMODULE dll = LoadLibraryW(L"iphlpapi.dll");
    static GetTableFn getTable = dll ? reinterpret_cast<GetTableFn>(
        GetProcAddress(dll, "GetIfTable")) : nullptr;
    if (!getTable) return false;

    ULONG bytes = 0;
    const DWORD firstStatus = getTable(nullptr, &bytes, FALSE);
    if (firstStatus != ERROR_INSUFFICIENT_BUFFER && firstStatus != NO_ERROR)
        return false;
    if (bytes < sizeof(MIB_IFTABLE)) bytes = sizeof(MIB_IFTABLE);

    std::vector<BYTE> buffer(bytes);
    PMIB_IFTABLE table = reinterpret_cast<PMIB_IFTABLE>(buffer.data());
    DWORD result = getTable(table, &bytes, FALSE);
    if (result == ERROR_INSUFFICIENT_BUFFER && bytes > buffer.size()) {
        buffer.resize(bytes);
        table = reinterpret_cast<PMIB_IFTABLE>(buffer.data());
        result = getTable(table, &bytes, FALSE);
    }
    if (result != NO_ERROR) return false;

    // IANA interface types: 6=Ethernet, 71=Wi-Fi, 24=loopback.
    // Legacy operational status: 4=connected, 5=operational.
    bool hasPhysical = false;
    for (DWORD i = 0; i < table->dwNumEntries; ++i) {
        const MIB_IFROW& row = table->table[i];
        if (row.dwOperStatus == 4 || row.dwOperStatus == 5) {
            if (row.dwType == 6 || row.dwType == 71) {
                hasPhysical = true;
                break;
            }
        }
    }

    static std::unordered_map<DWORD, NetworkAdapterSample> previous;
    static ULONGLONG accumulatedUp = 0;
    static ULONGLONG accumulatedDown = 0;
    std::unordered_map<DWORD, NetworkAdapterSample> current;

    for (DWORD i = 0; i < table->dwNumEntries; ++i) {
        const MIB_IFROW& row = table->table[i];
        if (row.dwOperStatus != 4 && row.dwOperStatus != 5) continue;
        if (row.dwType == 24) continue;
        if (hasPhysical && row.dwType != 6 && row.dwType != 71) continue;

        NetworkAdapterSample sample{row.dwInOctets, row.dwOutOctets};
        current[row.dwIndex] = sample;
        auto it = previous.find(row.dwIndex);
        if (it != previous.end()) {
            // DWORD subtraction is intentionally modulo 2^32.
            const DWORD sent = DWORD(sample.sent - it->second.sent);
            const DWORD received = DWORD(sample.received - it->second.received);
            // Ignore an implausible one-sample jump (e.g. adapter counter reset).
            // 512 MiB/sample still allows multi-Gbps throughput at 1 Hz.
            constexpr DWORD kMaxSampleDelta = 512u * 1024u * 1024u;
            if (sent <= kMaxSampleDelta) accumulatedUp += sent;
            if (received <= kMaxSampleDelta) accumulatedDown += received;
        }
    }
    previous.swap(current);
    uploaded = accumulatedUp;
    downloaded = accumulatedDown;
    return true;
}

// Performance counters can be unavailable depending on GPU driver and locale.
// PdhAddEnglishCounterW handles localized Windows installations.
using PdhOpenFn = PDH_STATUS (WINAPI*)(LPCWSTR,DWORD_PTR,PDH_HQUERY*);
using PdhAddFn = PDH_STATUS (WINAPI*)(PDH_HQUERY,LPCWSTR,DWORD_PTR,PDH_HCOUNTER*);
using PdhCollectFn = PDH_STATUS (WINAPI*)(PDH_HQUERY);
using PdhArrayFn = PDH_STATUS (WINAPI*)(PDH_HCOUNTER,DWORD,LPDWORD,LPDWORD,PPDH_FMT_COUNTERVALUE_ITEM_W);
using PdhCloseFn = PDH_STATUS (WINAPI*)(PDH_HQUERY);
struct GpuPdh {
    bool attempted=false;
    bool ready=false;
    HMODULE dll=nullptr;
    PDH_HQUERY query=nullptr;
    PDH_HCOUNTER counter=nullptr;
    PdhCollectFn collect=nullptr;
    PdhArrayFn getArray=nullptr;
    PdhCloseFn close=nullptr;
} g_gpu;

void InitGpuMonitor() {
    if(g_gpu.attempted) return;
    g_gpu.attempted=true;
    g_gpu.dll=LoadLibraryW(L"pdh.dll");
    if(!g_gpu.dll)return;
    PdhOpenFn open=reinterpret_cast<PdhOpenFn>(GetProcAddress(g_gpu.dll,"PdhOpenQueryW"));
    PdhAddFn add=reinterpret_cast<PdhAddFn>(GetProcAddress(g_gpu.dll,"PdhAddEnglishCounterW"));
    g_gpu.collect=reinterpret_cast<PdhCollectFn>(GetProcAddress(g_gpu.dll,"PdhCollectQueryData"));
    g_gpu.getArray=reinterpret_cast<PdhArrayFn>(GetProcAddress(g_gpu.dll,"PdhGetFormattedCounterArrayW"));
    g_gpu.close=reinterpret_cast<PdhCloseFn>(GetProcAddress(g_gpu.dll,"PdhCloseQuery"));
    if(!open||!add||!g_gpu.collect||!g_gpu.getArray||!g_gpu.close)return;
    if(open(nullptr,0,&g_gpu.query)!=ERROR_SUCCESS)return;
    if(add(g_gpu.query,L"\\GPU Engine(*)\\Utilization Percentage",0,&g_gpu.counter)!=ERROR_SUCCESS){
        g_gpu.close(g_gpu.query);g_gpu.query=nullptr;return;
    }
    g_gpu.collect(g_gpu.query);
    g_gpu.ready=true;
}
void UpdateGpuMonitor() {
    InitGpuMonitor();
    if(!g_gpu.ready)return;
    if(g_gpu.collect(g_gpu.query)!=ERROR_SUCCESS)return;
    DWORD bytes=0,count=0;
    // First call reports the required allocation size.
    g_gpu.getArray(g_gpu.counter,PDH_FMT_DOUBLE,&bytes,&count,nullptr);
    if(bytes<sizeof(PDH_FMT_COUNTERVALUE_ITEM_W) || bytes>1024*1024)return;
    std::vector<BYTE> storage(bytes);
    PPDH_FMT_COUNTERVALUE_ITEM_W values=reinterpret_cast<PPDH_FMT_COUNTERVALUE_ITEM_W>(storage.data());
    if(g_gpu.getArray(g_gpu.counter,PDH_FMT_DOUBLE,&bytes,&count,values)!=ERROR_SUCCESS)return;
    double peak=0.0;bool found=false;
    for(DWORD i=0;i<count;i++){
        if(values[i].FmtValue.CStatus==PDH_CSTATUS_VALID_DATA ||
           values[i].FmtValue.CStatus==PDH_CSTATUS_NEW_DATA){
            double val=values[i].FmtValue.doubleValue;
            if(std::isfinite(val) && val>=0.0){peak=std::max(peak,val);found=true;}
        }
    }
    if(found)g_hw.gpu=std::max(0.0f,std::min(100.0f,float(peak)));
}
void ShutdownGpuMonitor(){
    if(g_gpu.query&&g_gpu.close)g_gpu.close(g_gpu.query);
    g_gpu.query=nullptr;
    if(g_gpu.dll)FreeLibrary(g_gpu.dll);
    g_gpu.dll=nullptr;
}

void UpdateHardware() {
    FILETIME idle{},kernel{},user{};
    if(GetSystemTimes(&idle,&kernel,&user)) {
        ULONGLONG a=FtToU64(idle),b=FtToU64(kernel),c=FtToU64(user);
        if(g_prevCPUKernel||g_prevCPUUser){
            ULONGLONG total=(b-g_prevCPUKernel)+(c-g_prevCPUUser);
            ULONGLONG idled=a-g_prevCPUIdle;
            if(total>0 && idled<=total)g_hw.cpu=100.0f*float(total-idled)/float(total);
        }
        g_prevCPUIdle=a;g_prevCPUKernel=b;g_prevCPUUser=c;
    }
    MEMORYSTATUSEX ms{};ms.dwLength=sizeof(ms);
    if(GlobalMemoryStatusEx(&ms)&&ms.ullTotalPhys>0){
        g_hw.ram=100.0f*float(ms.ullTotalPhys-ms.ullAvailPhys)/float(ms.ullTotalPhys);
        g_hw.usedRamGiB=double(ms.ullTotalPhys-ms.ullAvailPhys)/(1024.0*1024.0*1024.0);
        g_hw.totalRamGiB=double(ms.ullTotalPhys)/(1024.0*1024.0*1024.0);
    }
    wchar_t root[]=L"C:\\";
    wchar_t dir[MAX_PATH]{};
    if(GetWindowsDirectoryW(dir,MAX_PATH)>=2 && dir[1]==L':')root[0]=dir[0];
    ULARGE_INTEGER available{},total{},freeDisk{};
    if(GetDiskFreeSpaceExW(root,&available,&total,&freeDisk)&&total.QuadPart>0)
        g_hw.disk=100.0f*float(total.QuadPart-freeDisk.QuadPart)/float(total.QuadPart);
    ULONGLONG up=0,down=0;
    ULONGLONG now=GetTickCount64();
    if(ReadNetworkCounters(up,down)) {
        if(g_hasNetworkSample && now>g_prevNetTick && up>=g_prevNetUp && down>=g_prevNetDown){
            double sec=double(now-g_prevNetTick)/1000.0;
            g_hw.netUp=double(up-g_prevNetUp)*8.0/(1000000.0*sec);
            g_hw.netDown=double(down-g_prevNetDown)*8.0/(1000000.0*sec);
        }
        g_hasNetworkSample=true;g_prevNetUp=up;g_prevNetDown=down;g_prevNetTick=now;
    }
    UpdateGpuMonitor();
}

float Clamp(float x,float lo,float hi) {return std::max(lo,std::min(hi,x));}
int ClampInt(int x,int lo,int hi) {return std::max(lo,std::min(hi,x));}

Color Accent(BYTE a=255) {
    using Fn=HRESULT (WINAPI*)(DWORD*,BOOL*);
    static HMODULE dll=LoadLibraryW(L"dwmapi.dll");
    static Fn fn=dll?reinterpret_cast<Fn>(GetProcAddress(dll,"DwmGetColorizationColor")):nullptr;
    DWORD argb=0; BOOL opaque=FALSE;
    if (fn && SUCCEEDED(fn(&argb,&opaque)))
        return Color(a,BYTE(argb>>16),BYTE(argb>>8),BYTE(argb));
    COLORREF c=GetSysColor(COLOR_HIGHLIGHT);
    return Color(a,GetRValue(c),GetGValue(c),GetBValue(c));
}

Color PupilColor(BYTE alpha=255) {
    if(!g_manualPupil) return Accent(alpha);
    return Color(alpha,BYTE(g_pupilR.load()),BYTE(g_pupilG.load()),BYTE(g_pupilB.load()));
}

void LoadSettings() {
    g_topGap=ClampInt(Wh_GetIntSetting(L"topGap"),0,130);
    g_xOffset=ClampInt(Wh_GetIntSetting(L"xOffset"),-1200,1200);
    g_expandedOpacity=ClampInt(Wh_GetIntSetting(L"expandedOpacity"),170,252);
    g_24h=Wh_GetIntSetting(L"use24Hour")!=0;
    g_hover=Wh_GetIntSetting(L"hoverToExpand")!=0;
    g_showClipboard=Wh_GetIntSetting(L"clipboardPreview")!=0;
    g_manualPupil=Wh_GetIntSetting(L"useManualPupilColor")!=0;
    g_pupilR=ClampInt(Wh_GetIntSetting(L"pupilRed"),0,255);
    g_pupilG=ClampInt(Wh_GetIntSetting(L"pupilGreen"),0,255);
    g_pupilB=ClampInt(Wh_GetIntSetting(L"pupilBlue"),0,255);
    g_autoOpenSpotify=Wh_GetIntSetting(L"autoOpenSpotify")!=0;
    g_swipeSensitivity=ClampInt(Wh_GetIntSetting(L"swipeSensitivity"),12,160);
    g_gestureDiagnostics=Wh_GetIntSetting(L"gestureDiagnostics")!=0;
}

void Text(Graphics& g,const std::wstring& str,float x,float y,float w,float h,
          float fontSize,Color color,bool bold=false,bool center=false,bool wrap=false) {
    FontFamily family(L"Segoe UI");
    Font font(&family,fontSize,bold?FontStyleBold:FontStyleRegular,UnitPixel);
    SolidBrush brush(color);
    StringFormat f;
    f.SetAlignment(center?StringAlignmentCenter:StringAlignmentNear);
    f.SetLineAlignment(wrap?StringAlignmentNear:StringAlignmentCenter);
    f.SetTrimming(StringTrimmingEllipsisCharacter);
    if(!wrap) f.SetFormatFlags(StringFormatFlagsNoWrap);
    g.DrawString(str.c_str(),-1,&font,RectF(x,y,w,h),&f,&brush);
}

// HOVER v3.9.2: las tarjetas son superficies de color, nunca cajas con contorno.
void Round(Graphics& g,float x,float y,float w,float h,float r,Color fill,Color line,float lw=1.0f) {
    (void)line; (void)lw;
    if(w<=1.0f||h<=1.0f)return;
    r=std::min(r,std::min(w,h)*0.49f);
    GraphicsPath p;
    const float d=2.0f*r;
    p.AddArc(x,y,d,d,180,90);p.AddArc(x+w-d,y,d,d,270,90);
    p.AddArc(x+w-d,y+h-d,d,d,0,90);p.AddArc(x,y+h-d,d,d,90,90);
    p.CloseFigure();
    SolidBrush brush(fill);g.FillPath(&brush,&p);
}

void IslandPath(GraphicsPath& p,float w,float h,float rTop,float rBottom) {
    const float left=0.5f;
    const float right=w-0.5f;
    const float bottom=h-0.7f;
    const float shoulder=Clamp(11.0f + rTop*0.18f,9.0f,16.0f);
    const float innerL=left+shoulder;
    const float innerR=right-shoulder;
    const float corner=std::min(rBottom,std::min((innerR-innerL)*0.5f,bottom*0.48f));
    p.StartFigure();
    p.AddLine(left,0.0f,right,0.0f);
    // hombro derecho: curva continua desde el borde superior
    p.AddBezier(right,0.0f,right-shoulder*0.58f,0.0f,
                innerR,shoulder*0.40f,innerR,shoulder);
    p.AddLine(innerR,shoulder,innerR,bottom-corner);
    p.AddArc(innerR-2.0f*corner,bottom-2.0f*corner,
             2.0f*corner,2.0f*corner,0.0f,90.0f);
    p.AddLine(innerR-corner,bottom,innerL+corner,bottom);
    p.AddArc(innerL,bottom-2.0f*corner,
             2.0f*corner,2.0f*corner,90.0f,90.0f);
    p.AddLine(innerL,bottom-corner,innerL,shoulder);
    p.AddBezier(innerL,shoulder,innerL,shoulder*0.40f,
                left+shoulder*0.58f,0.0f,left,0.0f);
    p.CloseFigure();
}

void SendMediaKey(WORD vk) {
    INPUT a[2]{};
    a[0].type=INPUT_KEYBOARD;a[0].ki.wVk=vk;
    a[1]=a[0];a[1].ki.dwFlags=KEYEVENTF_KEYUP;
    SendInput(2,a,sizeof(INPUT));
}
void Screenshot() {
    INPUT a[6]{};
    const WORD keys[3]={VK_LWIN,VK_LSHIFT,'S'};
    for(int i=0;i<3;i++){
        a[i].type=INPUT_KEYBOARD;a[i].ki.wVk=keys[i];
        a[5-i].type=INPUT_KEYBOARD;a[5-i].ki.wVk=keys[i];
        a[5-i].ki.dwFlags=KEYEVENTF_KEYUP;
    }
    SendInput(6,a,sizeof(INPUT));
}
void OpenUrl(const wchar_t* url) {ShellExecuteW(nullptr,L"open",url,nullptr,nullptr,SW_SHOWNORMAL);}
void OpenSpotify() {
    auto result=reinterpret_cast<INT_PTR>(ShellExecuteW(nullptr,L"open",L"spotify:",nullptr,nullptr,SW_SHOWNORMAL));
    if(result<=32) OpenUrl(L"https://open.spotify.com/");
}
std::wstring FavoritePathFile() {
    wchar_t appdata[MAX_PATH]{};
    if(FAILED(SHGetFolderPathW(nullptr,CSIDL_APPDATA,nullptr,SHGFP_TYPE_CURRENT,appdata)))return L"";
    std::wstring dir=std::wstring(appdata)+L"\\HOVER";
    CreateDirectoryW(dir.c_str(),nullptr);
    return dir+L"\\carpeta_favorita.txt";
}
// The position is stored separately from Windhawk settings so a drag is
// preserved across explorer.exe restarts. Nothing is written until release.
std::wstring IslandPositionFile() {
    const auto favorite=FavoritePathFile();
    if(favorite.empty())return L"";
    const auto separator=favorite.find_last_of(L'\\');
    if(separator==std::wstring::npos)return L"";
    return favorite.substr(0,separator+1)+L"posicion_isla.txt";
}
void LoadIslandPosition() {
    const auto path=IslandPositionFile();if(path.empty())return;
    HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,
                             OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return;
    char data[64]{};DWORD received=0;
    const BOOL ok=ReadFile(file,data,sizeof(data)-1,&received,nullptr);
    CloseHandle(file);
    int dx=0,dy=0;
    if(ok && received>0 && std::sscanf(data,"%d %d",&dx,&dy)==2 &&
       dx>=-10000 && dx<=10000 && dy>=-10000 && dy<=10000){
        g_islandShiftX=dx;
        g_islandShiftY=dy;
    }
}
void SaveIslandPosition() {
    const auto path=IslandPositionFile();if(path.empty())return;
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,
                             CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return;
    char data[64]{};
    const int count=std::snprintf(data,sizeof(data),"%d %d",
                                  g_islandShiftX,g_islandShiftY);
    if(count>0 && count<int(sizeof(data))){
        DWORD written=0;
        WriteFile(file,data,DWORD(count),&written,nullptr);
    }
    CloseHandle(file);
}

void SaveFavoriteFolder() {
    std::wstring cfg=FavoritePathFile(); if(cfg.empty())return;
    HANDLE f=CreateFileW(cfg.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,
                         CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(f==INVALID_HANDLE_VALUE)return;
    DWORD n=0;const WORD bom=0xFEFF;
    WriteFile(f,&bom,sizeof(bom),&n,nullptr);
    WriteFile(f,g_favFolder.c_str(),DWORD(g_favFolder.size()*sizeof(wchar_t)),&n,nullptr);
    CloseHandle(f);
}
void LoadFavoriteFolder() {
    std::wstring cfg=FavoritePathFile(); if(cfg.empty())return;
    HANDLE f=CreateFileW(cfg.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,
                         OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(f==INVALID_HANDLE_VALUE)return;
    DWORD size=GetFileSize(f,nullptr);
    if(size>2 && size<=MAX_PATH*sizeof(wchar_t) && size%2==0) {
        std::vector<wchar_t> buffer(size/sizeof(wchar_t)+1,0);
        DWORD n=0;
        if(ReadFile(f,buffer.data(),size,&n,nullptr) && n==size && buffer[0]==0xFEFF) {
            g_favFolder.assign(buffer.data()+1);
            DWORD attrs=GetFileAttributesW(g_favFolder.c_str());
            if(attrs==INVALID_FILE_ATTRIBUTES || !(attrs&FILE_ATTRIBUTE_DIRECTORY))
                g_favFolder.clear();
        }
    }
    CloseHandle(f);
}
void SelectFolder(HWND owner) {
    BROWSEINFOW bi{};
    bi.hwndOwner=owner;bi.lpszTitle=L"Selecciona la carpeta de destino de HOVER";
    bi.ulFlags=BIF_RETURNONLYFSDIRS|BIF_NEWDIALOGSTYLE;
    PIDLIST_ABSOLUTE pidl=SHBrowseForFolderW(&bi);
    if(!pidl)return;
    wchar_t path[MAX_PATH]{};
    if(SHGetPathFromIDListW(pidl,path)) {
        g_favFolder=path;
        SaveFavoriteFolder();
        OpenUrl(g_favFolder.c_str());
    }
    CoTaskMemFree(pidl);
}
void FavoriteFolder(HWND owner,bool force) {
    if(force || g_favFolder.empty()) SelectFolder(owner);
    else OpenUrl(g_favFolder.c_str());
}

// Drag & drop OLE de archivos de Explorer. Copia, nunca elimina el original.
// Conserva el nombre y renombra al producirse una colision.
int HitAction(float x,float y); // definido mas abajo
bool FavoriteFolderValid() {
    if(g_favFolder.empty())return false;
    DWORD attrs=GetFileAttributesW(g_favFolder.c_str());
    return attrs!=INVALID_FILE_ATTRIBUTES&&(attrs&FILE_ATTRIBUTE_DIRECTORY);
}
struct CopyJob {
    std::wstring folder;
    std::vector<std::wstring> files;
    HWND hwnd=nullptr;
};
DWORD WINAPI CopyFilesWorker(LPVOID argument) {
    std::unique_ptr<CopyJob> job(static_cast<CopyJob*>(argument));
    HRESULT com=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
    std::wstring from;
    for(const auto& path:job->files) {from+=path;from.push_back(L'\0');}
    from.push_back(L'\0');
    std::wstring to=job->folder;to.push_back(L'\0');to.push_back(L'\0');
    SHFILEOPSTRUCTW op{};
    op.wFunc=FO_COPY;
    op.pFrom=from.c_str();
    op.pTo=to.c_str();
    op.fFlags=FOF_NOCONFIRMATION|FOF_RENAMEONCOLLISION|
              FOF_NOCONFIRMMKDIR|FOF_NOERRORUI|FOF_SILENT;
    int result=SHFileOperationW(&op);
    if(job->hwnd)PostMessageW(job->hwnd,kFilesCopiedMessage,
                             result==0&&!op.fAnyOperationsAborted?1:0,
                             WPARAM(job->files.size()));
    if(SUCCEEDED(com))CoUninitialize();
    return 0;
}
void StartCopyToFavorite(HWND hwnd,const std::vector<std::wstring>& files) {
    if(files.empty()||!FavoriteFolderValid())return;
    std::unique_ptr<CopyJob> job(new CopyJob);
    job->folder=g_favFolder;job->files=files;job->hwnd=hwnd;
    // Limpia operaciones terminadas para no conservar handles innecesarios.
    for(size_t i=0;i<g_copyThreads.size();) {
        if(WaitForSingleObject(g_copyThreads[i],0)==WAIT_OBJECT_0) {
            CloseHandle(g_copyThreads[i]);g_copyThreads.erase(g_copyThreads.begin()+i);
        } else ++i;
    }
    HANDLE thread=CreateThread(nullptr,0,CopyFilesWorker,job.get(),0,nullptr);
    if(thread) {job.release();g_copyThreads.push_back(thread);}
    else {g_copyToastText=L"No se pudo iniciar la copia";
          g_copyToastUntil=GetTickCount64()+3500ULL;}
}
std::vector<std::wstring> DropFilePaths(HDROP hdrop) {
    std::vector<std::wstring> paths;
    UINT count=DragQueryFileW(hdrop,0xFFFFFFFF,nullptr,0);
    for(UINT i=0;i<count&&i<256;i++) {
        UINT len=DragQueryFileW(hdrop,i,nullptr,0);
        if(len==0||len>32760)continue;
        std::vector<wchar_t> text(len+2,0);
        if(DragQueryFileW(hdrop,i,text.data(),len+1))paths.emplace_back(text.data());
    }
    return paths;
}
class HoverFileDropTarget final : public IDropTarget {
    LONG refCount=1;
    HWND owner;
    bool hasFiles=false;
    static bool DragContainsFiles(IDataObject* data) {
        FORMATETC fmt{};
        fmt.cfFormat=CF_HDROP;fmt.dwAspect=DVASPECT_CONTENT;
        fmt.lindex=-1;fmt.tymed=TYMED_HGLOBAL;
        return data && SUCCEEDED(data->QueryGetData(&fmt));
    }
    void UpdateDropPoint(POINTL pt,DWORD* effect) {
        POINT pos{pt.x,pt.y};
        ScreenToClient(owner,&pos);
        g_dropHoverFolder=hasFiles&&FavoriteFolderValid()&&
                          HitAction(float(pos.x),float(pos.y))==204;
        if(effect)*effect=g_dropHoverFolder?DROPEFFECT_COPY:DROPEFFECT_NONE;
    }
public:
    explicit HoverFileDropTarget(HWND hwnd):owner(hwnd){}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void** out) override {
        if(!out)return E_POINTER;
        *out=nullptr;
        // Windhawk/Clang puede no enlazar automaticamente los IID globales de uuid.lib.
        // GUID locales: evita referencias externas a IID_IUnknown e IID_IDropTarget.
        static const GUID kUnknown = {
            0x00000000,0x0000,0x0000,{0xC0,0x00,0x00,0x00,0x00,0x00,0x00,0x46}
        };
        static const GUID kDropTarget = {
            0x00000122,0x0000,0x0000,{0xC0,0x00,0x00,0x00,0x00,0x00,0x00,0x46}
        };
        if(IsEqualGUID(id,kUnknown)||IsEqualGUID(id,kDropTarget)) {
            *out=static_cast<IDropTarget*>(this);
            AddRef();
            return S_OK;
        }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override {return ULONG(InterlockedIncrement(&refCount));}
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG n=ULONG(InterlockedDecrement(&refCount));if(!n)delete this;return n;
    }
    HRESULT STDMETHODCALLTYPE DragEnter(IDataObject* data,DWORD,POINTL pt,DWORD* effect) override {
        hasFiles=DragContainsFiles(data);
        g_fileDragActive=hasFiles;
        if(hasFiles){g_currentPage=3;g_previousPage=3;g_pageEase=1.0f;}
        UpdateDropPoint(pt,effect);
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE DragOver(DWORD,POINTL pt,DWORD* effect) override {
        UpdateDropPoint(pt,effect);return S_OK;
    }
    HRESULT STDMETHODCALLTYPE DragLeave() override {
        g_fileDragActive=false;g_dropHoverFolder=false;hasFiles=false;return S_OK;
    }
    HRESULT STDMETHODCALLTYPE Drop(IDataObject* data,DWORD,POINTL pt,DWORD* effect) override {
        UpdateDropPoint(pt,effect);
        if(!g_dropHoverFolder||!hasFiles||!data){DragLeave();return S_OK;}
        FORMATETC fmt{};fmt.cfFormat=CF_HDROP;fmt.dwAspect=DVASPECT_CONTENT;
        fmt.lindex=-1;fmt.tymed=TYMED_HGLOBAL;
        STGMEDIUM medium{};
        if(SUCCEEDED(data->GetData(&fmt,&medium))) {
            auto paths=DropFilePaths(reinterpret_cast<HDROP>(medium.hGlobal));
            StartCopyToFavorite(owner,paths);
            ReleaseStgMedium(&medium);
        }
        DragLeave();return S_OK;
    }
};

// The clipboard is read AFTER WM_CLIPBOARDUPDATE, on the UI timer, with retries.
// No keyboard hooks or network traffic are used.
bool TryReadClipboard() {
    if(!OpenClipboard(nullptr)) return false;
    std::wstring result;
    HANDLE h=GetClipboardData(CF_UNICODETEXT);
    if(h) {
        const wchar_t* p=static_cast<const wchar_t*>(GlobalLock(h));
        if(p) {
            for(int i=0;p[i]&&i<1000;i++){
                wchar_t c=p[i];
                result.push_back(c==L'\r'||c==L'\n'||c==L'\t'?L' ':c);
            }
            GlobalUnlock(h);
        }
    }
    if(result.empty()) {
        if(IsClipboardFormatAvailable(CF_HDROP)) result=L"Archivos o carpetas copiados";
        else if(IsClipboardFormatAvailable(CF_DIB)||IsClipboardFormatAvailable(CF_BITMAP)) result=L"Imagen copiada";
        else result=L"Contenido copiado (sin vista previa de texto)";
    }
    CloseClipboard();
    g_lastClip=result;
    g_clipTick=GetTickCount64();
    return true;
}


// Puente local opcional: %TEMP%\WindhawkIslandPremium\status.txt
// Compatible con el helper Python incluido en el ZIP. No usa red.
std::wstring BridgePath(const wchar_t* name) {
    wchar_t temp[MAX_PATH]{};
    DWORD len=GetTempPathW(MAX_PATH,temp);
    if(len==0||len>=MAX_PATH)return L"";
    std::wstring folder=std::wstring(temp)+L"WindhawkIslandPremium";
    CreateDirectoryW(folder.c_str(),nullptr);
    return folder+L"\\"+name;
}

std::wstring DecodeUtf8(const std::string& value) {
    if(value.empty())return L"";
    int size=MultiByteToWideChar(CP_UTF8,0,value.data(),int(value.size()),nullptr,0);
    if(size<=0)return L"";
    std::wstring result(size,L' ');
    MultiByteToWideChar(CP_UTF8,0,value.data(),int(value.size()),&result[0],size);
    return result;
}

void ChangePage(int page);

// HOVER voice UI uses only local UTF-8 text snapshots.  Never executes arbitrary
// text as shell commands, and ignores stale responses after starting Windhawk.
std::string ReadSmallFile(const wchar_t* filename, DWORD limit=8192) {
    std::wstring path=BridgePath(filename);
    HANDLE h=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|
        FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h==INVALID_HANDLE_VALUE)return "";
    std::vector<char> data(limit+1,0); DWORD n=0;
    BOOL ok=ReadFile(h,data.data(),limit,&n,nullptr);
    CloseHandle(h);
    return ok?std::string(data.data(),n):"";
}

void ReadVoiceTabs() {
    std::string blob=ReadSmallFile(L"voice_tabs.txt",4096);
    static std::string lastBlob;
    if(blob==lastBlob)return; // Evita reasignar vectores durante cada cuadro.
    lastBlob=blob;
    std::vector<VoiceTab> next;
    size_t pos=0;
    while(pos<blob.size() && next.size()<kMaxVoiceTabs){
        size_t end=blob.find('\n',pos);if(end==std::string::npos)end=blob.size();
        std::string line=blob.substr(pos,end-pos);
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        size_t mid=line.find('\t');
        if(mid!=std::string::npos){
            std::wstring title=DecodeUtf8(line.substr(0,mid));
            std::wstring url=DecodeUtf8(line.substr(mid+1));
            if(title.size()>40)title.resize(40);
            // Whitelist schemes to avoid executing commands from IPC files.
            if(!title.empty() && (url.empty() ||
                url.rfind(L"https://",0)==0 || url.rfind(L"http://",0)==0))
                next.push_back({title,url});
        }
        pos=end+1;
    }
    g_voiceTabs=std::move(next);
    int maxPage=kBuiltInPages+int(g_voiceTabs.size());
    if(g_currentPage>=maxPage){g_currentPage=maxPage-1;g_previousPage=g_currentPage;g_pageEase=1;}
    if(g_previousPage>=maxPage)g_previousPage=g_currentPage;
}

void ReadCalendarBridge() {
    // Read only local metadata written by Python. No OAuth tokens or network.
    std::string blob=ReadSmallFile(L"calendar_events.tsv",262144);
    static std::string previous;
    if(blob==previous)return;
    previous=blob;
    std::vector<CalendarEvent> next;
    std::wstring state=L"sin datos";
    size_t pos=0;
    while(pos<blob.size() && next.size()<250){
        size_t end=blob.find('\n',pos);
        if(end==std::string::npos)end=blob.size();
        std::string line=blob.substr(pos,end-pos);
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        size_t first=line.find('\t');
        if(first!=std::string::npos){
            std::string rawDate=line.substr(0,first);
            if(rawDate=="status"){
                state=DecodeUtf8(line.substr(first+1));
            } else {
                size_t second=line.find('\t',first+1);
                if(second!=std::string::npos && rawDate.size()==10) {
                    int yr=0,mo=0,dy=0;
                    if(std::sscanf(rawDate.c_str(),"%4d-%2d-%2d",&yr,&mo,&dy)==3 &&
                       yr>=2020 && yr<2100 && mo>=1 && mo<=12 && dy>=1 && dy<=31){
                        std::wstring title=DecodeUtf8(line.substr(first+1,second-first-1));
                        std::wstring url=DecodeUtf8(line.substr(second+1));
                        if(title.size()>95)title.resize(95);
                        if(url.rfind(L"https://calendar.google.com/",0)!=0)url.clear();
                        if(!title.empty())next.push_back({yr,mo,dy,title,url});
                    }
                }
            }
        }
        pos=end+1;
    }
    g_calendarStatus=state;
    g_calendarEvents=std::move(next);
    if(g_calendarSelectedIndex>=int(g_calendarEvents.size()))g_calendarSelectedIndex=0;
}

void VisibleCalendarMonth(int& year,int& month) {
    SYSTEMTIME st{};GetLocalTime(&st);
    int m=int(st.wMonth)-1+g_monthOffset;
    year=st.wYear;
    while(m<0){m+=12;--year;}
    while(m>=12){m-=12;++year;}
    month=m+1;
}

std::vector<const CalendarEvent*> DayEvents(int year,int month,int day) {
    std::vector<const CalendarEvent*> result;
    for(const auto& event:g_calendarEvents)
        if(event.year==year && event.month==month && event.day==day)
            result.push_back(&event);
    return result;
}

void ReadVoiceBridge() {
    std::string blob=ReadSmallFile(L"voice_ui.txt",2048);
    if(blob.empty())return;
    // serial\tmode\trequested_page\tmessage, with no tabs/newlines in values.
    size_t a=blob.find('\t');if(a==std::string::npos)return;
    size_t b=blob.find('\t',a+1);if(b==std::string::npos)return;
    size_t c=blob.find('\t',b+1);if(c==std::string::npos)return;
    std::string serial=blob.substr(0,a);
    if(serial==g_lastVoiceSerial)return;
    g_lastVoiceSerial=serial;
    std::string mode=blob.substr(a+1,b-a-1);
    // Voice updates are ALWAYS compact; no automatic page change, toast
    // enlargement, mouse-focus acquisition or animated opening.
    // Older mods also remain compact when Python sends "quiet-*".
    bool quiet=mode.rfind("quiet-",0)==0;
    if(quiet)mode=mode.substr(6);
    g_voiceState=DecodeUtf8(mode);
    g_voiceMessage=DecodeUtf8(blob.substr(c+1));
    if(g_voiceMessage.size()>115)g_voiceMessage.resize(115);
    ULONGLONG now=GetTickCount64();
    g_voiceNoticeUntil=0; // never trigger kToastHeight due to voice
    g_voiceExpandUntil=0; // no timed enlargement by voice
    g_voiceQuietUntil=(mode=="listening" || mode=="thinking")?now+1400:0;
    // Requested pages are intentionally ignored for voice events.
    // Only a user's mouse/touchpad can open or navigate the notch.

}

void ReadBridgeState() {
    const std::wstring path=BridgePath(L"status.txt");
    if(path.empty())return;
    WIN32_FILE_ATTRIBUTE_DATA info{};
    bool recent=false;
    if(GetFileAttributesExW(path.c_str(),GetFileExInfoStandard,&info)) {
        FILETIME current{};GetSystemTimeAsFileTime(&current);
        ULARGE_INTEGER a{},b{};
        a.LowPart=info.ftLastWriteTime.dwLowDateTime;
        a.HighPart=info.ftLastWriteTime.dwHighDateTime;
        b.LowPart=current.dwLowDateTime;
        b.HighPart=current.dwHighDateTime;
        recent=b.QuadPart>=a.QuadPart && (b.QuadPart-a.QuadPart)<80'000'000ULL;
    }
    if(!recent) {
        if(g_bridgeOnline.exchange(false)) {
            std::lock_guard<std::mutex> lock(g_mediaGuard);
            g_media=MediaState{}; // No seguir mostrando una cancion antigua.
        }
        return;
    }
    HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                            nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return;
    char buf[2048]{};DWORD size=0;
    BOOL ok=ReadFile(file,buf,sizeof(buf)-1,&size,nullptr);
    CloseHandle(file);
    if(!ok||!size)return;
    std::string text(buf,size);
    MediaState next;
    size_t pos=0;
    while(pos<text.size()) {
        size_t end=text.find('\n',pos);
        if(end==std::string::npos)end=text.size();
        std::string line=text.substr(pos,end-pos);
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        size_t eq=line.find('=');
        if(eq!=std::string::npos) {
            std::string key=line.substr(0,eq),val=line.substr(eq+1);
            if(key=="spotify")next.spotify=val=="1";
            else if(key=="playing")next.playing=val=="1";
            else if(key=="shuffle")next.shuffle=val=="1";
            else if(key=="repeat")next.repeat=val=="1";
            else if(key=="title")next.title=DecodeUtf8(val);
            else if(key=="artist")next.artist=DecodeUtf8(val);
            else if(key=="source")next.source=DecodeUtf8(val);
            else if(key=="artwork")next.artwork=DecodeUtf8(val);
            else if(key=="progress") {
                try{next.progress=Clamp(std::stof(val),0,1);}catch(...){next.progress=-1;}
            }
        }
        pos=end+1;
    }
    g_bridgeOnline=true;
    std::lock_guard<std::mutex> lock(g_mediaGuard);
    g_media=next;
}

bool WriteBridgeCommand(const char* command) {
    if(!g_bridgeOnline)return false;
    std::wstring path=BridgePath(L"command.txt");
    if(path.empty())return false;
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                           nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    char content[100]{};
    unsigned long seq=++g_bridgeCommandSerial;
    int len=wsprintfA(content,"%lu:%s\n",seq,command);
    DWORD written=0;
    BOOL ok=WriteFile(file,content,DWORD(len),&written,nullptr);
    CloseHandle(file);
    return ok&&written==DWORD(len);
}

void Command(int id) {
    if(id==4) {SendMediaKey(VK_VOLUME_DOWN);return;}
    if(id==5) {SendMediaKey(VK_VOLUME_UP);return;}
    if(id==6) {SendMediaKey(VK_VOLUME_MUTE);return;}

    // Playback buttons now talk to the media bridge's currently selected
    // Windows session. No global Play/Pause, which could pause Chrome while
    // the user is asking to play Spotify.
    if(id==1||id==2||id==3) {
        MediaState state;
        {std::lock_guard<std::mutex> guard(g_mediaGuard);state=g_media;}
        if(g_bridgeOnline && state.spotify) {
            if(id==1)WriteBridgeCommand("play");
            if(id==2)WriteBridgeCommand("prev");
            if(id==3)WriteBridgeCommand("next");
            return;
        }
        // If Spotify has no media session yet, opening the app is the only
        // supported non-destructive action. Never toggle Chrome or another
        // media player when the user clicked the Spotify Play button.
        if(id==1)OpenSpotify();
        return;
    }
    if(id==7 && g_bridgeOnline)WriteBridgeCommand("shuffle");

}

void ClockText(wchar_t (&text)[32]) {
    SYSTEMTIME st{};GetLocalTime(&st);
    if(g_24h) swprintf(text,32,L"%02d:%02d",int(st.wHour),int(st.wMinute));
    else {
        int hour=st.wHour%12;if(hour==0)hour=12;
        swprintf(text,32,L"%d:%02d %ls",hour,int(st.wMinute),st.wHour>=12?L"PM":L"AM");
    }
}

// Dos ojos (sin cara ni aureola): parte blanca e iris del acento de Windows.
// El globo ocular se desplaza un poco y el iris se desplaza mas, sin salirse.
void DrawEyes(Graphics& g,float cx) {
    // Eyes are a little closer while preserving the original look and blink.
    auto saved=g.Save();
    // Larger, smoothly expanding eyes (up to 75% larger in the panel).
    const float opening=Clamp(g_open,0.0f,1.0f);
    const float smooth=opening*opening*(3.0f-2.0f*opening);
    const float scale=1.0f+0.75f*smooth;
    const float anchorY=23.2f;
    g.TranslateTransform(cx,anchorY);
    g.ScaleTransform(scale,scale);
    g.TranslateTransform(-cx,-anchorY);
    Color accent=PupilColor();
    const BYTE ar=accent.GetR(), ag=accent.GetG(), ab=accent.GetB();
    const float phase=float(GetTickCount64()%5700ULL);
    const bool voiceListening=g_voiceState==L"listening" &&
                              GetTickCount64()<g_voiceQuietUntil;
    float blink=1.0f;
    if(phase<195.0f) blink=1.0f-0.94f*std::sin(3.14159265f*phase/195.0f);
    const float cy=23.2f;
    for(int i=0;i<2;i++) {
        const float eyeCenter=cx+(i==0?-14.2f:14.2f);
        const float ex=eyeCenter+g_eyeX*0.30f;
        const float ey=cy+g_eyeY*0.27f;
        const float breathing=voiceListening?
            1.0f+0.035f*std::sin(float(GetTickCount64()%1000ULL)*0.0062831853f):1.0f;
        const float height=17.0f*blink*breathing+0.35f;
        SolidBrush white(Color(255,253,254,255));
        g.FillEllipse(&white,ex-5.4f,ey-height*0.5f,10.8f,height);
        if(blink>0.26f) {
            // Limita la trayectoria del iris al interior de la zona blanca.
            const float px=ex+Clamp(g_eyeX*0.69f,-2.20f,2.20f);
            const float py=ey+Clamp(g_eyeY*0.70f,-3.20f,3.20f);
            SolidBrush iris(Color(255,ar,ag,ab));
            g.FillEllipse(&iris,px-2.15f,py-3.05f,4.30f,6.10f);
            SolidBrush pupil(Color(255,10,14,22));
            g.FillEllipse(&pupil,px-1.13f,py-1.75f,2.26f,3.50f);
            SolidBrush glint(Color(248,255,255,255));
            g.FillEllipse(&glint,px-1.25f,py-2.05f,0.80f,0.90f);
        }
    }
    g.Restore(saved);
}

// Cinco puntos verticales; el punto activo se estira y todos se animan.
void DrawPageDots(Graphics& g) {
    Color ac=Accent();
    const float cx=527.0f;
    const float p=g_pageEase*g_pageEase*(3.0f-2.0f*g_pageEase);
    int n=kBuiltInPages+int(g_voiceTabs.size());
    const float spacing=n>1?std::min(45.0f,220.0f/float(n-1)):45.0f;
    for(int i=0;i<n;i++) {
        const float prev=i==g_previousPage?1.0f:0.0f;
        const float target=i==g_currentPage?1.0f:0.0f;
        const float amount=g_pageEase<1.0f?prev+(target-prev)*p:target;
        const float height=5.0f+12.0f*amount;
        const float width=4.5f+2.0f*amount;
        const float cy=121.0f+float(i)*spacing;
        Color fill(BYTE(95+int(155.0f*amount)),
                  BYTE(145.0f+(float(ac.GetR())-145.0f)*amount),
                  BYTE(151.0f+(float(ac.GetG())-151.0f)*amount),
                  BYTE(159.0f+(float(ac.GetB())-159.0f)*amount));
        Round(g,cx-width*0.5f,cy-height*0.5f,width,height,width*0.5f,fill,Color(0,0,0,0),0.0f);
    }
}

void Button(Graphics& g,float x,float y,float w,float h,const wchar_t* label,
            int hot,int id,bool selected=false) {
    Color a=Accent();
    bool hover=g_hoverAction==id;
    BYTE rr=a.GetR(),gg=a.GetG(),bb=a.GetB();
    Round(g,x,y,w,h,15,
          hover?Color(185,BYTE(rr*0.32f+25),BYTE(gg*0.32f+25),BYTE(bb*0.32f+25)):
                (selected?Color(165,BYTE(rr*0.30f+24),BYTE(gg*0.30f+24),BYTE(bb*0.30f+24)):
                          Color(154,29,32,43)),
          Color(0,0,0,0),0.0f);
    Text(g,label,x+5,y,w-10,h,hot?15.0f:13.0f,Color(255,246,247,251),hot,true);
}

// Reproductor estilo Spotify: iconos mas cercanos a la interfaz original.
void DrawShuffleIcon(Graphics& g,float cx,float cy,bool active) {
    Color a=Accent();
    Color c=active?Color(255,a.GetR(),a.GetG(),a.GetB()):Color(240,221,225,235);
    Pen p(c,2.1f); p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
    g.DrawLine(&p,cx-10.0f,cy-8.0f,cx-2.0f,cy-8.0f);
    g.DrawLine(&p,cx-2.0f,cy-8.0f,cx+7.0f,cy+7.0f);
    g.DrawLine(&p,cx-10.0f,cy+8.0f,cx-2.0f,cy+8.0f);
    g.DrawLine(&p,cx-2.0f,cy+8.0f,cx+2.0f,cy+1.5f);
    PointF t1[] = {PointF(cx+7.0f,cy+7.0f),PointF(cx+3.0f,cy+2.8f),PointF(cx+9.8f,cy+2.5f)};
    PointF t2[] = {PointF(cx+10.0f,cy-8.0f),PointF(cx+3.5f,cy-8.2f),PointF(cx+7.2f,cy-3.5f)};
    SolidBrush b(c); g.FillPolygon(&b,t1,3); g.FillPolygon(&b,t2,3);
}
void DrawPrevNextIcon(Graphics& g,float cx,float cy,bool next) {
    SolidBrush b(Color(245,236,239,245));
    if(next) {
        PointF t1[] = {PointF(cx-8.0f,cy-9.0f),PointF(cx+2.0f,cy),PointF(cx-8.0f,cy+9.0f)};
        PointF t2[] = {PointF(cx+1.0f,cy-9.0f),PointF(cx+11.0f,cy),PointF(cx+1.0f,cy+9.0f)};
        g.FillPolygon(&b,t1,3); g.FillPolygon(&b,t2,3);
    } else {
        PointF t1[] = {PointF(cx+8.0f,cy-9.0f),PointF(cx-2.0f,cy),PointF(cx+8.0f,cy+9.0f)};
        PointF t2[] = {PointF(cx-1.0f,cy-9.0f),PointF(cx-11.0f,cy),PointF(cx-1.0f,cy+9.0f)};
        g.FillPolygon(&b,t1,3); g.FillPolygon(&b,t2,3);
    }
}
void DrawPlayPauseButton(Graphics& g,float cx,float cy,bool playing) {
    SolidBrush plate(Color(255,245,247,251));
    g.FillEllipse(&plate,cx-28.0f,cy-28.0f,56.0f,56.0f);
    SolidBrush ink(Color(255,10,14,20));
    if(playing) {
        g.FillRectangle(&ink,RectF(cx-9.0f,cy-11.0f,6.0f,22.0f));
        g.FillRectangle(&ink,RectF(cx+3.0f,cy-11.0f,6.0f,22.0f));
    } else {
        PointF tri[] = {PointF(cx-7.0f,cy-12.0f),PointF(cx+13.0f,cy),PointF(cx-7.0f,cy+12.0f)};
        g.FillPolygon(&ink,tri,3);
    }
}
void DrawQueueIcon(Graphics& g,float cx,float cy,bool active) {
    Color a=Accent();
    Color c=active?Color(255,a.GetR(),a.GetG(),a.GetB()):Color(240,221,225,235);
    Pen p(c,2.0f); p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
    g.DrawLine(&p,cx-10.0f,cy-8.0f,cx+5.0f,cy-8.0f);
    g.DrawLine(&p,cx-10.0f,cy-1.0f,cx+5.0f,cy-1.0f);
    g.DrawLine(&p,cx-10.0f,cy+6.0f,cx-1.0f,cy+6.0f);
    PointF tri[] = {PointF(cx+1.0f,cy+2.0f),PointF(cx+10.0f,cy+6.0f),PointF(cx+1.0f,cy+10.0f)};
    SolidBrush b(c); g.FillPolygon(&b,tri,3);
}
// El puente escribe archivos locales con nombre fijo por hash para evitar
// bloquear una caratula que esta siendo reemplazada por Windows.
void RefreshCoverIfNeeded(const std::wstring& name) {
    // The bridge writes status and artwork separately. If the image is not
    // ready on the first render, do NOT cache failure forever.
    if(name==g_currentCoverName && g_albumCover)return;
    if(name!=g_currentCoverName){
        g_albumCover.reset();
        g_currentCoverName=name;
    }
    if(name.empty() || name.find(L"..")!=std::wstring::npos ||
       name.find(L'\\')!=std::wstring::npos || name.find(L'/')!=std::wstring::npos)
        return;
    const std::wstring path=BridgePath(name.c_str());
    if(path.empty())return;
    // Avoid excessive GDI+ file opens while the status references an image
    // that has not yet been flushed by the Python media bridge.
    static ULONGLONG lastAttempt=0;
    const ULONGLONG tick=GetTickCount64();
    if(tick-lastAttempt<500)return;
    lastAttempt=tick;
    std::unique_ptr<Bitmap> candidate(new Bitmap(path.c_str()));
    if(candidate->GetLastStatus()==Ok && candidate->GetWidth()>0 && candidate->GetHeight()>0)
        g_albumCover=std::move(candidate);
}

void DrawMiniSpectrum(Graphics& g,float x,float y,bool playing) {
    const Color a=Accent();
    const float seconds=float(GetTickCount64()%120000ULL)/1000.0f;
    SolidBrush bg(Color(255,24,27,34));
    g.FillEllipse(&bg,x,y,78.0f,78.0f);
    for(int i=0;i<8;i++) {
        const float phase=seconds*(3.0f+0.13f*i)+float(i)*1.48f;
        const float swing=playing?(0.5f+0.5f*std::sin(phase)):0.10f;
        const float h=playing?(7.0f+37.0f*swing):5.0f;
        const float bx=x+11.0f+float(i)*7.3f;
        const BYTE alpha=BYTE(125+int(120.0f*swing));
        SolidBrush bar(Color(alpha,a.GetR(),a.GetG(),a.GetB()));
        g.FillRectangle(&bar,RectF(bx,y+39.0f-h*0.5f,4.0f,h));
    }
}

void PageMusic(Graphics& g) {
    MediaState m;
    {std::lock_guard<std::mutex> lock(g_mediaGuard);m=g_media;}
    Color ac=Accent();
    Round(g,17,112,502,231,22,Color(231,17,19,26),Color(0,0,0,0),0.0f);
    // Caratula real, cuando el puente local puede leerla. Si no, espectro vivo.
    RefreshCoverIfNeeded(m.artwork);
    if(g_albumCover) {
        GraphicsPath clip; const float x=38.0f,y=134.0f,w=78.0f,h=78.0f;
        clip.AddEllipse(x,y,w,h);
        auto state=g.Save();g.SetClip(&clip);
        g.DrawImage(g_albumCover.get(),RectF(x,y,w,h),0.0f,0.0f,
                    float(g_albumCover->GetWidth()),float(g_albumCover->GetHeight()),UnitPixel);
        g.Restore(state);
    } else DrawMiniSpectrum(g,38.0f,134.0f,m.playing);
    bool hasMedia = !m.title.empty() || !m.artist.empty();
    if(m.playing) {
        const float t=float(GetTickCount64()%3000ULL)/3000.0f*6.283185f;
        for(int i=0;i<3;i++) {
            const float bh=3.0f+5.0f*(0.5f+0.5f*std::sin(t*3.0f+float(i)*1.8f));
            SolidBrush dot(Color(240,ac.GetR(),ac.GetG(),ac.GetB()));
            g.FillRectangle(&dot,RectF(128.0f+float(i)*4.0f,147.0f-bh,2.2f,bh));
        }
    }
    Text(g,hasMedia?(m.spotify?L"SPOTIFY" : (m.source.empty()?L"MEDIA DEL SISTEMA":m.source)):
             (g_bridgeOnline?L"ESPERANDO METADATOS" : L"REPRODUCTOR MULTIMEDIA"),
         138,132,362,18,10.5f,Color(255,157,216,177),true);
    Text(g,hasMedia?m.title:L"Sin cancion detectada",138,154,362,30,18.0f,Color(255,247,248,251),true);
    Text(g,hasMedia?(m.artist.empty()?L"Artista no disponible":m.artist):
         (g_bridgeOnline?L"Selecciona una cancion en Spotify para mostrarla aqui":L"Inicia HOVER para conectar portada y controles"),
         138,185,360,28,11.8f,Color(235,187,191,202),false,false,true);
    SolidBrush track(Color(175,67,72,81));
    g.FillRectangle(&track,RectF(37.0f,226.0f,462.0f,3.0f));
    if(m.progress>=0.0f) {
        SolidBrush progress(Color(255,ac.GetR(),ac.GetG(),ac.GetB()));
        g.FillRectangle(&progress,RectF(37.0f,226.0f,462.0f*m.progress,3.0f));
    }
    // Smooth visual feedback: hover breathes, clicks draw a fading ripple
    // for ~650ms. No enlargement or popup outside the music page.
    const float centers[]={157.0f,213.0f,268.0f,323.0f,379.0f};
    const int actions[]={107,102,101,103,108};
    for(int i=0;i<5;i++) {
        bool hot=g_hoverAction==actions[i];
        const ULONGLONG tick=GetTickCount64();
        bool pushed=g_feedbackAction==actions[i] && tick<g_feedbackUntil;
        if(hot || pushed) {
            float breath=0.5f+0.5f*std::sin(float(tick%1300)*0.004833219f);
            BYTE alpha=BYTE(pushed?185:65+int(30.0f*breath));
            SolidBrush highlight(Color(alpha,35,43,57));
            float size=hot?48.0f+2.0f*breath:46.0f;
            g.FillEllipse(&highlight,centers[i]-size*0.5f,
                          279.0f-size*0.5f,size,size);
        }
        if(pushed) {
            float t=1.0f-float(g_feedbackUntil-tick)/650.0f;
            float radius=20.0f+15.0f*t;
            const BYTE fade=BYTE(190.0f*(1.0f-t));
            Pen ripple(Color(fade,ac.GetR(),ac.GetG(),ac.GetB()),1.6f);
            g.DrawEllipse(&ripple,centers[i]-radius,279.0f-radius,
                          radius*2.0f,radius*2.0f);
        }
    }
    DrawShuffleIcon(g,157.0f,279.0f,m.shuffle);
    DrawPrevNextIcon(g,213.0f,279.0f,false);
    DrawPlayPauseButton(g,268.0f,279.0f,m.playing);
    DrawPrevNextIcon(g,323.0f,279.0f,true);
    DrawQueueIcon(g,379.0f,279.0f,false);
    Text(g,L"VOL",35,317,35,18,10,Color(240,165,171,182),true);
    Button(g,73,310,42,30,L"−",true,104);
    Button(g,122,310,42,30,L"+",true,105);
    Button(g,172,310,93,30,L"SILENCIO",false,106);
    Text(g,g_bridgeOnline?(m.spotify?L"SPOTIFY · CONECTADO":L"SPOTIFY SIN SESION"):
         L"PUENTE SIN CONEXION",320,311,190,27,10.0f,
         Color(205,184,194,208),false,true);
}

void PageCopies(Graphics& g) {
    Color ac=Accent();
    Text(g,L"Lo que vas a pegar",20,113,455,29,19,Color(255,246,247,250),true);
    Text(g,L"Vista previa local del ultimo contenido copiado",20,141,466,19,11,Color(222,183,187,202));
    Round(g,18,172,500,126,19,Color(200,20,23,31),Color(0,0,0,0),0.0f);
    Text(g,g_lastClip.empty()?L"Copia algo con Ctrl+C para verlo aqui.":g_lastClip,
         33,186,468,97,15,Color(255,242,244,250),false,false,true);
    Text(g,L"No guarda historial ni envia contenido a internet.",24,310,488,26,11,Color(212,173,177,191));
}

int MonthDays(int year,int mon) {
    if(mon==2) return ((year%4==0 && year%100!=0)||year%400==0)?29:28;
    if(mon==4||mon==6||mon==9||mon==11)return 30;
    return 31;
}
void PageCalendar(Graphics& g) {
    static const wchar_t* months[]={L"ENERO",L"FEBRERO",L"MARZO",L"ABRIL",L"MAYO",L"JUNIO",L"JULIO",L"AGOSTO",L"SEPTIEMBRE",L"OCTUBRE",L"NOVIEMBRE",L"DICIEMBRE"};
    static const wchar_t* weekdays[]={L"LU",L"MA",L"MI",L"JU",L"VI",L"SA",L"DO"};
    SYSTEMTIME st{};GetLocalTime(&st);
    int year=0,month=0;
    VisibleCalendarMonth(year,month);
    int mo=month-1;
    SYSTEMTIME first{};first.wYear=WORD(year);first.wMonth=WORD(month);first.wDay=1;
    FILETIME ft{};
    if(SystemTimeToFileTime(&first,&ft))FileTimeToSystemTime(&ft,&first);
    int offset=(int(first.wDayOfWeek)+6)%7;
    Color ac=Accent();
    Round(g,17,114,502,223,21,Color(200,19,22,31),Color(0,0,0,0),0.0f);
    wchar_t monthTitle[80]{};swprintf(monthTitle,80,L"%ls  %d",months[mo],year);
    Text(g,monthTitle,33,123,278,27,18,Color(255,248,248,252),true);
    Button(g,306,119,96,36,L"+ NUEVO",true,654);
    Button(g,407,119,43,36,L"<",true,401);
    Button(g,459,119,43,36,L">",true,402);
    for(int col=0;col<7;col++) Text(g,weekdays[col],36+col*68,159,53,20,11,Color(230,165,169,182),true,true);
    const int days=MonthDays(year,month);
    for(int day=1;day<=days;day++){
        int cell=offset+day-1,col=cell%7,row=cell/7;
        float x=36+col*68,y=184+row*25;
        wchar_t number[8]{};swprintf(number,8,L"%d",day);
        bool today=day==st.wDay&&month==st.wMonth&&year==st.wYear;
        if(today)Round(g,x+8,y+1,37,22,11,Color(230,ac.GetR(),ac.GetG(),ac.GetB()),Color(40,255,255,255));
        Text(g,number,x,y,53,24,12,today?Color(255,5,7,10):Color(255,231,233,241),today,true);
        if(!DayEvents(year,month,day).empty()){
            SolidBrush eventMark(Color(245,ac.GetR(),ac.GetG(),ac.GetB()));
            g.FillEllipse(&eventMark,x+24.0f,y+21.0f,4.5f,4.5f);
        }
    }
    // Only user clicks open details; Calendar never expands the notch itself.
    if(g_calendarDetailsOpen && g_calendarSelectedDay>0){
        auto dayEvents=DayEvents(year,month,g_calendarSelectedDay);
        Round(g,32,228,471,105,15,Color(251,34,37,47),
              Color(105,165,175,188),1.0f);
        wchar_t selected[60]{};
        swprintf(selected,60,L"%d/%d/%d",g_calendarSelectedDay,month,year);
        Text(g,selected,46,235,190,18,12,Color(245,242,245,249),true);
        if(dayEvents.empty()){
            Text(g,g_calendarStatus==L"ok"?L"Sin eventos este dia":
                 L"Conecta Calendar en Atajos para cargar tus eventos",
                 46,259,425,23,12,Color(245,201,207,218),false,false,true);
        } else {
            if(g_calendarSelectedIndex>=int(dayEvents.size()))g_calendarSelectedIndex=0;
            const auto& event=*dayEvents[g_calendarSelectedIndex];
            Text(g,event.title,46,255,444,26,14,Color(255,243,247,252),true);
            wchar_t count[55]{};
            swprintf(count,55,L"Evento %d de %d",g_calendarSelectedIndex+1,
                     int(dayEvents.size()));
            Text(g,count,46,287,164,20,10.5f,Color(200,195,205,220));
            if(!event.url.empty())
                Button(g,319,289,121,32,L"ABRIR",true,650);
            if(dayEvents.size()>1)Button(g,229,289,77,32,L"SIG.",true,653);
        }
        Button(g,450,236,41,30,L"X",true,652);
    }
}

// Six cards inspired by the reference video, with live Windows measurements.
void HardwareTile(Graphics& g,float x,float y,float w,float h,const wchar_t* label,
                  const wchar_t* value,float percent,int symbol) {
    Color a=Accent();
    Round(g,x,y,w,h,15.0f,Color(198,28,31,42),Color(0,0,0,0));
    Color ink(245,239,241,248);
    Color accent(255,a.GetR(),a.GetG(),a.GetB());
    Pen iconPen(accent,1.7f);
    iconPen.SetStartCap(LineCapRound);iconPen.SetEndCap(LineCapRound);
    const float ix=x+13.0f,iy=y+13.0f;
    if(symbol==0) { // CPU chip
        g.DrawRectangle(&iconPen,ix+2.0f,iy+2.0f,12.0f,12.0f);
        for(int i=0;i<3;i++){
            float a0=ix+4.0f+i*4.0f;
            g.DrawLine(&iconPen,a0,iy,a0,iy+2.0f);g.DrawLine(&iconPen,a0,iy+14.0f,a0,iy+16.0f);
        }
    } else if(symbol==1){ // Upload
        g.DrawLine(&iconPen,ix+8.0f,iy+15.0f,ix+8.0f,iy+1.0f);
        g.DrawLine(&iconPen,ix+3.0f,iy+6.0f,ix+8.0f,iy+1.0f);
        g.DrawLine(&iconPen,ix+8.0f,iy+1.0f,ix+13.0f,iy+6.0f);
    } else if(symbol==2){ // RAM module
        g.DrawRectangle(&iconPen,ix,iy+4.0f,18.0f,10.0f);
        for(int i=0;i<4;i++)g.DrawLine(&iconPen,ix+3.0f+i*4.0f,iy+6.0f,ix+3.0f+i*4.0f,iy+11.0f);
    } else if(symbol==3){ // Download
        g.DrawLine(&iconPen,ix+8.0f,iy,ix+8.0f,iy+15.0f);
        g.DrawLine(&iconPen,ix+3.0f,iy+10.0f,ix+8.0f,iy+15.0f);
        g.DrawLine(&iconPen,ix+8.0f,iy+15.0f,ix+13.0f,iy+10.0f);
    } else if(symbol==4){ // GPU chip
        g.DrawRectangle(&iconPen,ix,iy+2.0f,18.0f,13.0f);
        g.DrawEllipse(&iconPen,ix+6.0f,iy+5.0f,7.0f,7.0f);
    } else if(symbol==5){ // Disk stack
        g.DrawEllipse(&iconPen,ix+1.0f,iy+2.0f,17.0f,6.0f);
        g.DrawArc(&iconPen,ix+1.0f,iy+7.0f,17.0f,7.0f,0.0f,180.0f);
        g.DrawLine(&iconPen,ix+1.0f,iy+5.0f,ix+1.0f,iy+11.0f);
        g.DrawLine(&iconPen,ix+18.0f,iy+5.0f,ix+18.0f,iy+11.0f);
    }
    Text(g,label,x+43.0f,y+7.0f,w-54.0f,17.0f,10.4f,Color(205,184,194,214),true);
    Text(g,value,x+43.0f,y+23.0f,w-54.0f,22.0f,16.2f,ink,true);
    SolidBrush track(Color(115,66,72,82));
    g.FillRectangle(&track,RectF(x+13.0f,y+h-9.0f,w-26.0f,3.0f));
    if(percent>=0.0f){
        SolidBrush progress(accent);
        g.FillRectangle(&progress,RectF(x+13.0f,y+h-9.0f,(w-26.0f)*Clamp(percent/100.0f,0.0f,1.0f),3.0f));
    }
}
void PageHardware(Graphics& g) {
    Text(g,L"Monitor de hardware",20,106,480,26,17.0f,Color(255,245,246,251),true);
    HardwareState h=g_hw;
    wchar_t cpu[64]{},ram[64]{},gpu[64]{},up[64]{},down[64]{},disk[64]{};
    if(h.cpu>=0)swprintf(cpu,64,L"%.0f%%",double(h.cpu));else wcscpy(cpu,L"N/D");
    if(h.ram>=0)swprintf(ram,64,L"%.1f / %.1f GB",h.usedRamGiB,h.totalRamGiB);else wcscpy(ram,L"N/D");
    if(h.gpu>=0)swprintf(gpu,64,L"%.0f%%",double(h.gpu));else wcscpy(gpu,L"N/D");
    if(h.netUp>=0)swprintf(up,64,L"%.1f Mbps",h.netUp);else wcscpy(up,L"N/D");
    if(h.netDown>=0)swprintf(down,64,L"%.1f Mbps",h.netDown);else wcscpy(down,L"N/D");
    if(h.disk>=0)swprintf(disk,64,L"%.0f%% usado",double(h.disk));else wcscpy(disk,L"N/D");
    const float x1=17.0f,x2=273.0f,w=245.0f,height=62.0f;
    HardwareTile(g,x1,140.0f,w,height,L"CPU",cpu,h.cpu,0);
    HardwareTile(g,x2,140.0f,w,height,L"NET UP",up,-1.0f,1);
    HardwareTile(g,x1,208.0f,w,height,L"RAM",ram,h.ram,2);
    HardwareTile(g,x2,208.0f,w,height,L"NET DOWN",down,-1.0f,3);
    HardwareTile(g,x1,276.0f,w,height,L"GPU",gpu,h.gpu,4);
    HardwareTile(g,x2,276.0f,w,height,L"DISCO SISTEMA",disk,h.disk,5);
}

// Ocho iconos vectoriales propios: no dependen de fuentes ni pictogramas externos.
void ShortcutIcon(Graphics& g,int type,float x,float y) {
    Color accent=Accent();
    Color ink(250,236,242,249);
    Pen p(ink,2.0f);
    p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
    p.SetLineJoin(LineJoinRound);
    SolidBrush fill(ink);
    SolidBrush tint(Color(230,accent.GetR(),accent.GetG(),accent.GetB()));
    switch(type) {
      case 0: { // chat: burbuja
        g.DrawArc(&p,x+3.0f,y+3.0f,21.0f,18.0f,190.0f,328.0f);
        g.DrawLine(&p,x+8.0f,y+20.0f,x+6.0f,y+25.0f);
        g.DrawLine(&p,x+6.0f,y+25.0f,x+13.0f,y+21.0f);
        g.FillEllipse(&tint,x+9.0f,y+11.0f,2.7f,2.7f);
        g.FillEllipse(&tint,x+15.5f,y+11.0f,2.7f,2.7f);
        break;
      }
      case 1: { // chispa cuatro puntas
        PointF star[]={PointF(x+14.0f,y+2.0f),PointF(x+17.2f,y+10.8f),
          PointF(x+26.0f,y+14.0f),PointF(x+17.2f,y+17.2f),
          PointF(x+14.0f,y+26.0f),PointF(x+10.8f,y+17.2f),
          PointF(x+2.0f,y+14.0f),PointF(x+10.8f,y+10.8f)};
        g.DrawPolygon(&p,star,8);break;
      }
      case 2: { // nota musical
        g.DrawLine(&p,x+12.0f,y+6.0f,x+12.0f,y+22.0f);
        g.DrawLine(&p,x+12.0f,y+6.0f,x+24.0f,y+3.0f);
        g.DrawLine(&p,x+24.0f,y+3.0f,x+24.0f,y+19.0f);
        g.FillEllipse(&fill,x+5.0f,y+18.0f,9.0f,6.0f);
        g.FillEllipse(&fill,x+17.0f,y+15.0f,9.0f,6.0f);break;
      }
      case 3: { // captura: cuatro esquinas y punto central
        g.DrawLine(&p,x+3.0f,y+10.0f,x+3.0f,y+3.0f);
        g.DrawLine(&p,x+3.0f,y+3.0f,x+10.0f,y+3.0f);
        g.DrawLine(&p,x+18.0f,y+3.0f,x+25.0f,y+3.0f);
        g.DrawLine(&p,x+25.0f,y+3.0f,x+25.0f,y+10.0f);
        g.DrawLine(&p,x+3.0f,y+18.0f,x+3.0f,y+25.0f);
        g.DrawLine(&p,x+3.0f,y+25.0f,x+10.0f,y+25.0f);
        g.DrawLine(&p,x+18.0f,y+25.0f,x+25.0f,y+25.0f);
        g.DrawLine(&p,x+25.0f,y+25.0f,x+25.0f,y+18.0f);
        g.FillEllipse(&tint,x+11.0f,y+11.0f,6.0f,6.0f);break;
      }
      case 4: { // carpeta
        PointF folder[]={PointF(x+3.0f,y+7.0f),PointF(x+11.0f,y+7.0f),
          PointF(x+14.0f,y+10.0f),PointF(x+25.0f,y+10.0f),
          PointF(x+25.0f,y+23.0f),PointF(x+3.0f,y+23.0f)};
        g.DrawPolygon(&p,folder,6);break;
      }
      case 5: { // explorador de archivos
        g.DrawRectangle(&p,x+3.0f,y+4.0f,22.0f,21.0f);
        g.DrawLine(&p,x+3.0f,y+10.0f,x+25.0f,y+10.0f);
        g.DrawLine(&p,x+15.0f,y+10.0f,x+15.0f,y+25.0f);
        g.FillEllipse(&tint,x+6.0f,y+6.0f,2.0f,2.0f);break;
      }
      case 6: { // engranaje esquematico
        g.DrawEllipse(&p,x+7.0f,y+7.0f,14.0f,14.0f);
        g.DrawEllipse(&p,x+11.0f,y+11.0f,6.0f,6.0f);
        for(int i=0;i<8;i++) {
          float a=float(i)*0.785398163f;
          float co=std::cos(a),si=std::sin(a);
          g.DrawLine(&p,x+14.0f+co*9.0f,y+14.0f+si*9.0f,
                         x+14.0f+co*12.0f,y+14.0f+si*12.0f);
        } break;
      }
      case 7: { // historial del portapapeles
        g.DrawRectangle(&p,x+5.0f,y+6.0f,18.0f,19.0f);
        g.DrawLine(&p,x+11.0f,y+3.0f,x+17.0f,y+3.0f);
        g.DrawLine(&p,x+11.0f,y+3.0f,x+11.0f,y+8.0f);
        g.DrawLine(&p,x+17.0f,y+3.0f,x+17.0f,y+8.0f);
        g.DrawLine(&p,x+10.0f,y+14.0f,x+19.0f,y+14.0f);
        g.DrawLine(&p,x+10.0f,y+19.0f,x+19.0f,y+19.0f);break;
      }
    }
}

void PageShortcuts(Graphics& g) {
    static const int shortcutIds[]={0,1,3,4,5,6};
    static const wchar_t* names[]={L"ChatGPT",L"Claude",L"Capturas",L"Carpeta",L"Archivos",L"Ajustes"};
    Color ac=Accent();
    for(int i=0;i<6;i++) {
        int col=i%3,row=i/3;
        float x=23.0f+col*164.0f,y=142.0f+row*96.0f;
        int id=shortcutIds[i];
        bool hot=g_hoverAction==(200+id);
        bool drop= id==4 && g_dropHoverFolder;
        Round(g,x,y,152.0f,86.0f,19.0f,
              drop?Color(238,44,74,60):(hot?Color(220,37,43,58):Color(178,24,28,37)),
              Color(0,0,0,0));
        Round(g,x+55.0f,y+8.0f,42.0f,42.0f,13.0f,
              drop?Color(165,ac.GetR(),ac.GetG(),ac.GetB()):
              Color(hot?110:58,ac.GetR(),ac.GetG(),ac.GetB()),
              Color(0,0,0,0),0.0f);
        ShortcutIcon(g,id,x+62.0f,y+15.0f);
        Text(g,names[i],x+7.0f,y+54.0f,138.0f,24.0f,12.0f,
             Color(255,242,245,250),hot||drop,true);
    }
    if(g_fileDragActive) {
        Text(g,FavoriteFolderValid()?L"Suelta sobre Carpeta para COPIAR":
               L"Primero configura la carpeta con clic derecho",26,332,490,15,11.0f,
             Color(230,ac.GetR(),ac.GetG(),ac.GetB()),false,true);
    } else {
        Round(g,24.0f,326.0f,478.0f,25.0f,9.0f,
              g_hoverAction==208?Color(210,43,52,57):Color(180,26,31,37),
              Color(0,0,0,0),0.0f);
        Text(g,L"GOOGLE  |  Conectar cuenta  /  Gestionar permisos",
             34,332,458,14,11.0f,
             Color(255,ac.GetR(),ac.GetG(),ac.GetB()),true,true);
    }
}

void PageVoiceTab(Graphics& g,int page) {
    const int idx=page-kBuiltInPages;
    if(idx<0 || idx>=int(g_voiceTabs.size()))return;
    const VoiceTab& tab=g_voiceTabs[idx];
    Color ac=Accent();
    Text(g,tab.title,29,134,470,38,22,Color(255,248,250,255),true);
    Text(g,L"PESTANA PERSONALIZADA",29,173,420,18,10.5f,
         Color(230,ac.GetR(),ac.GetG(),ac.GetB()),true);
    if(tab.url.empty()) {
        Text(g,L"Sin enlace configurado. Di: Oye Hover, configura pestana "
               L"[nombre] para abrir GitHub.",29,203,468,73,14,
               Color(230,208,212,222),false,false,true);
    } else {
        Round(g,27,205,470,70,18,Color(150,29,32,39),Color(0,0,0,0),0);
        Text(g,L"ABRIR ENLACE",46,214,422,22,12,Color(245,247,248,251),true);
        Text(g,tab.url,46,239,415,19,11,Color(205,175,186,198));
        Text(g,L"Pulsa la tarjeta para abrir en tu navegador.",29,294,470,20,11,
             Color(200,175,182,194));
    }
}

int HitAction(float x,float y) {
    if(g_open<0.76f)return -1;
    y+=kContentLift;
    if(g_currentPage==0){
        if(y>=248&&y<309){
            if(x>=133&&x<182)return 107;
            if(x>=187&&x<238)return 102;
            if(x>=239&&x<298)return 101;
            if(x>=299&&x<350)return 103;
            if(x>=351&&x<406)return 108;
        }
        if(y>=310&&y<342){
            if(x>=73&&x<115)return 104;
            if(x>=122&&x<164)return 105;
            if(x>=172&&x<265)return 106;
        }
    } else if(g_currentPage==2){
        if(g_calendarDetailsOpen){
            if(y>=236&&y<268&&x>=447&&x<495)return 652;
            if(y>=289&&y<324){
                if(x>=319&&x<445)return 650;
                if(x>=229&&x<309)return 653;
            }
            if(y>=228&&y<334&&x>=32&&x<503)return -1;
        }
        if(y>=119&&y<155){
            if(x>=306&&x<402)return 654;
            if(x>=407&&x<450)return 401;
            if(x>=459&&x<502)return 402;
        }
        if(y>=184&&y<334&&x>=36&&x<510){
            int year=0,month=0;VisibleCalendarMonth(year,month);
            SYSTEMTIME f{};f.wYear=WORD(year);f.wMonth=WORD(month);f.wDay=1;
            FILETIME stamp{};
            if(SystemTimeToFileTime(&f,&stamp))FileTimeToSystemTime(&stamp,&f);
            int offset=(int(f.wDayOfWeek)+6)%7;
            int row=int((y-184)/25),col=int((x-36)/68);
            if(col>=0&&col<7&&row>=0&&row<6){
                int day=row*7+col-offset+1;
                if(day>=1&&day<=MonthDays(year,month))return 600+day;
            }
        }
    } else if(g_currentPage==3) {
        if(y>=326.0f&&y<355.0f&&x>=24.0f&&x<502.0f)
            return 208;
        if(y>=142.0f&&y<324.0f) {
            int row=int((y-142.0f)/96.0f);
            int col=int((x-23.0f)/164.0f);
            if(col>=0&&col<3&&row>=0&&row<2) {
                float rx=23.0f+col*164.0f,ry=142.0f+row*96.0f;
                if(x>=rx&&x<rx+152.0f&&y>=ry&&y<ry+86.0f) {
                    static const int ids[]={0,1,3,4,5,6};
                    return 200+ids[row*3+col];
                }
            }
        }
    }
    if(g_currentPage>=kBuiltInPages && y>=205.0f&&y<275.0f && x>=27.0f&&x<498.0f)
        return 500+g_currentPage-kBuiltInPages;
    return -1;
}

void ChangePage(int page) {
    const int count=kBuiltInPages+int(g_voiceTabs.size());
    if(count<1)return;
    const int previous=g_currentPage;
    page=(page%count+count)%count;
    if(previous!=page) {
        int rawDelta=page-previous;
        if(rawDelta>count/2)rawDelta-=count;
        if(rawDelta<-count/2)rawDelta+=count;
        g_pageDirection=rawDelta<0?-1:1;
        g_previousPage=previous;
        g_currentPage=page;
        if(g_gestureDiagnostics)Wh_Log(L"HOVER: navegar pagina %d",page);
        g_pageEase=0.0f;
    }
}

// Administrador nativo de proyectos HOVER.
// Archivo compartido con el asistente Python: %LOCALAPPDATA%\HOVER_NEXT\projects.tsv.
// Nunca almacena contrasenas, cookies o tokens, solamente URLs HTTPS validadas.
constexpr wchar_t kProjectWindowClass[]=L"HOVERProjectManagerV45";
constexpr int kPmList=9401, kPmName=9402, kPmUrl=9403;
constexpr int kPmSave=9404, kPmOpen=9405, kPmDelete=9406;
constexpr int kPmPaste=9407, kPmClose=9408, kPmHome=9409;
struct ProjectLink {int provider=0;std::wstring name,url;};
std::vector<ProjectLink> g_projectLinks;
HWND g_projectWindow=nullptr,g_projectList=nullptr,g_projectName=nullptr,g_projectUrl=nullptr;
int g_projectProvider=0;

std::wstring ProjectStorePath() {
    wchar_t app[MAX_PATH]{};
    if(FAILED(SHGetFolderPathW(nullptr,CSIDL_LOCAL_APPDATA,nullptr,SHGFP_TYPE_CURRENT,app)))return L"";
    std::wstring folder=std::wstring(app)+L"\\HOVER_NEXT";
    CreateDirectoryW(folder.c_str(),nullptr);
    return folder+L"\\projects.tsv";
}
std::string ProjectUtf8(const std::wstring& input) {
    if(input.empty())return "";
    int n=WideCharToMultiByte(CP_UTF8,0,input.c_str(),int(input.size()),nullptr,0,nullptr,nullptr);
    if(n<=0)return "";
    std::string encoded(size_t(n),'\0');
    WideCharToMultiByte(CP_UTF8,0,input.c_str(),int(input.size()),&encoded[0],n,nullptr,nullptr);
    return encoded;
}
bool SafeProjectName(const std::wstring& name) {
    if(name.empty()||name.size()>40)return false;
    for(wchar_t c:name)if(c==L'\r'||c==L'\n'||c==L'\t'||c<32)return false;
    return true;
}
bool SafeProjectUrl(int provider,const std::wstring& url) {
    const std::wstring start=provider==0?L"https://chatgpt.com/g/g-p-":L"https://claude.ai/project/";
    if(url.size()<=start.size()||url.rfind(start,0)!=0||url.size()>1500)return false;
    for(wchar_t c:url)if(c<=32||c==L'<'||c==L'>'||c==L'"'||c==L'\\')return false;
    return true;
}
std::wstring ProjectEditText(HWND edit) {
    if(!edit)return L"";
    int n=GetWindowTextLengthW(edit);
    if(n<0||n>1600)return L"";
    std::wstring value(size_t(n)+1,L'\0');
    GetWindowTextW(edit,&value[0],n+1);
    value.resize(size_t(n));
    return value;
}
void ReadProjectLinks() {
    g_projectLinks.clear();
    const std::wstring path=ProjectStorePath();
    if(path.empty())return;
    HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                             nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return;
    DWORD size=GetFileSize(file,nullptr);
    if(size==INVALID_FILE_SIZE||size>32768){CloseHandle(file);return;}
    std::string data(size,'\0');DWORD read=0;
    bool ok=size==0||ReadFile(file,&data[0],size,&read,nullptr);
    CloseHandle(file);
    if(!ok)return;
    data.resize(read);
    size_t pos=0;
    while(pos<data.size()&&g_projectLinks.size()<48) {
        size_t end=data.find('\n',pos);
        if(end==std::string::npos)end=data.size();
        std::string line=data.substr(pos,end-pos);
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        size_t a=line.find('\t');
        size_t b=a==std::string::npos?std::string::npos:line.find('\t',a+1);
        if(a!=std::string::npos&&b!=std::string::npos) {
            std::string p=line.substr(0,a);
            int provider=p=="chatgpt"?0:p=="claude"?1:-1;
            std::wstring name=DecodeUtf8(line.substr(a+1,b-a-1));
            std::wstring url=DecodeUtf8(line.substr(b+1));
            if(provider>=0&&SafeProjectName(name)&&SafeProjectUrl(provider,url))
                g_projectLinks.push_back({provider,name,url});
        }
        pos=end+1;
    }
}
bool SaveProjectLinks() {
    const std::wstring path=ProjectStorePath();
    if(path.empty())return false;
    std::string data;
    for(const auto& entry:g_projectLinks) {
        if(!SafeProjectName(entry.name)||!SafeProjectUrl(entry.provider,entry.url))continue;
        data+=entry.provider==0?"chatgpt\t":"claude\t";
        data+=ProjectUtf8(entry.name)+"\t"+ProjectUtf8(entry.url)+"\n";
    }
    std::wstring temp=path+L".hover.tmp";
    HANDLE file=CreateFileW(temp.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    DWORD written=0;
    BOOL ok=WriteFile(file,data.data(),DWORD(data.size()),&written,nullptr);
    FlushFileBuffers(file);CloseHandle(file);
    if(!ok||written!=data.size()){DeleteFileW(temp.c_str());return false;}
    if(!MoveFileExW(temp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        DeleteFileW(temp.c_str());return false;
    }
    return true;
}
void RefreshProjectList() {
    if(!g_projectList)return;
    SendMessageW(g_projectList,LB_RESETCONTENT,0,0);
    for(size_t i=0;i<g_projectLinks.size();++i) {
        const auto& item=g_projectLinks[i];
        if(item.provider!=g_projectProvider)continue;
        LRESULT index=SendMessageW(g_projectList,LB_ADDSTRING,0,LPARAM(item.name.c_str()));
        if(index!=LB_ERR&&index!=LB_ERRSPACE)
            SendMessageW(g_projectList,LB_SETITEMDATA,WPARAM(index),LPARAM(i));
    }
}
int SelectedProjectIndex() {
    if(!g_projectList)return -1;
    LRESULT selected=SendMessageW(g_projectList,LB_GETCURSEL,0,0);
    if(selected==LB_ERR)return -1;
    LRESULT index=SendMessageW(g_projectList,LB_GETITEMDATA,WPARAM(selected),0);
    return index==LB_ERR||index<0||index>=LRESULT(g_projectLinks.size())?-1:int(index);
}
void PopulateSelectedProject() {
    int index=SelectedProjectIndex();
    if(index<0)return;
    SetWindowTextW(g_projectName,g_projectLinks[index].name.c_str());
    SetWindowTextW(g_projectUrl,g_projectLinks[index].url.c_str());
}
void PasteProjectUrl() {
    if(!OpenClipboard(g_projectWindow))return;
    HANDLE data=GetClipboardData(CF_UNICODETEXT);
    if(data) {
        const wchar_t* text=static_cast<const wchar_t*>(GlobalLock(data));
        if(text) {
            std::wstring url(text);
            GlobalUnlock(data);
            if(SafeProjectUrl(g_projectProvider,url))
                SetWindowTextW(g_projectUrl,url.c_str());
            else MessageBoxW(g_projectWindow,L"Copia la URL HTTPS del proyecto desde ChatGPT o Claude.",
                             L"Enlace no valido",MB_OK|MB_ICONWARNING);
        }
    }
    CloseClipboard();
}
HWND NewProjectControl(HWND owner,const wchar_t* klass,const wchar_t* text,
                       DWORD style,int x,int y,int w,int h,int id=0) {
    HWND control=CreateWindowExW(0,klass,text,style|WS_CHILD|WS_VISIBLE,x,y,w,h,owner,
                                 reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);
    if(control)SendMessageW(control,WM_SETFONT,WPARAM(GetStockObject(DEFAULT_GUI_FONT)),TRUE);
    return control;
}
LRESULT CALLBACK ProjectWindowProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp) {
    switch(msg) {
        case WM_COMMAND:{
            const int id=LOWORD(wp);
            if(id==kPmList&&HIWORD(wp)==LBN_SELCHANGE){PopulateSelectedProject();return 0;}
            if(HIWORD(wp)!=BN_CLICKED)return 0;
            if(id==kPmClose){DestroyWindow(hwnd);return 0;}
            if(id==kPmPaste){PasteProjectUrl();return 0;}
            if(id==kPmHome) {
                OpenUrl(g_projectProvider==0?L"https://chatgpt.com/":L"https://claude.ai/new");
                return 0;
            }
            if(id==kPmOpen){
                int index=SelectedProjectIndex();
                if(index>=0)OpenUrl(g_projectLinks[index].url.c_str());
                else MessageBoxW(hwnd,L"Selecciona un proyecto de la lista.",
                                 L"HOVER",MB_OK|MB_ICONINFORMATION);
                return 0;
            }
            if(id==kPmSave) {
                std::wstring name=ProjectEditText(g_projectName);
                std::wstring url=ProjectEditText(g_projectUrl);
                if(!SafeProjectName(name)||!SafeProjectUrl(g_projectProvider,url)) {
                    MessageBoxW(hwnd,L"Escribe un nombre (por ejemplo Zap) y pega la URL real del proyecto.\n"
                               L"ChatGPT: https://chatgpt.com/g/g-p-...\n"
                               L"Claude: https://claude.ai/project/...",
                               L"Comprueba los datos",MB_OK|MB_ICONWARNING);
                    return 0;
                }
                int index=-1;
                for(size_t i=0;i<g_projectLinks.size();i++) {
                    if(g_projectLinks[i].provider==g_projectProvider &&
                       _wcsicmp(g_projectLinks[i].name.c_str(),name.c_str())==0){
                        index=int(i);break;
                    }
                }
                if(index>=0)g_projectLinks[index].url=url;
                else g_projectLinks.push_back({g_projectProvider,name,url});
                if(!SaveProjectLinks()){
                    MessageBoxW(hwnd,L"No se pudo guardar el archivo local de proyectos.",
                                L"HOVER",MB_OK|MB_ICONERROR);
                } else {
                    RefreshProjectList();
                    g_voiceMessage=L"Proyecto guardado: "+name;
                    g_voiceState=L"ok";
                    g_voiceNoticeUntil=GetTickCount64()+3600;
                }
                return 0;
            }
            if(id==kPmDelete) {
                int index=SelectedProjectIndex();
                if(index<0)return 0;
                if(MessageBoxW(hwnd,L"Eliminar el enlace de este proyecto?",
                               L"HOVER",MB_YESNO|MB_ICONQUESTION)!=IDYES)return 0;
                g_projectLinks.erase(g_projectLinks.begin()+index);
                if(!SaveProjectLinks())
                    MessageBoxW(hwnd,L"No se pudo actualizar el archivo de proyectos.",
                                L"HOVER",MB_OK|MB_ICONERROR);
                RefreshProjectList();
                SetWindowTextW(g_projectName,L"");
                SetWindowTextW(g_projectUrl,L"");
                return 0;
            }
            return 0;
        }
        case WM_CLOSE:DestroyWindow(hwnd);return 0;
        case WM_DESTROY:
            if(g_projectWindow==hwnd)g_projectWindow=nullptr;
            g_projectList=g_projectName=g_projectUrl=nullptr;
            return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
void OpenProjectManager(HWND owner,int provider) {
    if(g_projectWindow&&IsWindow(g_projectWindow))DestroyWindow(g_projectWindow);
    g_projectProvider=provider;
    ReadProjectLinks();
    HINSTANCE instance=GetModuleHandleW(nullptr);
    WNDCLASSEXW wc{};wc.cbSize=sizeof(wc);wc.hInstance=instance;
    wc.lpfnWndProc=ProjectWindowProc;wc.lpszClassName=kProjectWindowClass;
    wc.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));
    wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1);
    if(!GetClassInfoExW(instance,kProjectWindowClass,&wc)){
        wc={};wc.cbSize=sizeof(wc);wc.hInstance=instance;
        wc.lpfnWndProc=ProjectWindowProc;wc.lpszClassName=kProjectWindowClass;
        wc.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));
        wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1);
        if(!RegisterClassExW(&wc))return;
    }
    const wchar_t* title=provider==0?L"HOVER - Proyectos ChatGPT":L"HOVER - Proyectos Claude";
    HWND window=CreateWindowExW(WS_EX_TOOLWINDOW|WS_EX_TOPMOST,kProjectWindowClass,title,
        WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,502,426,owner,nullptr,instance,nullptr);
    if(!window)return;
    g_projectWindow=window;
    NewProjectControl(window,L"STATIC",L"PROYECTOS GUARDADOS",SS_LEFT,17,16,450,20);
    g_projectList=NewProjectControl(window,L"LISTBOX",L"",
        LBS_NOTIFY|WS_VSCROLL|WS_BORDER|WS_TABSTOP,17,39,450,119,kPmList);
    NewProjectControl(window,L"STATIC",L"Nombre del proyecto (ej.: Zap)",SS_LEFT,17,169,450,18);
    g_projectName=NewProjectControl(window,L"EDIT",L"",
        WS_BORDER|ES_AUTOHSCROLL|WS_TABSTOP,17,188,450,26,kPmName);
    NewProjectControl(window,L"STATIC",L"URL del proyecto (copia el enlace desde el navegador)",SS_LEFT,
                      17,221,450,18);
    g_projectUrl=NewProjectControl(window,L"EDIT",L"",WS_BORDER|ES_AUTOHSCROLL|WS_TABSTOP,
                                   17,241,358,26,kPmUrl);
    NewProjectControl(window,L"BUTTON",L"Pegar",BS_PUSHBUTTON|WS_TABSTOP,
                      383,241,84,26,kPmPaste);
    NewProjectControl(window,L"BUTTON",L"Guardar",BS_DEFPUSHBUTTON|WS_TABSTOP,
                      17,283,110,32,kPmSave);
    NewProjectControl(window,L"BUTTON",L"Abrir proyecto",BS_PUSHBUTTON|WS_TABSTOP,
                      135,283,138,32,kPmOpen);
    NewProjectControl(window,L"BUTTON",L"Eliminar",BS_PUSHBUTTON|WS_TABSTOP,
                      281,283,87,32,kPmDelete);
    NewProjectControl(window,L"BUTTON",L"Cerrar",BS_PUSHBUTTON|WS_TABSTOP,
                      376,283,91,32,kPmClose);
    NewProjectControl(window,L"BUTTON",provider==0?L"Abrir ChatGPT":L"Abrir Claude",
                      BS_PUSHBUTTON|WS_TABSTOP,17,326,450,27,kPmHome);
    RefreshProjectList();
    ShowWindow(window,SW_SHOW);
    SetForegroundWindow(window);
    SetFocus(g_projectName);
}

// OAuth: only short local commands/status are passed between the mod and
// HOVER Python. NO access tokens, cookies, passwords or client secret here.
// Google credentials stay encrypted with Windows DPAPI by Python.
constexpr wchar_t kHoverGoogleClass[]=L"HOVERGoogleOAuthV46";
constexpr int kGoogleLabel=9600,kGoogleClose=9601,kGoogleAll=9602;
constexpr int kGoogleDisconnectAll=9603,kGoogleConnectBase=9610;
constexpr int kGoogleDisconnectBase=9620;
HWND g_googleWindow=nullptr,g_googleStatusLabel=nullptr;
const char* kGoogleServices[]={"drive","calendar","gmail","docs"};
const wchar_t* kGoogleNames[]={L"Drive",L"Calendar",L"Gmail",L"Docs"};

std::wstring HoverGooglePath(const wchar_t* filename) {
    std::wstring file=ProjectStorePath();
    size_t slash=file.find_last_of(L"\\/");
    if(slash==std::wstring::npos)return L"";
    return file.substr(0,slash+1)+filename;
}

bool HoverGoogleCommand(const char* action,const char* service) {
    // All call sites use compile-time action and service literals.
    if(strcmp(action,"connect")!=0&&strcmp(action,"disconnect")!=0)return false;
    bool valid=strcmp(service,"all")==0;
    for(const char* name:kGoogleServices)if(strcmp(name,service)==0)valid=true;
    if(!valid)return false;
    std::wstring path=HoverGooglePath(L"google_control.txt");
    if(path.empty())return false;
    std::string cmd=std::string(action)+" "+service+"\n";
    HANDLE h=CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,
                         FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h==INVALID_HANDLE_VALUE)return false;
    DWORD written=0;
    BOOL ok=WriteFile(h,cmd.data(),DWORD(cmd.size()),&written,nullptr);
    CloseHandle(h);
    return ok&&written==cmd.size();
}
std::wstring HoverGoogleReadStatus() {
    std::wstring filename=HoverGooglePath(L"google_status.tsv");
    if(filename.empty())return L"Motor HOVER no configurado.";
    HANDLE h=CreateFileW(filename.c_str(),GENERIC_READ,FILE_SHARE_READ|
                         FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,
                         OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h==INVALID_HANDLE_VALUE)
        return L"Ejecuta INICIAR_HOVER.bat para activar la conexión Google.";
    char buf[750]{};DWORD got=0;
    BOOL ok=ReadFile(h,buf,sizeof(buf)-1,&got,nullptr);
    CloseHandle(h);
    if(!ok||got==0)return L"Sin estado Google del asistente.";
    std::string raw(buf,got);
    std::vector<std::string> fields;
    size_t pos=0;
    for(int i=0;i<5;i++){
        size_t end=raw.find('\t',pos);
        if(end==std::string::npos)end=raw.size();
        fields.push_back(raw.substr(pos,end-pos));
        pos=end<raw.size()?end+1:end;
    }
    if(fields.size()<5)return L"Esperando estado de Google...";
    std::wstring label=L"Drive: ";
    label+=(fields[0]=="1"?L"OK":L"No");
    label+=L"  |  Calendar: ";
    label+=(fields[1]=="1"?L"OK":L"No");
    label+=L"\r\nGmail: ";
    label+=(fields[2]=="1"?L"OK":L"No");
    label+=L"  |  Docs: ";
    label+=(fields[3]=="1"?L"OK":L"No");
    label+=L"\r\n";
    label+=DecodeUtf8(fields[4]);
    if(label.size()>300)label.resize(300);
    return label;
}
void HoverGoogleRefresh() {
    if(g_googleStatusLabel&&IsWindow(g_googleStatusLabel)){
        std::wstring message=HoverGoogleReadStatus();
        SetWindowTextW(g_googleStatusLabel,message.c_str());
    }
}
LRESULT CALLBACK HoverGoogleWindowProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp) {
    switch(msg) {
        case WM_COMMAND:{
            if(HIWORD(wp)!=BN_CLICKED)return 0;
            int id=LOWORD(wp);
            if(id==kGoogleClose){DestroyWindow(hwnd);return 0;}
            const char* action=nullptr;
            const char* service=nullptr;
            if(id==kGoogleAll){action="connect";service="all";}
            else if(id==kGoogleDisconnectAll){
                action="disconnect";service="all";
                if(MessageBoxW(hwnd,L"¿Desconectar todas las cuentas Google en este PC?",
                               L"HOVER Google",MB_YESNO|MB_ICONQUESTION)!=IDYES)
                    return 0;
            } else if(id>=kGoogleConnectBase&&id<kGoogleConnectBase+4){
                action="connect";service=kGoogleServices[id-kGoogleConnectBase];
            } else if(id>=kGoogleDisconnectBase&&id<kGoogleDisconnectBase+4){
                action="disconnect";service=kGoogleServices[id-kGoogleDisconnectBase];
            }
            if(action&&service) {
                bool accepted=HoverGoogleCommand(action,service);
                if(!accepted)
                    MessageBoxW(hwnd,L"No se pudo enviar la orden a HOVER.",
                                L"HOVER Google",MB_OK|MB_ICONERROR);
                else
                    SetWindowTextW(g_googleStatusLabel,
                        L"Orden enviada. Autoriza en Google si se abre el navegador.\r\n"
                        L"El motor HOVER debe estar encendido.");
                return 0;
            }
            break;
        }
        case WM_TIMER:HoverGoogleRefresh();return 0;
        case WM_CLOSE:DestroyWindow(hwnd);return 0;
        case WM_DESTROY:
            KillTimer(hwnd,9619);
            if(g_googleWindow==hwnd)g_googleWindow=nullptr;
            g_googleStatusLabel=nullptr;
            return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
void OpenGoogleAccountManager(HWND owner) {
    if(g_googleWindow&&IsWindow(g_googleWindow)){
        ShowWindow(g_googleWindow,SW_RESTORE);
        SetForegroundWindow(g_googleWindow);
        return;
    }
    HINSTANCE instance=GetModuleHandleW(nullptr);
    WNDCLASSEXW wc{};wc.cbSize=sizeof(wc);wc.hInstance=instance;
    wc.lpfnWndProc=HoverGoogleWindowProc;wc.lpszClassName=kHoverGoogleClass;
    wc.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));
    wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1);
    if(!GetClassInfoExW(instance,kHoverGoogleClass,&wc)) {
        if(!RegisterClassExW(&wc))return;
    }
    HWND window=CreateWindowExW(WS_EX_TOOLWINDOW|WS_EX_TOPMOST,
        kHoverGoogleClass,L"HOVER - Cuenta Google",
        WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,505,425,owner,nullptr,instance,nullptr);
    if(!window)return;
    g_googleWindow=window;
    NewProjectControl(window,L"STATIC",
        L"Autoriza solo los servicios que quieras conectar.",
        SS_LEFT,16,14,460,22);
    g_googleStatusLabel=NewProjectControl(window,L"STATIC",L"",
        SS_LEFT,16,40,460,65,kGoogleLabel);
    NewProjectControl(window,L"STATIC",L"Servicio",SS_LEFT,16,116,175,20);
    for(int i=0;i<4;i++) {
        int y=140+i*43;
        NewProjectControl(window,L"STATIC",kGoogleNames[i],
                          SS_LEFT,18,y+7,155,24);
        NewProjectControl(window,L"BUTTON",L"Conectar",
            BS_PUSHBUTTON|WS_TABSTOP,179,y,126,30,kGoogleConnectBase+i);
        NewProjectControl(window,L"BUTTON",L"Desconectar",
            BS_PUSHBUTTON|WS_TABSTOP,316,y,154,30,kGoogleDisconnectBase+i);
    }
    NewProjectControl(window,L"BUTTON",L"Conectar los cuatro",
        BS_PUSHBUTTON|WS_TABSTOP,16,322,165,33,kGoogleAll);
    NewProjectControl(window,L"BUTTON",L"Desconectar todos",
        BS_PUSHBUTTON|WS_TABSTOP,189,322,163,33,kGoogleDisconnectAll);
    NewProjectControl(window,L"BUTTON",L"Cerrar",
        BS_PUSHBUTTON|WS_TABSTOP,360,322,110,33,kGoogleClose);
    HoverGoogleRefresh();
    SetTimer(window,9619,1500,nullptr);
    ShowWindow(window,SW_SHOW);
    SetForegroundWindow(window);
}

void Execute(HWND hwnd,int action) {
    g_feedbackAction=action;
    g_feedbackUntil=GetTickCount64()+650;
    // El ultimo icono del reproductor abre su aplicacion en vez de quedar inactivo.
    if(action==108){OpenSpotify();return;}
    if(action>=500 && action<500+int(g_voiceTabs.size())){
        const std::wstring& url=g_voiceTabs[action-500].url;
        if(url.rfind(L"https://",0)==0||url.rfind(L"http://",0)==0)
            OpenUrl(url.c_str());
        return;
    }
    if(action>=101&&action<=108){Command(action-100);return;}
    if(action==202){Command(1);return;}
    if(action>=601&&action<=631){
        g_calendarSelectedDay=action-600;
        g_calendarSelectedIndex=0;
        g_calendarDetailsOpen=true;
        return;
    }
    if(action==652){g_calendarDetailsOpen=false;return;}
    if(action==654){
        OpenUrl(L"https://calendar.google.com/calendar/u/0/r/eventedit");
        return;
    }
    if(action==650){
        int year=0,month=0;VisibleCalendarMonth(year,month);
        auto events=DayEvents(year,month,g_calendarSelectedDay);
        if(!events.empty() && g_calendarSelectedIndex<int(events.size())){
            const auto& url=events[g_calendarSelectedIndex]->url;
            if(url.rfind(L"https://calendar.google.com/",0)==0)
                OpenUrl(url.c_str());
        }
        return;
    }
    if(action==653){
        int year=0,month=0;VisibleCalendarMonth(year,month);
        auto events=DayEvents(year,month,g_calendarSelectedDay);
        if(!events.empty())
            g_calendarSelectedIndex=(g_calendarSelectedIndex+1)%int(events.size());
        return;
    }
    if(action==401){g_monthOffset=ClampInt(g_monthOffset-1,-24,24);g_calendarDetailsOpen=false;return;}
    if(action==402){g_monthOffset=ClampInt(g_monthOffset+1,-24,24);g_calendarDetailsOpen=false;return;}
    switch(action){
        case 200: OpenProjectManager(hwnd,0);break;
        case 201: OpenProjectManager(hwnd,1);break;
        case 208: OpenGoogleAccountManager(hwnd);break;
        case 203: Screenshot();break;
        case 204: FavoriteFolder(hwnd,false);break;
        case 205: OpenUrl(L"explorer.exe");break;
        case 206: OpenUrl(L"ms-settings:");break;
        case 207: {INPUT a[4]{};a[0].type=INPUT_KEYBOARD;a[0].ki.wVk=VK_LWIN;
                   a[1].type=INPUT_KEYBOARD;a[1].ki.wVk='V';
                   a[2]=a[1];a[2].ki.dwFlags=KEYEVENTF_KEYUP;
                   a[3]=a[0];a[3].ki.dwFlags=KEYEVENTF_KEYUP;
                   SendInput(4,a,sizeof(INPUT));break;}
    }
}

void DrawPanel(Graphics& g,int w,int h,bool showToast) {
    Color ac=Accent();
    const float opened=Clamp(g_open,0,1);
    const BYTE a=BYTE(255*(1-opened)+g_expandedOpacity.load()*opened);
    GraphicsPath outline;
    IslandPath(outline,float(w),float(h),12+6*opened,24+4*opened);
    LinearGradientBrush gradient(PointF(0,0),PointF(float(w),float(h)),
                                 Color(a,3,4,7),
                                 Color(a,BYTE(ac.GetR()*opened*0.075f+8),
                                         BYTE(ac.GetG()*opened*0.075f+9),
                                         BYTE(ac.GetB()*opened*0.075f+14)));
    // Sin contornos: se dibuja solo el relleno curvado de la isla.
    g.FillPath(&gradient,&outline);
    // Main capsule: deliberately no HOVER text
    wchar_t clock[32]{};ClockText(clock);
    Text(g,clock,26,11,72,29,12.8f,Color(255,241,241,247),true);
    DrawEyes(g,w*0.5f);
    // En reposo solo HOVER a la derecha: NUNCA titulo ni artista sobre los ojos.
    if(g_open<0.15f && !showToast) {
        Text(g,L"HOVER",float(w-77),11,49,25,9.4f,
             Color(205,155,164,179),false,true);
    }
    if(g_open>0.82f) {
        DrawPageDots(g);
        // Transicion VERTICAL, con contenido que ocupa la zona liberada.
        auto state=g.Save();
        g.SetClip(RectF(12.0f,78.0f,float(w)-24.0f,float(h)-82.0f));
        float p=g_pageEase*g_pageEase*(3.0f-2.0f*g_pageEase);
        const float slide=278.0f;
        if(g_pageEase<1.0f) {
            auto previous=g.Save();
            g.TranslateTransform(0.0f,-kContentLift-float(g_pageDirection)*slide*p);
            if(g_previousPage==0)PageMusic(g);
            else if(g_previousPage==1)PageCopies(g);
            else if(g_previousPage==2)PageCalendar(g);
            else if(g_previousPage==3)PageShortcuts(g);
            else if(g_previousPage==4)PageHardware(g);
            else PageVoiceTab(g,g_previousPage);
            g.Restore(previous);
        }
        auto current=g.Save();
        g.TranslateTransform(0.0f,-kContentLift+float(g_pageDirection)*slide*(1.0f-p));
        if(g_currentPage==0)PageMusic(g);
        else if(g_currentPage==1)PageCopies(g);
        else if(g_currentPage==2)PageCalendar(g);
        else if(g_currentPage==3)PageShortcuts(g);
        else if(g_currentPage==4)PageHardware(g);
        else PageVoiceTab(g,g_currentPage);
        g.Restore(current);
        g.Restore(state);
        if(GetTickCount64()<g_voiceNoticeUntil && !g_voiceMessage.empty()) {
            const wchar_t* shortState = g_voiceState==L"listening"?L"ESCUCHANDO":
                  g_voiceState==L"thinking"?L"PROCESANDO":
                  g_voiceState==L"error"?L"NO ENTENDIDO":L"LISTO";
            Text(g,shortState,355.0f,52.0f,130.0f,20.0f,10.5f,
                 Color(230,194,213,230),true,true);
        }
    } else if(showToast || GetTickCount64()<g_chargeToastUntil ||
              GetTickCount64()<g_copyToastUntil || GetTickCount64()<g_voiceNoticeUntil) {
        Round(g,12,53,float(w-24),40,13,Color(230,18,21,30),Color(0,0,0,0),0.0f);
        if(GetTickCount64()<g_chargeToastUntil) {
            const float t=float((GetTickCount64()%900ULL))/900.0f;
            const float pulse=0.75f+0.25f*std::sin(t*6.28318f);
            SolidBrush boltGlow(Color(BYTE(70*pulse),ac.GetR(),ac.GetG(),ac.GetB()));
            g.FillEllipse(&boltGlow,24.0f,59.0f,18.0f,18.0f);
            SolidBrush bolt(Color(255,245,248,252));
            PointF pts[] = {PointF(31.0f,58.0f),PointF(24.5f,69.5f),PointF(30.0f,69.5f),PointF(27.0f,81.0f),PointF(39.0f,65.3f),PointF(33.0f,65.3f)};
            g.FillPolygon(&bolt,pts,6);
            Text(g,L"CARGANDO",53,57,110,15,10,Accent(255),true);
            Text(g,L"El cargador se conecto",53,72,float(w-70),18,12,Color(255,241,243,247));
        } else if(GetTickCount64()<g_voiceNoticeUntil && !g_voiceMessage.empty()) {
            Text(g,g_voiceState==L"listening"?L"ESCUCHANDO" :
                   g_voiceState==L"thinking"?L"PROCESANDO" : L"HOVER VOZ",
                 24,57,155,15,10,Accent(255),true);
            Text(g,g_voiceMessage,24,72,float(w-48),18,12,Color(255,241,243,247));
        } else if(GetTickCount64()<g_copyToastUntil) {
            Text(g,L"CARPETA",24,57,96,15,10,Accent(255),true);
            Text(g,g_copyToastText,24,72,float(w-48),18,12,Color(255,241,243,247));
        } else {
            Text(g,L"COPIADO",24,57,92,15,10,Accent(255),true);
            Text(g,g_lastClip,24,72,float(w-48),18,12,Color(255,241,243,247));
        }
    }
}

void Paint(HWND hwnd) {
    RECT r{};GetWindowRect(hwnd,&r);
    int w=r.right-r.left,h=r.bottom-r.top;if(w<1||h<1)return;
    Bitmap bmp(w,h,PixelFormat32bppPARGB);
    Graphics g(&bmp);
    g.Clear(Color(0,0,0,0));
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    bool toast=g_showClipboard&&!g_lastClip.empty()&&GetTickCount64()-g_clipTick<kToastMs;
    DrawPanel(g,w,h,toast);
    g.Flush(FlushIntentionSync);
    HDC screen=GetDC(nullptr);if(!screen)return;
    HDC mem=CreateCompatibleDC(screen);if(!mem){ReleaseDC(nullptr,screen);return;}
    BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=w;bi.bmiHeader.biHeight=-h;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    void* bits=nullptr;
    HBITMAP dib=CreateDIBSection(mem,&bi,DIB_RGB_COLORS,&bits,nullptr,0);
    if(dib&&bits) {
        BitmapData data{};Rect area(0,0,w,h);
        if(bmp.LockBits(&area,ImageLockModeRead,PixelFormat32bppPARGB,&data)==Ok) {
            for(int y=0;y<h;y++)
                std::memcpy(static_cast<BYTE*>(bits)+size_t(y)*size_t(w)*4,
                            static_cast<BYTE*>(data.Scan0)+ptrdiff_t(y)*data.Stride,
                            size_t(w)*4);
            bmp.UnlockBits(&data);
            HGDIOBJ prev=SelectObject(mem,dib);
            POINT src{0,0},dst{r.left,r.top};SIZE size{w,h};
            BLENDFUNCTION blend{AC_SRC_OVER,0,255,AC_SRC_ALPHA};
            UpdateLayeredWindow(hwnd,screen,&dst,&size,mem,&src,0,&blend,ULW_ALPHA);
            SelectObject(mem,prev);
        }
        DeleteObject(dib);
    }
    DeleteDC(mem);ReleaseDC(nullptr,screen);
}

RECT PrimaryBounds(){
    POINT pt{0,0};HMONITOR monitor=MonitorFromPoint(pt,MONITOR_DEFAULTTOPRIMARY);
    MONITORINFO mi{};mi.cbSize=sizeof(mi);
    if(GetMonitorInfoW(monitor,&mi))return mi.rcMonitor;
    return RECT{0,0,GetSystemMetrics(SM_CXSCREEN),GetSystemMetrics(SM_CYSCREEN)};
}
// Eye-center drag needs a route independent of normal WM_LBUTTONDOWN:
// UpdateLayeredWindow with a transparent frame and WS_EX_NOACTIVATE can cause
// Windows to route clicks to the window behind the visible island.
bool IsEyeGripScreenPoint(HWND hwnd,const POINT& point) {
    RECT bounds{};
    if(!hwnd || !IsWindow(hwnd) || !IsWindowVisible(hwnd) ||
       !GetWindowRect(hwnd,&bounds))return false;
    const int middle=(bounds.left+bounds.right)/2;
    // Deliberately generous: covers the dark strip and inner sides of eyes.
    // It does not cover calendar/music buttons or the window below.
    return std::abs(point.x-middle)<=23 &&
           point.y>=bounds.top+2 && point.y<=bounds.top+44;
}

void BeginEyeGrip(HWND hwnd,const POINT& point) {
    if(!IsEyeGripScreenPoint(hwnd,point))return;
    g_eyeGripDrag=true;
    g_eyeGripMoved=false;
    g_drag=false;
    g_dragOrigin=point;
    g_grabStartShiftX=g_islandShiftX;
    g_grabStartShiftY=g_islandShiftY;
}

void FinishEyeGrip(HWND hwnd) {
    if(!g_eyeGripDrag)return;
    POINT point{};GetCursorPos(&point);
    const int dx=point.x-g_dragOrigin.x;
    const int dy=point.y-g_dragOrigin.y;
    const bool moved=g_eyeGripMoved || std::abs(dx)>4 || std::abs(dy)>4;
    RECT r{};GetWindowRect(hwnd,&r);
    const RECT monitor=PrimaryBounds();
    const int w=r.right-r.left,h=r.bottom-r.top;
    const int baseX=(monitor.left+monitor.right-w)/2+g_xOffset;
    const int baseY=monitor.top+g_topGap;
    const int x=ClampInt(baseX+g_grabStartShiftX+dx,monitor.left,
                         std::max(monitor.left,monitor.right-w));
    const int y=ClampInt(baseY+g_grabStartShiftY+dy,monitor.top,
                         std::max(monitor.top,monitor.bottom-h));
    g_islandShiftX=x-baseX;
    g_islandShiftY=y-baseY;
    g_eyeGripDrag=false;
    if(moved)SaveIslandPosition();
}

void Animate(HWND hwnd){
    if(g_stopping){DestroyWindow(hwnd);return;}
    if(g_clipDirty){
        if(TryReadClipboard()||++g_clipAttempts>12)g_clipDirty=false;
    }
    ULONGLONG nowMs=GetTickCount64();
    if(nowMs-g_lastHardwareRead>1050ULL){
        g_lastHardwareRead=nowMs;
        if(g_open>0.20f || g_currentPage==4)UpdateHardware();
    }
    if(nowMs-g_lastMediaRead>700){g_lastMediaRead=nowMs;ReadBridgeState();}
    if(nowMs-g_lastTabsRead>950) {
        g_lastTabsRead=nowMs;
        ReadVoiceTabs();
    }
    if(nowMs-g_calendarLastRead>2500) {
        g_calendarLastRead=nowMs;
        ReadCalendarBridge();
    }
    if(nowMs-g_lastVoiceRead>275) {
        g_lastVoiceRead=nowMs;
        ReadVoiceBridge();
    }
    if(g_pendingMediaAction) {
        if(nowMs>g_pendingMediaExpires)g_pendingMediaAction=0;
        else if(g_bridgeOnline) {
            MediaState m;
            {std::lock_guard<std::mutex> guard(g_mediaGuard);m=g_media;}
            if(!m.source.empty()||!m.title.empty()) {
                const int a=g_pendingMediaAction;
                g_pendingMediaAction=0;
                if(a==1)SendMediaKey(VK_MEDIA_PLAY_PAUSE);
                if(a==2)SendMediaKey(VK_MEDIA_PREV_TRACK);
                if(a==3)SendMediaKey(VK_MEDIA_NEXT_TRACK);
            }
        }
    }
    SYSTEM_POWER_STATUS ps{};
    if(GetSystemPowerStatus(&ps)) {
        if(g_lastACLineStatus==255) g_lastACLineStatus=ps.ACLineStatus;
        else if(ps.ACLineStatus!=g_lastACLineStatus) {
            if(ps.ACLineStatus==1) g_chargeToastUntil=nowMs+kChargeToastMs;
            g_lastACLineStatus=ps.ACLineStatus;
        }
    }
    POINT mouse{};GetCursorPos(&mouse);
    RECT old{};GetWindowRect(hwnd,&old);
    bool inside=mouse.x>=old.left&&mouse.x<old.right&&mouse.y>=old.top&&mouse.y<old.bottom;
    // The eye-grip keeps the island expanded while it is physically dragged.
    // Audio/voice status never causes the panel to expand by itself.
    if(g_eyeGripDrag) {
        if(!g_hookGripActive.load() &&
           (GetAsyncKeyState(VK_LBUTTON)&0x8000)==0) {
            // When the low-level hook intentionally swallows mouse-down,
            // GetAsyncKeyState is not authoritative. Wait for kEyeGripEnd.
            // Normal Win32 clicks still use the old physical-button fallback.
            // Commit the location rather than silently discarding the drag.
            FinishEyeGrip(hwnd);
            g_drag=false;
            if(GetCapture()==hwnd)ReleaseCapture();
        } else {
            const int dx=mouse.x-g_dragOrigin.x;
            const int dy=mouse.y-g_dragOrigin.y;
            if(std::abs(dx)>4||std::abs(dy)>4)g_eyeGripMoved=true;
            g_islandShiftX=g_grabStartShiftX+dx;
            g_islandShiftY=g_grabStartShiftY+dy;
        }
    }
    bool expand=g_eyeGripDrag || g_fileDragActive ||
                (g_hover&&inside) || nowMs<g_voiceExpandUntil;
    float goal=expand?1:0;
    g_openV=(g_openV+(goal-g_open)*0.20f)*0.76f;
    g_open=Clamp(g_open+g_openV,0,1);
    if(g_open<0.003f&&!expand){
        g_open=0;g_openV=0;
        g_wheelAccumV=0;g_wheelAccumH=0;
    }
    if(g_open>0.997f&&expand){g_open=1;g_openV=0;}
    g_pageEase=Clamp(g_pageEase+0.10f,0,1);
    float eased=g_open*g_open*(3-2*g_open);
    bool toast=g_showClipboard&&!g_lastClip.empty()&&GetTickCount64()-g_clipTick<kToastMs;
    bool quickNotice=toast || GetTickCount64()<g_copyToastUntil ||
         GetTickCount64()<g_chargeToastUntil || GetTickCount64()<g_voiceNoticeUntil;
    int baseW=quickNotice?kToastWidth:kMiniWidth;
    int baseH=quickNotice?kToastHeight:kMiniHeight;
    int w=int(baseW+(kPanelWidth-baseW)*eased+0.5f);
    int h=int(baseH+(kPanelHeight-baseH)*eased+0.5f);
    RECT screen=PrimaryBounds();
    const int baseX=(screen.left+screen.right-w)/2+g_xOffset;
    const int baseY=screen.top+g_topGap;
    // Clamp both the mini island and the expanded panel to the monitor.
    // Drag changes runtime offsets, not the user's Windhawk settings.
    int x=ClampInt(baseX+g_islandShiftX,screen.left,
                   std::max(screen.left,screen.right-w));
    int y=ClampInt(baseY+g_islandShiftY,screen.top,
                   std::max(screen.top,screen.bottom-h));
    if(g_eyeGripDrag) {
        g_islandShiftX=x-baseX;
        g_islandShiftY=y-baseY;
    }
    if(x!=old.left||y!=old.top||w!=old.right-old.left||h!=old.bottom-old.top)
        SetWindowPos(hwnd,HWND_TOPMOST,x,y,w,h,SWP_NOACTIVATE|SWP_NOOWNERZORDER|SWP_SHOWWINDOW);
    float targetX=Clamp((float(mouse.x)-float(x)-float(w)*0.5f)/62.0f,-1.0f,1.0f)*3.5f;
    float targetY=Clamp(float(mouse.y-(y+25))/62.0f,-1.0f,1.0f)*3.3f;
    g_eyeVX=(g_eyeVX+(targetX-g_eyeX)*0.30f)*0.66f;
    g_eyeVY=(g_eyeVY+(targetY-g_eyeY)*0.30f)*0.66f;
    g_eyeX+=g_eyeVX;g_eyeY+=g_eyeVY;
    g_hoverAction=inside?HitAction(float(mouse.x-x),float(mouse.y-y)):-1;
    Paint(hwnd);
}

// Los touchpads de precision emiten deltas pequenos y repetidos; se acumulan.
// La rueda de mouse tipica envia 120 unidades y navega de inmediato.
void HandleSwipeDelta(int rawDelta,bool horizontal) {
    if(rawDelta==0 || g_open<0.35f || g_eyeGripDrag)return;
    const ULONGLONG now=GetTickCount64();
    if(now-g_lastGestureTick>330ULL) {
        g_wheelAccumV=0.0f;g_wheelAccumH=0.0f;
    }
    g_lastGestureTick=now;
    float& accum=horizontal?g_wheelAccumH:g_wheelAccumV;
    if((accum>0.0f && rawDelta<0)||(accum<0.0f && rawDelta>0))accum=0.0f;
    accum=Clamp(accum+float(rawDelta),-360.0f,360.0f);
    const float threshold=float(g_swipeSensitivity.load());
    if(std::fabs(accum)<threshold)return;
    if(now-g_lastSwipeMs<180ULL)return;
    const int direction=horizontal?(accum>0.0f?1:-1):(accum>0.0f?-1:1);
    ChangePage(g_currentPage+direction);
    g_lastSwipeMs=now;
    g_wheelAccumV=0.0f;
    g_wheelAccumH=0.0f;
}

// Evita procesar dos veces el mismo evento (WM_MOUSEWHEEL + hook de bajo nivel).
void ReceiveWheel(int rawDelta,bool horizontal,DWORD eventTime) {
    const ULONGLONG now=GetTickCount64();
    if(eventTime==g_lastWheelTick&&rawDelta==g_lastWheelValue&&
       horizontal==g_lastWheelHorizontal&&now-g_lastWheelAt<40ULL)return;
    g_lastWheelTick=eventTime;
    g_lastWheelValue=rawDelta;
    g_lastWheelHorizontal=horizontal;
    g_lastWheelAt=now;
    HandleSwipeDelta(rawDelta,horizontal);
}

LRESULT CALLBACK LowLevelWheelHook(int code,WPARAM wp,LPARAM lp) {
    if(code!=HC_ACTION || g_stopping || !lp)
        return CallNextHookEx(nullptr,code,wp,lp);
    HWND hwnd=g_hwnd;
    if(!hwnd)return CallNextHookEx(nullptr,code,wp,lp);
    const MSLLHOOKSTRUCT* e=reinterpret_cast<const MSLLHOOKSTRUCT*>(lp);
    // Let real mouse/trackpad gestures work even when the transparent layer
    // cannot receive clicks. Never intercept synthetic events from apps.
    if(!(e->flags & LLMHF_INJECTED)){
        if(wp==WM_LBUTTONDOWN && !g_hookGripActive.load() &&
           IsEyeGripScreenPoint(hwnd,e->pt)){
            if(PostMessageW(hwnd,kEyeGripBegin,0,0)){
                g_hookGripActive.store(true);
                return 1; // ONLY the tiny center grip owns this press.
            }
        }
        if(wp==WM_LBUTTONUP && g_hookGripActive.exchange(false)){
            PostMessageW(hwnd,kEyeGripEnd,0,0);
            return 1; // Release is paired even when dragged outside island.
        }
    }
    if((wp==WM_MOUSEWHEEL||wp==WM_MOUSEHWHEEL) &&
       !g_hookGripActive.load()){
        RECT bounds{};
        if(GetWindowRect(hwnd,&bounds) &&
           e->pt.x>=bounds.left && e->pt.x<bounds.right &&
           e->pt.y>=bounds.top && e->pt.y<bounds.bottom) {
            if(g_open>0.35f && PostMessageW(hwnd,
                    wp==WM_MOUSEHWHEEL?kWheelHorizontalMessage:kWheelMessage,
                    HIWORD(e->mouseData),LPARAM(e->time))) {
                return 1;
            }
        }
    }
    return CallNextHookEx(nullptr,code,wp,lp);
}

// Las flechas funcionan sin quitar el foco a la aplicacion del usuario.
// Solo se interceptan cuando el cursor esta sobre la isla expandida.
LRESULT CALLBACK HoverKeyboardHook(int code,WPARAM wp,LPARAM lp) {
    if(code==HC_ACTION && (wp==WM_KEYDOWN || wp==WM_SYSKEYDOWN) && !g_stopping) {
        const KBDLLHOOKSTRUCT* key=reinterpret_cast<const KBDLLHOOKSTRUCT*>(lp);
        if((key->vkCode==VK_UP || key->vkCode==VK_DOWN ||
            key->vkCode==VK_LEFT || key->vkCode==VK_RIGHT) &&
            !(key->flags & LLKHF_INJECTED)) {
            HWND hwnd=g_hwnd;
            POINT p{};RECT r{};
            if(hwnd && g_open>0.65f && GetCursorPos(&p) && GetWindowRect(hwnd,&r) &&
               PtInRect(&r,p) && GetAsyncKeyState(VK_CONTROL)>=0 &&
               GetAsyncKeyState(VK_MENU)>=0) {
                int dir=(key->vkCode==VK_DOWN||key->vkCode==VK_RIGHT)?1:-1;
                if(PostMessageW(hwnd,kArrowNavigation,WPARAM(dir),0))return 1;
            }
        }
    }
    return CallNextHookEx(nullptr,code,wp,lp);
}

LRESULT CALLBACK WndProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp){
    switch(msg){
        case WM_CREATE:
            if(!AddClipboardFormatListener(hwnd))
                Wh_Log(L"No se pudo activar el listener del portapapeles");
            SetTimer(hwnd,kTimer,16,nullptr);
            return 0;
        case WM_CLIPBOARDUPDATE:
            g_clipDirty=true;g_clipAttempts=0;
            return 0;
        case WM_GESTURE: {
            GESTUREINFO info{};info.cbSize=sizeof(info);
            if(GetGestureInfo(reinterpret_cast<HGESTUREINFO>(lp),&info)) {
                if(info.dwID==GID_PAN) {
                    POINT p{info.ptsLocation.x,info.ptsLocation.y};
                    if((info.dwFlags & GF_BEGIN) || !g_gestureActive) {
                        g_gestureActive=true;g_lastGesturePos=p;
                    } else {
                        const int dy=p.y-g_lastGesturePos.y;
                        const int dx=p.x-g_lastGesturePos.x;
                        g_lastGesturePos=p;
                        if(g_open>0.35f && !g_eyeGripDrag &&
                           (std::abs(dy)+std::abs(dx))>=2) {
                            if(std::abs(dy)>=std::abs(dx))HandleSwipeDelta(-dy*3,false);
                            else HandleSwipeDelta(dx*3,true);
                        }
                    }
                    if(info.dwFlags & GF_END)g_gestureActive=false;
                }
            }
            CloseGestureInfoHandle(reinterpret_cast<HGESTUREINFO>(lp));
            return 0;
        }
        case kEyeGripBegin: {
            POINT pointer{};GetCursorPos(&pointer);
            BeginEyeGrip(hwnd,pointer);
            return 0;
        }
        case kEyeGripEnd:
            FinishEyeGrip(hwnd);
            return 0;
        case kArrowNavigation:
            if(g_open>0.60f)ChangePage(g_currentPage+(static_cast<int>(wp)>0?1:-1));
            return 0;
        case WM_MOUSEWHEEL:
        case WM_MOUSEHWHEEL:
        case WM_POINTERWHEEL:
        case WM_POINTERHWHEEL:
            ReceiveWheel(GET_WHEEL_DELTA_WPARAM(wp),
                         msg==WM_MOUSEHWHEEL || msg==WM_POINTERHWHEEL,
                         DWORD(GetMessageTime()));
            return 0;
        case kWheelMessage:
            ReceiveWheel(static_cast<short>(wp),false,DWORD(lp));
            return 0;
        case kWheelHorizontalMessage:
            ReceiveWheel(static_cast<short>(wp),true,DWORD(lp));
            return 0;
        case WM_TIMER:
            if(wp==kTimer)Animate(hwnd);
            return 0;
        case WM_LBUTTONDOWN: {
            POINT point{};GetCursorPos(&point);
            if(IsEyeGripScreenPoint(hwnd,point)){
                BeginEyeGrip(hwnd,point);
            } else {
                g_drag=true;
                g_dragOrigin=point;
            }
            // Keep normal touch/click swipes for the rest of the panel.
            SetCapture(hwnd);
            return 0;
        }
        case WM_LBUTTONUP:{
            POINT mouse{};GetCursorPos(&mouse);RECT r{};GetWindowRect(hwnd,&r);
            if(g_eyeGripDrag){
                FinishEyeGrip(hwnd);
                if(GetCapture()==hwnd)ReleaseCapture();
                g_drag=false;
                return 0;
            }
            if(g_drag) {
                g_drag=false;
                ReleaseCapture();
                const int dx=mouse.x-g_dragOrigin.x;
                const int dy=mouse.y-g_dragOrigin.y;
                if(g_open>0.66f && (std::abs(dx)>45 || std::abs(dy)>45)) {
                    const bool horizontal=std::abs(dx)>std::abs(dy);
                    ChangePage(g_currentPage + (horizontal?(dx<0?1:-1):(dy<0?1:-1)));
                    return 0;
                }
            }
            int action=HitAction(float(mouse.x-r.left),float(mouse.y-r.top));
            if(action!=-1)Execute(hwnd,action);
            return 0;
        }
        case WM_CAPTURECHANGED:
            g_drag=false;
            // The mouse hook owns capture for a center-grip drag.
            if(!g_hookGripActive.load())FinishEyeGrip(hwnd);
            return 0;
        case WM_RBUTTONUP:{
            POINT mouse{};GetCursorPos(&mouse);RECT r{};GetWindowRect(hwnd,&r);
            const int action=HitAction(float(mouse.x-r.left),float(mouse.y-r.top));
            if(action==204)FavoriteFolder(hwnd,true);
            else if(action==200)OpenUrl(L"https://chatgpt.com/");
            else if(action==201)OpenUrl(L"https://claude.ai/new");
            return 0;
        }
        case kFilesCopiedMessage:
            g_copyToastText=wp?L"Archivos copiados correctamente":L"No se pudieron copiar algunos archivos";
            g_copyToastUntil=GetTickCount64()+3500ULL;
            return 0;
        case kSettingsChanged:return 0;
        case WM_DESTROY:
            if(g_projectWindow&&IsWindow(g_projectWindow))DestroyWindow(g_projectWindow);
            RevokeDragDrop(hwnd);
            RemoveClipboardFormatListener(hwnd);
            KillTimer(hwnd,kTimer);g_hwnd=nullptr;PostQuitMessage(0);return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}

DWORD WINAPI UIThreadMain(LPVOID){
    if(g_stopping) return 0;
    HRESULT hr=OleInitialize(nullptr);
    GdiplusStartupInput in{};ULONG_PTR token=0;
    if(GdiplusStartup(&token,&in,nullptr)!=Ok){if(SUCCEEDED(hr))OleUninitialize();return 0;}
    WNDCLASSEXW wc{};wc.cbSize=sizeof(wc);wc.lpfnWndProc=WndProc;
    wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=kClass;
    wc.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));
    if(!RegisterClassExW(&wc)){GdiplusShutdown(token);if(SUCCEEDED(hr))OleUninitialize();return 0;}
    RECT m=PrimaryBounds();
    LoadIslandPosition();
    HWND hwnd=CreateWindowExW(WS_EX_LAYERED|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|WS_EX_TOPMOST,
        kClass,L"Isla dinamica Premium",WS_POPUP,
        ClampInt((m.left+m.right-kMiniWidth)/2+g_xOffset+g_islandShiftX,
                 m.left,std::max(m.left,m.right-kMiniWidth)),
        ClampInt(m.top+g_topGap+g_islandShiftY,m.top,
                 std::max(m.top,m.bottom-kMiniHeight)),
        kMiniWidth,kMiniHeight,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    if(hwnd) {
        g_hwnd=hwnd;
        GESTURECONFIG gc{};gc.dwID=GID_PAN;gc.dwWant=GC_PAN;
        SetGestureConfig(hwnd,0,1,&gc,sizeof(gc));
        LoadFavoriteFolder();
        HoverFileDropTarget* dropTarget=new HoverFileDropTarget(hwnd);
        bool dropRegistered=SUCCEEDED(RegisterDragDrop(hwnd,dropTarget));
        if(!dropRegistered) Wh_Log(L"HOVER: no se pudo registrar drag and drop OLE");
        HMODULE modModule=nullptr;
        GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|
                           GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(reinterpret_cast<void*>(&LowLevelWheelHook)),&modModule);
        g_wheelHook=SetWindowsHookExW(WH_MOUSE_LL,LowLevelWheelHook,modModule,0);
        g_keyboardHook=SetWindowsHookExW(WH_KEYBOARD_LL,HoverKeyboardHook,modModule,0);
        if(!g_keyboardHook)Wh_Log(L"HOVER: flechas no disponibles; usa rueda o touchpad");
        if(!g_wheelHook) Wh_Log(L"No se instalo el hook de rueda: se usa el control del mouse de Windows");
        ShowWindow(hwnd,SW_SHOWNOACTIVATE);
        Paint(hwnd);
        if(g_stopping)PostMessageW(hwnd,WM_CLOSE,0,0);
        MSG msg{};while(GetMessageW(&msg,nullptr,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}
        // Ya se revoco en WM_DESTROY; liberar la referencia local.
        dropTarget->Release();
    }
    if(g_wheelHook){UnhookWindowsHookEx(g_wheelHook);g_wheelHook=nullptr;}
    if(g_keyboardHook){UnhookWindowsHookEx(g_keyboardHook);g_keyboardHook=nullptr;}
    // No descargar el codigo mientras SHFileOperation siga copiando archivos.
    for(HANDLE thread:g_copyThreads) {
        WaitForSingleObject(thread,INFINITE);
        CloseHandle(thread);
    }
    g_copyThreads.clear();
    ShutdownGpuMonitor();
    UnregisterClassW(kClass,GetModuleHandleW(nullptr));
    GdiplusShutdown(token);if(SUCCEEDED(hr))OleUninitialize();
    return 0;
}
} // namespace

BOOL Wh_ModInit(){
    g_mutexHandle=CreateMutexW(nullptr,FALSE,L"Local\\WindhawkIslandPremiumV39OnlyOne");
    if(g_mutexHandle&&GetLastError()==ERROR_ALREADY_EXISTS){CloseHandle(g_mutexHandle);g_mutexHandle=nullptr;return TRUE;}
    g_stopping=false;LoadSettings();
    g_uiThread=CreateThread(nullptr,0,UIThreadMain,nullptr,0,nullptr);
    if(!g_uiThread){
        if(g_mutexHandle){CloseHandle(g_mutexHandle);g_mutexHandle=nullptr;}
        return FALSE;
    }
    return TRUE;
}
void Wh_ModUninit(){
    g_stopping=true;
    HWND hwnd=g_hwnd;
    if(hwnd)PostMessageW(hwnd,WM_CLOSE,0,0);
    if(g_uiThread){WaitForSingleObject(g_uiThread,INFINITE);CloseHandle(g_uiThread);g_uiThread=nullptr;}
    if(g_mutexHandle){CloseHandle(g_mutexHandle);g_mutexHandle=nullptr;}
}
void Wh_ModSettingsChanged(){LoadSettings();HWND hwnd=g_hwnd;if(hwnd)PostMessageW(hwnd,kSettingsChanged,0,0);}
