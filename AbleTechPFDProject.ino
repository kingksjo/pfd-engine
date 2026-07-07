/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║           AbleTechPFDProject — Primary Flight Display v4.0       ║
 * ║        Boeing 787 Dreamliner Style Avionics Instrument           ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  Platform : ESP32 Dual-Core 240 MHz (no PSRAM required)          ║
 * ║  Display  : ILI9488 4.0" 480×320 SPI + XPT2046 Touch            ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  SENSORS                                                         ║
 * ║   BMP280 Pitot  Dynamic Pressure  I2C 0x76  SDO=GND             ║
 * ║   BMP280 Static Pressure+Alt      I2C 0x77  SDO=VCC             ║
 * ║   MPU6050       Roll/Pitch        I2C 0x68  AD0=GND             ║
 * ║   QMC5883P      Compass/Heading   I2C 0x2C  (fixed)             ║
 * ║   DHT11         Temperature       GPIO 4                         ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  REQUIRED LIBRARIES (Arduino Library Manager)                    ║
 * ║   LovyanGFX        — ILI9488 display driver                      ║
 * ║   Adafruit_QMC5883P — QMC5883P compass                           ║
 * ║   MPU6050_light    — MPU6050 by rfetick                          ║
 * ║   DHT sensor       — DHT11 by Adafruit                           ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  v4.0 KEY FIXES                                                   ║
 * ║  [WHITE SCREEN] Root cause: tft.startWrite() wrapped around      ║
 * ║    spr.pushSprite() creates a double SPI lock → bus hangs.       ║
 * ║    Fix: remove startWrite/endWrite from pfdFullFrame().           ║
 * ║    LovyanGFX sprite push manages its own bus transaction.        ║
 * ║  [WHITE SCREEN] bus_shared=true on touch conflicts with display   ║
 * ║    during frame push. Fix: set bus_shared=false on touch and     ║
 * ║    use a dedicated software-CS for XPT2046.                      ║
 * ║  [WHITE SCREEN] SPI.begin() before tft.init() is redundant and   ║
 * ║    can conflict with LovyanGFX own SPI init. Fix: removed.       ║
 * ║  [ALTITUDE] Ground cal now samples 30 readings, seeds Kalman     ║
 * ║    filter, and pins QNH = local ground pressure so display       ║
 * ║    reads 0 ft on startup. Serial command QNH:xxx still works.    ║
 * ║  [DISPLAY] Splash now uses direct tft.print calls (no sprite)    ║
 * ║    so screen is visible even before sprite allocation.           ║
 * ║  [TILES] Removed buggy clipRect calls from tiled renderer;       ║
 * ║    use fillSprite+offsetted draw coords instead — faster.        ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  DUAL-CORE ALLOCATION                                            ║
 * ║   Core 0 — taskSensors : sensors + 7 filters @ 50 Hz            ║
 * ║   Core 1 — taskDisplay : PFD tiles + serial TX @ 50 Hz           ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  SERIAL COMMANDS                                                  ║
 * ║   QNH:1013.25  set altimeter (hPa)                               ║
 * ║   BRT:180      set backlight brightness 20-255                   ║
 * ║   CAL          re-run compass calibration                        ║
 * ║   GNDCAL       re-sample ground pressure and zero altitude       ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  ERROR CODES (see ErrorManual.md)                                ║
 * ║   S-xxx Sensor   D-xxx Display   C-xxx Comms   T-xxx RTOS        ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

// ═══════════════════════════════════════════════════════════
//  INCLUDES
// ═══════════════════════════════════════════════════════════
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <math.h>
#include <MPU6050_light.h>        // Arduino Library Manager: "MPU6050_light"
#include <Adafruit_QMC5883P.h>    // Arduino Library Manager: "Adafruit QMC5883P"
#include <DHT.h>                  // Arduino Library Manager: "DHT sensor library"
#define LGFX_USE_V1
#include <LovyanGFX.hpp>          // Arduino Library Manager: "LovyanGFX"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

// ═══════════════════════════════════════════════════════════
//  USER CONFIGURATION
// ═══════════════════════════════════════════════════════════
#define COMM_SERIAL   0
#define COMM_WIFI     1
#define COMM_MODE     COMM_SERIAL   // change to COMM_WIFI for UDP

#define WIFI_SSID     "YOUR_SSID"
#define WIFI_PASS     "YOUR_PASSWORD"
#define UDP_HOST      "192.168.1.100"
#define UDP_PORT      5005

#define SERIAL_BAUD          921600
#define SENSOR_INTERVAL_MS      20  // 50 Hz

// Local magnetic declination — find at magnetic-declination.com
// Positive = East, Negative = West
#define MAG_DECL_DEG    0.0f

// Compass calibration window (seconds)
#define COMPASS_CAL_SEC   15

// ═══════════════════════════════════════════════════════════
//  PIN DEFINITIONS  — change to match your wiring
// ═══════════════════════════════════════════════════════════
//  ILI9488 SPI
#define TFT_SCLK   18
#define TFT_MOSI   23
#define TFT_MISO   19
#define TFT_CS     15
#define TFT_DC      2
#define TFT_RST    -1   // -1 = tied to EN; set pin number if wired
#define TFT_BL     32   // backlight PWM; -1 to always-on

//  XPT2046 touch (same SPI bus, separate CS)
#define TOUCH_CS   33
#define TOUCH_IRQ  34   // -1 if not wired

//  I2C bus
#define I2C_SDA    21
#define I2C_SCL    22

//  DHT11
#define DHT_PIN     4   // change if your DHT11 is on another GPIO
#define DHT_TYPE   DHT11

// ═══════════════════════════════════════════════════════════
//  I2C ADDRESSES
// ═══════════════════════════════════════════════════════════
#define BMP_PITOT_ADDR  0x76   // BMP280 pitot  (SDO=GND)
#define BMP_STAT_ADDR   0x77   // BMP280 static (SDO=VCC)
#define MPU_ADDR        0x68   // MPU6050       (AD0=GND)
// QMC5883P address 0x2C is fixed; handled by Adafruit library

// ═══════════════════════════════════════════════════════════
//  PHYSICAL CONSTANTS
// ═══════════════════════════════════════════════════════════
#define P0_HPA      1013.25f
#define R_DRY        287.05f
#define LAPSE        0.0065f
#define GRAV         9.80665f
#define GAMMA_AIR    1.4f
#define KTS_PER_MS   1.94384f
#define FT_PER_M     3.28084f
#define D2R          (float)(M_PI / 180.0)
#define R2D          (float)(180.0 / M_PI)

// ═══════════════════════════════════════════════════════════
//  FILTER PARAMETERS  (7 active filters)
// ═══════════════════════════════════════════════════════════
// 1. MPU6050_light internal complementary  (setFilterGyroCoef 0.98)
// 2. Kalman        — altitude
// 3. EMA           — IAS airspeed
// 4. EMA           — VSI vertical speed
// 5. Median 5-tap  — compass heading
// 6. MovAvg 8-tap  — OAT temperature
// 7. Butterworth 2nd-order — roll/pitch display
#define EMA_IAS_A   0.15f
#define EMA_VSI_A   0.08f
#define MED_SIZE       5
#define MAV_SIZE       8
#define BW_FC        4.0f   // Butterworth cut-off Hz

// ═══════════════════════════════════════════════════════════
//  BMP280 REGISTER MAP
// ═══════════════════════════════════════════════════════════
#define BMP_ID      0xD0
#define BMP_RESET   0xE0
#define BMP_CTRL    0xF4
#define BMP_CFG     0xF5
#define BMP_PRESS   0xF7

struct BMP280Cal {
  uint16_t T1; int16_t T2, T3;
  uint16_t P1; int16_t P2, P3, P4, P5, P6, P7, P8, P9;
};

// ═══════════════════════════════════════════════════════════
//  FLIGHT DATA  (shared Core-0 → Core-1)
// ═══════════════════════════════════════════════════════════
struct FlightData {
  float IAS_kts, TAS_kts, Mach;
  float alt_ft, VSI_fpm, QNH_hPa;
  float roll_deg, pitch_deg, hdg_deg;
  float OAT_C, pres_hPa;
  bool  valid;
  uint32_t ts_ms;
};

static FlightData         g_buf[2];
static volatile uint8_t   g_wb = 0;
static volatile uint8_t   g_rb = 1;
static SemaphoreHandle_t  g_mtx = NULL;

// ═══════════════════════════════════════════════════════════
//  LOVYANGFX  ILI9488 CONFIGURATION
// ═══════════════════════════════════════════════════════════
/**
 * WHITE SCREEN FIX — three things that matter:
 *
 * 1. Do NOT call SPI.begin() before tft.init().
 *    LovyanGFX initialises the SPI peripheral itself.
 *    Calling SPI.begin() first can corrupt the internal state.
 *
 * 2. Do NOT call tft.startWrite() / tft.endWrite() around
 *    spr.pushSprite(). The sprite push internally calls
 *    startWrite/endWrite. Double-locking the bus stalls
 *    the ILI9488 and the screen stays white.
 *
 * 3. Set bus_shared = false on the touch panel.
 *    When bus_shared=true the touch driver shares the
 *    display's SPI transaction lock. If the display and
 *    touch poll at the same time the bus deadlocks.
 *    With bus_shared=false the touch uses independent CS
 *    toggling and there is no conflict.
 */
class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_ILI9488  _panel;
  lgfx::Bus_SPI        _bus;
  lgfx::Light_PWM      _light;
  lgfx::Touch_XPT2046  _touch;

public:
  LGFX() {
    // ── SPI bus ───────────────────────────────────────────
    {
      auto c = _bus.config();
      c.spi_host    = VSPI_HOST;
      c.spi_mode    = 0;
      c.freq_write  = 27000000;  // 27 MHz — safe max for most ILI9488 boards
      c.freq_read   =  8000000;
      c.pin_sclk    = TFT_SCLK;
      c.pin_mosi    = TFT_MOSI;
      c.pin_miso    = TFT_MISO;
      c.pin_dc      = TFT_DC;
      _bus.config(c);
      _panel.setBus(&_bus);
    }

    // ── Panel ─────────────────────────────────────────────
    {
      auto c = _panel.config();
      c.pin_cs          = TFT_CS;
      c.pin_rst         = TFT_RST;
      c.pin_busy        = -1;
      c.panel_width     = 320;   // physical pixels in portrait
      c.panel_height    = 480;
      c.offset_rotation = 0;     // ILI9488 native portrait; setRotation(1) gives landscape
      c.invert          = false;
      c.rgb_order       = false;
      c.dlen_16bit      = false;
      c.bus_shared      = true;  // share bus with touch (CS-gated)
      _panel.config(c);
    }

    // ── Backlight ─────────────────────────────────────────
    {
      auto c = _light.config();
      c.pin_bl      = TFT_BL;
      c.invert      = false;
      c.freq        = 12000;
      c.pwm_channel = 7;
      _light.config(c);
      _panel.setLight(&_light);
    }

    // ── Touch XPT2046 ─────────────────────────────────────
    // bus_shared = false → touch uses independent CS toggling,
    // no conflict with display DMA transfers.
    {
      auto c = _touch.config();
      c.x_min          = 300;
      c.x_max          = 3900;
      c.y_min          = 300;
      c.y_max          = 3900;
      c.pin_int        = TOUCH_IRQ;
      c.bus_shared     = false;   // ← KEY FIX for white screen
      c.offset_rotation = 0;
      c.spi_host       = VSPI_HOST;
      c.freq           = 2500000;
      c.pin_sclk       = TFT_SCLK;
      c.pin_mosi       = TFT_MOSI;
      c.pin_miso       = TFT_MISO;
      c.pin_cs         = TOUCH_CS;
      _touch.config(c);
      _panel.setTouch(&_touch);
    }

    setPanel(&_panel);
  }
};

static LGFX        tft;

// ── Tile sprite (480 × TILE_H × 2 bytes = 76 KB) ─────────
// Solves D-001: full 480×320 sprite = 307 KB — too large for
// plain ESP32. We render the screen in 4 horizontal strips.
// IMPORTANT: pushSprite() manages its own SPI transaction.
// Do NOT wrap it in startWrite/endWrite.
#define TILE_H     80     // must divide DH evenly (320/80=4 tiles)
static LGFX_Sprite spr(&tft);
static bool        sprOK = false;

// ═══════════════════════════════════════════════════════════
//  SENSOR OBJECTS
// ═══════════════════════════════════════════════════════════
static MPU6050           mpu(Wire);
static Adafruit_QMC5883P qmc;
static DHT               dht(DHT_PIN, DHT_TYPE);
static BMP280Cal         bmpPitotCal, bmpStatCal;
static int32_t           tFine_pitot = 0, tFine_stat = 0;

static bool bmpPitotOK = false, bmpStatOK = false;
static bool mpuOK      = false, qmcOK     = false, dhtOK = false;

// QMC5883P hard/soft iron calibration
static int16_t qmc_bias[3]  = {0, 0, 0};
static int16_t qmc_scale[3] = {1000, 1000, 1000};
static bool    qmc_calDone  = false;

// ═══════════════════════════════════════════════════════════
//  FILTER STATE
// ═══════════════════════════════════════════════════════════
struct KalmanState { float x = 0, P = 1, Q = 0.05f, R = 1.5f, K = 0; };
static KalmanState kAlt;

static float ema_IAS = 0.0f, ema_VSI = 0.0f;
static float    prevAlt   = -999999.0f;  // sentinel: not yet set
static uint32_t prevAltMs = 0;

static float   medBuf[MED_SIZE] = {};
static uint8_t medIdx = 0;

static float   mavBuf[MAV_SIZE] = {};
static uint8_t mavIdx = 0;
static float   mavSum = 0.0f;

struct Butter2 { float x1=0,x2=0,y1=0,y2=0; float a1,a2,b0,b1,b2; };
static Butter2 bwRoll, bwPitch;

// ═══════════════════════════════════════════════════════════
//  USER ADJUSTABLE (thread-safe via volatile)
// ═══════════════════════════════════════════════════════════
volatile float   g_QNH        = P0_HPA;
volatile uint8_t g_brightness = 200;
volatile bool    g_doGndCal   = false;   // set true to re-zero altitude

#if COMM_MODE == COMM_WIFI
  #include <WiFi.h>
  #include <WiFiUdp.h>
  static WiFiUDP udp;
#endif

// ═══════════════════════════════════════════════════════════
//  PFD LAYOUT  (480 × 320 landscape)
// ═══════════════════════════════════════════════════════════
#define DW  480
#define DH  320

#define FMA_X    78
#define FMA_Y     0
#define FMA_W   324
#define FMA_H    18

#define SPD_X     0
#define SPD_Y    18
#define SPD_W    78
#define SPD_H   240

#define ADI_X    78
#define ADI_Y    18
#define ADI_W   244
#define ADI_H   240
#define ADI_CX  200
#define ADI_CY  138

#define ALT_X   322
#define ALT_Y    18
#define ALT_W    78
#define ALT_H   240

#define VSI_X   400
#define VSI_Y    18
#define VSI_W    20
#define VSI_H   240

#define HSI_X    78
#define HSI_Y   262
#define HSI_W   244
#define HSI_H    50
#define HSI_CX  200

#define OAT_X     0
#define OAT_Y   262
#define OAT_W    78
#define OAT_H    50

#define QNH_X   322
#define QNH_Y   262
#define QNH_W    78
#define QNH_H    50

#define VSID_X  400
#define VSID_Y  262
#define VSID_W   80
#define VSID_H   50

#define INFO_Y  312
#define INFO_H    8

// ═══════════════════════════════════════════════════════════
//  COLOUR PALETTE  (RGB565, Boeing 787 EFIS authentic)
// ═══════════════════════════════════════════════════════════
#define CK_BG      0x000CU
#define CK_PANEL   0x0841U
#define CK_DKGREY  0x2104U
#define CK_GREY    0x7BEFU
#define CK_WHITE   0xFFFFU
#define CK_YELLOW  0xFFE0U
#define CK_CYAN    0x07FFU
#define CK_GREEN   0x07E0U
#define CK_RED     0xF800U
#define CK_AMBER   0xFD20U
#define CK_LTBLUE  0x04DFU
#define CK_EARTH   0x5120U

// ═══════════════════════════════════════════════════════════
//  TILE HELPERS
// ═══════════════════════════════════════════════════════════
// inTile: true if the absolute rectangle [ry .. ry+rh) overlaps
//         the current tile strip [tileY .. tileY+TILE_H)
inline bool inTile(int16_t ry, int16_t rh, int16_t tileY) {
  return (ry < tileY + TILE_H) && (ry + rh > tileY);
}
// ty: convert absolute screen Y to sprite-local Y within this tile
inline int16_t ty(int16_t absY, int16_t tileY) {
  return (int16_t)(absY - tileY);
}
// Type-safe clamp helpers — avoids std::max(int, int16_t) mismatch
inline int16_t imax16(int16_t a, int16_t b) { return a > b ? a : b; }
inline int16_t imin16(int16_t a, int16_t b) { return a < b ? a : b; }

// ═══════════════════════════════════════════════════════════
//  FORWARD DECLARATIONS
// ═══════════════════════════════════════════════════════════
bool    bmpInit(uint8_t addr, BMP280Cal &c);
bool    bmpReadRaw(uint8_t addr, int32_t &rP, int32_t &rT);
float   bmpPres(int32_t rP, int32_t rT, BMP280Cal &c, bool pitot);
void    groundAltCal();
bool    mpuInit();
void    mpuRead(float &roll, float &pitch);
bool    qmcInit();
void    qmcCalibrate();
void    qmcRead(float &fx, float &fy, float &fz);
float   dhtReadTemp();
float   calcIAS(float q_Pa);
float   calcTAS(float IAS, float alt_ft, float oat_C);
float   calcMach(float TAS, float oat_C);
float   calcAlt(float P_hPa, float QNH);
float   kalman(KalmanState &k, float z);
float   ema(float prev, float v, float alpha);
float   medianF(float *buf, uint8_t sz, float v, uint8_t &idx);
float   movAvg(float *buf, uint8_t sz, float &sum, uint8_t &idx, float v);
void    bwInit(Butter2 &f, float fc, float fs);
float   bwStep(Butter2 &f, float x);
void    pfdFullFrame(const FlightData &fd);
void    pfdRenderTile(const FlightData &fd, int16_t tileY);
void    drBackground(int16_t tileY);
void    drFMA(int16_t tileY);
void    drADI(float roll, float pitch, int16_t tileY);
void    drSpdTape(float IAS, float TAS, float Mach, int16_t tileY);
void    drAltTape(float alt, float VSI, int16_t tileY);
void    drVSI(float VSI, int16_t tileY);
void    drHSI(float hdg, int16_t tileY);
void    drOAT(float oat, int16_t tileY);
void    drQNH(float qnh, int16_t tileY);
void    drInfoBar(const FlightData &fd, int16_t tileY);
void    drWarnings(const FlightData &fd, int16_t tileY);
void    splashPrint(const char *msg, uint16_t col, uint8_t size, int16_t y);
void    handleTouch();
void    initComm();
void    txData(const FlightData &fd);
void    i2cWr(uint8_t a, uint8_t r, uint8_t v);
uint8_t i2cRd(uint8_t a, uint8_t r);
void    i2cRdN(uint8_t a, uint8_t r, uint8_t *b, uint8_t n);
void    errP(const char *code, const char *msg);
void    taskSensors(void *pv);
void    taskDisplay(void *pv);

// ═══════════════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════════════
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println(F("\n╔══════════════════════════════════╗"));
  Serial.println(F("║  AbleTechPFDProject  v4.0         ║"));
  Serial.println(F("╚══════════════════════════════════╝"));

  // ── Display FIRST so splash is visible during sensor init ──
  // KEY: do NOT call SPI.begin() — LovyanGFX does it internally.
  // KEY: offset_rotation=0 in LGFX config + setRotation(1) here = landscape.
  // ILI9488 rotation values:
  //   0 = portrait  320×480   (USB top)
  //   1 = landscape 480×320   (USB left)   ← we want this
  //   2 = portrait  320×480   (USB bottom, flipped)
  //   3 = landscape 480×320   (USB right)
  tft.init();
  tft.setColorDepth(16);
  tft.setRotation(1);          // landscape: 480 wide × 320 tall
  tft.setBrightness(g_brightness);

  // Verify rotation worked — width must be 480 in landscape
  if (tft.width() != DW || tft.height() != DH) {
    // Some ILI9488 modules need rotation 3 instead of 1
    // (depends on which corner the flex cable exits)
    Serial.printf("[WARN] setRotation(1) gave %dx%d — trying rotation 3\n",
                  tft.width(), tft.height());
    tft.setRotation(3);
  }
  Serial.printf("[OK] ILI9488 %dx%d (landscape confirmed: %s)\n",
                tft.width(), tft.height(),
                tft.width()==DW ? "YES" : "NO — check offset_rotation");

  tft.fillScreen(CK_BG);

  splashPrint("AbleTechPFDProject v4.0", CK_WHITE,  2,  55);
  splashPrint("Boeing 787 Dreamliner PFD", CK_CYAN,  1,  90);
  splashPrint("AbleTech Systems",           CK_CYAN,  1, 104);
  splashPrint("Initialising sensors...",    CK_AMBER, 1, 130);

  // ── I2C 400 kHz ──────────────────────────────────────────
  Wire.begin(I2C_SDA, I2C_SCL, 400000);

  // ── BMP280 Pitot ─────────────────────────────────────────
  bmpPitotOK = bmpInit(BMP_PITOT_ADDR, bmpPitotCal);
  if (!bmpPitotOK) errP("S-001","BMP280 Pitot 0x76 not found — SDO must be GND");
  else Serial.println(F("[OK] BMP280 Pitot  0x76"));

  // ── BMP280 Static ────────────────────────────────────────
  bmpStatOK = bmpInit(BMP_STAT_ADDR, bmpStatCal);
  if (!bmpStatOK) errP("S-002","BMP280 Static 0x77 not found — SDO must be VCC");
  else Serial.println(F("[OK] BMP280 Static 0x77"));

  // ── Ground altitude calibration ──────────────────────────
  // Samples static pressure 30× to find P_ground, then sets
  // QNH = P_ground so the hypsometric formula returns 0 ft.
  // This removes the false high altitude reading at ground level.
  if (bmpStatOK) {
    groundAltCal();
  }

  // ── MPU6050 ──────────────────────────────────────────────
  splashPrint("MPU6050: calibrating... keep flat", CK_AMBER, 1, 150);
  mpuOK = mpuInit();
  if (!mpuOK) errP("S-003","MPU6050 init failed — check AD0=GND, wiring, power");
  else { Serial.println(F("[OK] MPU6050  0x68")); }

  // ── QMC5883P ─────────────────────────────────────────────
  qmcOK = qmcInit();
  if (!qmcOK) errP("S-004","QMC5883P not found — check I2C wiring 0x2C");
  else Serial.println(F("[OK] QMC5883P 0x2C"));

  // ── DHT11 ────────────────────────────────────────────────
  dht.begin(); delay(200);
  float tst = dht.readTemperature();
  dhtOK = !isnan(tst);
  if (!dhtOK) errP("S-005","DHT11 no response — check GPIO4, 10k pull-up to 3.3V");
  else Serial.printf("[OK] DHT11 GPIO%d  %.1fC\n", DHT_PIN, tst);

  // ── Sprite allocation ────────────────────────────────────
  spr.setColorDepth(16);
  sprOK = spr.createSprite(DW, TILE_H);
  if (!sprOK) {
    // Try half-height fallback
    sprOK = spr.createSprite(DW, TILE_H / 2);
    if (sprOK)
      errP("D-001","Full tile failed; using half-tile (40px). Display may be slower.");
    else
      errP("D-002","Sprite alloc failed completely. Direct-draw mode active.");
  } else {
    Serial.printf("[OK] Sprite %dx%d  free heap: %d B\n",
                  DW, TILE_H, (int)esp_get_free_heap_size());
  }

  // ── Butterworth filter init ───────────────────────────────
  float fs = 1000.0f / SENSOR_INTERVAL_MS;
  bwInit(bwRoll,  BW_FC, fs);
  bwInit(bwPitch, BW_FC, fs);

  // ── Communication ────────────────────────────────────────
  initComm();

  // ── FreeRTOS mutex ───────────────────────────────────────
  g_mtx = xSemaphoreCreateMutex();
  if (!g_mtx) { errP("T-001","Mutex alloc failed — halted"); while (1); }

  // ── Sensor status splash ─────────────────────────────────
  tft.fillScreen(CK_BG);
  splashPrint("AbleTechPFDProject v4.0", CK_WHITE, 2, 40);
  char sb[96];
  snprintf(sb, 96, "BMP-P:%s  BMP-S:%s  MPU:%s",
           bmpPitotOK?"OK":"--", bmpStatOK?"OK":"--", mpuOK?"OK":"--");
  splashPrint(sb, CK_GREEN, 1, 82);
  snprintf(sb, 96, "QMC:%s  DHT:%s  SPR:%s",
           qmcOK?"OK":"--", dhtOK?"OK":"--", sprOK?"OK":"--");
  splashPrint(sb, CK_GREEN, 1, 96);
  char qb[40];
  snprintf(qb, 40, "Ground QNH: %.2f hPa -> 0 ft", (float)g_QNH);
  splashPrint(qb, CK_YELLOW, 1, 114);
  splashPrint(qmcOK ? "Starting compass calibration..." : "Starting PFD display...",
              CK_AMBER, 1, 136);

  // ── Compass calibration ───────────────────────────────────
  if (qmcOK) qmcCalibrate();

  // ── Final ready ──────────────────────────────────────────
  tft.fillScreen(CK_BG);
  splashPrint("SYSTEM READY", CK_GREEN, 2, 130);
  splashPrint("Launching PFD...", CK_WHITE, 1, 165);
  delay(400);

  // ── Launch dual-core tasks ────────────────────────────────
  if (xTaskCreatePinnedToCore(taskSensors,"Sensors",12288,NULL,2,NULL,0) != pdPASS)
    errP("T-002","Sensor task create failed — check heap");
  if (xTaskCreatePinnedToCore(taskDisplay,"Display",20480,NULL,1,NULL,1) != pdPASS)
    errP("T-003","Display task create failed — check heap");

  Serial.println(F("[OK] Tasks running — PFD ACTIVE\n"));
}

void loop() { vTaskDelete(NULL); }

// ═══════════════════════════════════════════════════════════
//  GROUND ALTITUDE CALIBRATION
// ═══════════════════════════════════════════════════════════
/**
 * groundAltCal — samples the static BMP280 30 times, averages
 * the result, and sets QNH = ground pressure.
 * The hypsometric formula then returns exactly 0 ft at ground.
 * Also seeds the Kalman filter and prevAlt to 0 so the altitude
 * display starts at 0 ft immediately with no transient.
 *
 * Can be re-triggered at runtime via serial command "GNDCAL".
 */
void groundAltCal() {
  Serial.println(F("[GND] Ground pressure calibration..."));
  float sumPa    = 0.0f;
  uint8_t good   = 0;
  for (uint8_t i = 0; i < 30; i++) {
    delay(30);   // BMP280 in normal mode updates every ~26 ms
    int32_t rP, rT;
    if (bmpReadRaw(BMP_STAT_ADDR, rP, rT)) {
      float Pa = bmpPres(rP, rT, bmpStatCal, false);
      if (Pa > 50000.0f && Pa < 110000.0f) {
        sumPa += Pa;
        good++;
      }
    }
  }
  if (good >= 10) {
    float groundHpa = (sumPa / good) / 100.0f;
    g_QNH    = groundHpa;
    // Seed Kalman and prevAlt so the first sensor cycle
    // shows 0 ft instead of the uncalibrated ISA altitude.
    kAlt.x   = 0.0f;
    kAlt.P   = 1.0f;
    prevAlt  = 0.0f;
    prevAltMs = millis();
    Serial.printf("[GND] Samples=%d  P_ground=%.2f hPa  QNH=%.2f  -> 0 ft\n",
                  good, groundHpa, (float)g_QNH);
  } else {
    errP("S-020","Ground cal: fewer than 10 good samples. Using ISA QNH=1013.25");
    Serial.println(F("[GND] Altitude will show pressure altitude, not AGL."));
  }
}

// ═══════════════════════════════════════════════════════════
//  TASK — CORE 0 : SENSORS + 7 FILTERS
// ═══════════════════════════════════════════════════════════
/**
 * taskSensors — 50 Hz on Core 0.
 * Reads all 5 sensors, applies all 7 filters, computes
 * aerodynamic parameters, and writes to the inactive buffer.
 *
 * Filter chain:
 *  1. MPU6050_light internal complementary (gyro coef 0.98)
 *  2. Kalman              — altitude noise
 *  3. EMA α=0.15          — IAS smoothing
 *  4. EMA α=0.08          — VSI derivative smoothing
 *  5. Median 5-tap        — compass heading spike rejection
 *  6. MovAvg 8-tap        — OAT quantisation noise
 *  7. Butterworth 2nd-ord — roll/pitch for ADI display
 */
void taskSensors(void *pv) {
  Serial.println(F("[T0] Sensor task online — Core 0"));
  TickType_t xLast = xTaskGetTickCount();

  // Init prevAltMs to now (prevents VSI spike on first cycle)
  prevAltMs = millis();

  while (true) {

    // Check if ground re-cal was requested
    if (g_doGndCal) {
      g_doGndCal = false;
      if (bmpStatOK) groundAltCal();
    }

    // ── Read BMP280 Static ───────────────────────────────
    int32_t rPs = 0, rTs = 0;
    float statHpa = (float)g_QNH;   // safe fallback
    if (bmpStatOK && bmpReadRaw(BMP_STAT_ADDR, rPs, rTs)) {
      float Pa = bmpPres(rPs, rTs, bmpStatCal, false);
      if (Pa > 50000.0f) statHpa = Pa / 100.0f;
    }

    // ── Read BMP280 Pitot (dynamic = pitot − static) ─────
    int32_t rPd = 0, rTd = 0;
    float dynPa = 0.0f;
    if (bmpPitotOK && bmpReadRaw(BMP_PITOT_ADDR, rPd, rTd)) {
      float pitPa = bmpPres(rPd, rTd, bmpPitotCal, true);
      float diff  = pitPa - (statHpa * 100.0f);
      dynPa = (diff > 0.0f) ? diff : 0.0f;
    }

    // ── Read MPU6050 (Filter 1 built into library) ───────
    float roll_raw = 0.0f, pitch_raw = 0.0f;
    if (mpuOK) mpuRead(roll_raw, pitch_raw);

    // ── Read QMC5883P ────────────────────────────────────
    float mx = 1.0f, my = 0.0f, mz = 0.0f;
    if (qmcOK) qmcRead(mx, my, mz);

    // ── Read DHT11 ───────────────────────────────────────
    float oat_raw = dhtReadTemp();

    // ── Filter 7 — Butterworth on roll/pitch ─────────────
    float roll_f  = bwStep(bwRoll,  roll_raw);
    float pitch_f = bwStep(bwPitch, pitch_raw);

    // ── IAS — Bernoulli / compressible CAS ───────────────
    float IAS_raw = calcIAS(dynPa);
    // ── Filter 3 — EMA on IAS ────────────────────────────
    ema_IAS = ema(ema_IAS, IAS_raw, EMA_IAS_A);

    // ── Altitude — ISA hypsometric ───────────────────────
    float alt_raw = calcAlt(statHpa, (float)g_QNH);
    // ── Filter 2 — Kalman on altitude ────────────────────
    float alt_f   = kalman(kAlt, alt_raw);

    // ── VSI — derivative of filtered altitude ────────────
    uint32_t nowMs = millis();
    float VSI_raw  = 0.0f;
    if (prevAlt > -900000.0f) {
      float dtSec = (nowMs - prevAltMs) * 0.001f;
      if (dtSec > 0.001f)
        VSI_raw = (alt_f - prevAlt) / dtSec * 60.0f;
    }
    VSI_raw  = constrain(VSI_raw, -6000.0f, 6000.0f);
    prevAlt  = alt_f;
    prevAltMs = nowMs;

    // ── Filter 4 — EMA on VSI ────────────────────────────
    ema_VSI = ema(ema_VSI, VSI_raw, EMA_VSI_A);

    // ── Filter 6 — Moving average on OAT ─────────────────
    float oat_f = movAvg(mavBuf, MAV_SIZE, mavSum, mavIdx, oat_raw);

    // ── TAS + Mach ───────────────────────────────────────
    float TAS  = calcTAS(ema_IAS, alt_f, oat_f);
    float Mach = calcMach(TAS, oat_f);

    // ── Tilt-compensated heading (Freescale AN4248) ───────
    float rr = roll_f  * D2R;
    float pr = pitch_f * D2R;
    float Xh = mx * cosf(pr) + mz * sinf(pr);
    float Yh = mx * sinf(rr) * sinf(pr) + my * cosf(rr)
              - mz * sinf(rr) * cosf(pr);
    float hdg_raw = atan2f(-Yh, Xh) * R2D + MAG_DECL_DEG;
    if (hdg_raw < 0)    hdg_raw += 360.0f;
    if (hdg_raw >= 360) hdg_raw -= 360.0f;

    // ── Filter 5 — Median on heading ─────────────────────
    float hdg_f = medianF(medBuf, MED_SIZE, hdg_raw, medIdx);

    // ── Write inactive buffer, swap ───────────────────────
    uint8_t wb = g_wb;
    g_buf[wb] = {
      ema_IAS, TAS, Mach,
      alt_f, ema_VSI, (float)g_QNH,
      roll_f, pitch_f, hdg_f,
      oat_f, statHpa,
      (bmpStatOK || bmpPitotOK || mpuOK),
      nowMs
    };
    if (xSemaphoreTake(g_mtx, pdMS_TO_TICKS(5)) == pdTRUE) {
      g_wb = g_rb; g_rb = wb;
      xSemaphoreGive(g_mtx);
    } else {
      errP("T-010","Buffer swap timeout");
    }

    vTaskDelayUntil(&xLast, pdMS_TO_TICKS(SENSOR_INTERVAL_MS));
  }
}

// ═══════════════════════════════════════════════════════════
//  TASK — CORE 1 : DISPLAY + COMMS + TOUCH
// ═══════════════════════════════════════════════════════════
void taskDisplay(void *pv) {
  Serial.println(F("[T1] Display task online — Core 1"));
  TickType_t xLast = xTaskGetTickCount();

  // Draw initial blank PFD immediately so screen is not dark
  FlightData blank{};
  blank.QNH_hPa = (float)g_QNH;
  blank.OAT_C   = 15.0f;
  pfdFullFrame(blank);

  while (true) {
    // Snapshot latest data
    FlightData fd{};
    if (xSemaphoreTake(g_mtx, pdMS_TO_TICKS(5)) == pdTRUE) {
      fd = g_buf[g_rb];
      xSemaphoreGive(g_mtx);
    }

    pfdFullFrame(fd);

    if (fd.valid) txData(fd);

    handleTouch();

    // Serial commands
    if (Serial.available()) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      if (cmd.startsWith("QNH:")) {
        float q = cmd.substring(4).toFloat();
        if (q > 900.0f && q < 1100.0f) {
          g_QNH = q;
          Serial.printf("[CMD] QNH=%.2f hPa\n", q);
        } else errP("C-010","QNH out of range 900-1100");
      } else if (cmd.startsWith("BRT:")) {
        g_brightness = (uint8_t)constrain(cmd.substring(4).toInt(), 20, 255);
        tft.setBrightness(g_brightness);
        Serial.printf("[CMD] Brightness=%d\n", (int)g_brightness);
      } else if (cmd == "CAL" && qmcOK) {
        qmcCalibrate();
      } else if (cmd == "GNDCAL") {
        g_doGndCal = true;
        Serial.println(F("[CMD] Ground cal queued"));
      }
    }

    vTaskDelayUntil(&xLast, pdMS_TO_TICKS(SENSOR_INTERVAL_MS));
  }
}

// ═══════════════════════════════════════════════════════════
//  BMP280 DRIVER
// ═══════════════════════════════════════════════════════════
bool bmpInit(uint8_t addr, BMP280Cal &c) {
  uint8_t id = i2cRd(addr, BMP_ID);
  if (id != 0x60 && id != 0x58) {
    Serial.printf("[ERR] BMP280 @0x%02X ID=0x%02X (want 0x60 or 0x58)\n", addr, id);
    return false;
  }
  i2cWr(addr, BMP_RESET, 0xB6); delay(10);
  uint8_t cb[24]; i2cRdN(addr, 0x88, cb, 24);
  c.T1=(uint16_t)((cb[1]<<8)|cb[0]); c.T2=(int16_t)((cb[3]<<8)|cb[2]);
  c.T3=(int16_t)((cb[5]<<8)|cb[4]);
  c.P1=(uint16_t)((cb[7]<<8)|cb[6]); c.P2=(int16_t)((cb[9]<<8)|cb[8]);
  c.P3=(int16_t)((cb[11]<<8)|cb[10]);c.P4=(int16_t)((cb[13]<<8)|cb[12]);
  c.P5=(int16_t)((cb[15]<<8)|cb[14]);c.P6=(int16_t)((cb[17]<<8)|cb[16]);
  c.P7=(int16_t)((cb[19]<<8)|cb[18]);c.P8=(int16_t)((cb[21]<<8)|cb[20]);
  c.P9=(int16_t)((cb[23]<<8)|cb[22]);
  i2cWr(addr, BMP_CFG,  0x10);  // IIR=4, t_sb=0.5ms
  i2cWr(addr, BMP_CTRL, 0x93);  // T×4, P×4, normal mode
  delay(10);
  return true;
}

bool bmpReadRaw(uint8_t addr, int32_t &rP, int32_t &rT) {
  uint8_t d[6]; i2cRdN(addr, BMP_PRESS, d, 6);
  rP = ((int32_t)d[0]<<12)|((int32_t)d[1]<<4)|(d[2]>>4);
  rT = ((int32_t)d[3]<<12)|((int32_t)d[4]<<4)|(d[5]>>4);
  return !(rP == 0 && rT == 0);
}

float bmpPres(int32_t rP, int32_t rT, BMP280Cal &c, bool pitot) {
  int32_t v1 = ((((rT>>3)-((int32_t)c.T1<<1)))*c.T2)>>11;
  int32_t v2 = (((((rT>>4)-(int32_t)c.T1)*((rT>>4)-(int32_t)c.T1))>>12)*c.T3)>>14;
  int32_t tf = v1+v2;
  if (pitot) tFine_pitot=tf; else tFine_stat=tf;
  int64_t p1=(int64_t)tf-128000LL;
  int64_t p2=p1*p1*(int64_t)c.P6;
  p2+=(p1*(int64_t)c.P5)<<17; p2+=((int64_t)c.P4)<<35;
  p1=((p1*p1*(int64_t)c.P3)>>8)+((p1*(int64_t)c.P2)<<12);
  p1=(((1LL<<47)+p1)*(int64_t)c.P1)>>33;
  if (!p1) return 0.0f;
  int64_t p=1048576LL-rP;
  p=(((p<<31)-p2)*3125LL)/p1;
  p1=((int64_t)c.P9*(p>>13)*(p>>13))>>25;
  p2=((int64_t)c.P8*p)>>19;
  p=((p+p1+p2)>>8)+((int64_t)c.P7<<4);
  return (float)p/256.0f;  // Pascals
}

// ═══════════════════════════════════════════════════════════
//  MPU6050  (MPU6050_light)
// ═══════════════════════════════════════════════════════════
bool mpuInit() {
  byte s = mpu.begin();
  if (s != 0) {
    Serial.printf("[ERR][S-003] MPU6050_light begin()=%d\n", s);
    return false;
  }
  mpu.calcOffsets(true, true);   // gyro + accel auto-cal (keep sensor flat!)
  mpu.setFilterGyroCoef(0.98f);  // complementary filter weight
  return true;
}

void mpuRead(float &roll, float &pitch) {
  mpu.update();
  roll  = mpu.getAngleX();
  pitch = mpu.getAngleY();
}

// ═══════════════════════════════════════════════════════════
//  QMC5883P  (Adafruit_QMC5883P)
// ═══════════════════════════════════════════════════════════
bool qmcInit() {
  if (!qmc.begin()) return false;
  qmc.setMode(QMC5883P_MODE_CONTINUOUS);
  qmc.setRange(QMC5883P_RANGE_8G);
  qmc.setOSR(QMC5883P_OSR_8);
  return true;
}

void qmcCalibrate() {
  tft.fillScreen(CK_BG);
  splashPrint("COMPASS CALIBRATION",          CK_YELLOW, 2,  44);
  splashPrint("Rotate sensor in full 3D figure-8", CK_WHITE, 1,  88);
  splashPrint("Cover all headings + tilt angles",  CK_WHITE, 1, 102);
  char cb[40]; snprintf(cb,40,"Duration: %d seconds",COMPASS_CAL_SEC);
  splashPrint(cb, CK_CYAN, 1, 118);
  splashPrint("Starting in 2 seconds...", CK_AMBER, 1, 140);
  Serial.println(F("[CAL] Compass calibration — rotate now"));
  delay(2000);

  int16_t mnX=30000,mxX=-30000,mnY=30000,mxY=-30000,mnZ=30000,mxZ=-30000;
  uint32_t n=0, t0=millis(), dur=(uint32_t)COMPASS_CAL_SEC*1000;
  uint8_t lastSec=255;

  while (millis()-t0 < dur) {
    if (qmc.isDataReady()) {
      float fx,fy,fz;
      if (qmc.getGaussField(&fx,&fy,&fz)) {
        int16_t ix=(int16_t)(fx*1000),iy=(int16_t)(fy*1000),iz=(int16_t)(fz*1000);
        if(ix<mnX)mnX=ix; if(ix>mxX)mxX=ix;
        if(iy<mnY)mnY=iy; if(iy>mxY)mxY=iy;
        if(iz<mnZ)mnZ=iz; if(iz>mxZ)mxZ=iz;
        n++;
      }
    }
    uint8_t sec=(uint8_t)((millis()-t0)/1000);
    if (sec!=lastSec) {
      Serial.printf("[CAL] %2ds n=%lu\n",sec,n);
      lastSec=sec;
      tft.fillRect(40,180,400,18,CK_BG);
      uint16_t bw=(uint16_t)(400UL*sec/COMPASS_CAL_SEC);
      tft.fillRect(40,182,bw,14,CK_GREEN);
      tft.drawRect(40,182,400,14,CK_GREY);
      char pb[20]; snprintf(pb,20,"%d / %d s",sec,COMPASS_CAL_SEC);
      tft.setTextColor(CK_WHITE); tft.drawCenterString(pb,DW/2,202);
    }
    delay(5);
  }

  qmc_bias[0]=(mxX+mnX)/2; qmc_bias[1]=(mxY+mnY)/2; qmc_bias[2]=(mxZ+mnZ)/2;
  int16_t rx=mxX-mnX,ry=mxY-mnY,rz=mxZ-mnZ;
  int16_t ra=(rx+ry+rz)/3;
  if(rx>0) qmc_scale[0]=(int16_t)(((int32_t)ra*1000)/rx);
  if(ry>0) qmc_scale[1]=(int16_t)(((int32_t)ra*1000)/ry);
  if(rz>0) qmc_scale[2]=(int16_t)(((int32_t)ra*1000)/rz);
  qmc_calDone=true;

  Serial.printf("[CAL] Done n=%lu Bias=%d,%d,%d Scale=%d,%d,%d\n",
    n,qmc_bias[0],qmc_bias[1],qmc_bias[2],qmc_scale[0],qmc_scale[1],qmc_scale[2]);
  tft.fillScreen(CK_BG);
  splashPrint("CAL COMPLETE", CK_GREEN, 2, 135);
  delay(800);
}

void qmcRead(float &fx, float &fy, float &fz) {
  static float lx=1,ly=0,lz=0;
  if (!qmc.isDataReady()) { fx=lx; fy=ly; fz=lz; return; }
  float rx,ry,rz;
  if (!qmc.getGaussField(&rx,&ry,&rz)) {
    errP("S-040","QMC getGaussField failed"); fx=lx; fy=ly; fz=lz; return;
  }
  int32_t cx=((int32_t)(rx*1000)-qmc_bias[0])*qmc_scale[0]/1000;
  int32_t cy=((int32_t)(ry*1000)-qmc_bias[1])*qmc_scale[1]/1000;
  int32_t cz=((int32_t)(rz*1000)-qmc_bias[2])*qmc_scale[2]/1000;
  fx=lx=(float)cx/1000.f;
  fy=ly=(float)cy/1000.f;
  fz=lz=(float)cz/1000.f;
}

// ═══════════════════════════════════════════════════════════
//  DHT11
// ═══════════════════════════════════════════════════════════
float dhtReadTemp() {
  static float last = 15.0f;
  float t = dht.readTemperature();
  if (!isnan(t) && t > -40.0f && t < 85.0f) last = t;
  return last;
}

// ═══════════════════════════════════════════════════════════
//  AERODYNAMIC FORMULAS
// ═══════════════════════════════════════════════════════════
float calcIAS(float q_Pa) {
  if (q_Pa < 0.5f) return 0.0f;
  float rat = q_Pa / (P0_HPA * 100.0f) + 1.0f;
  float t   = powf(rat, 2.0f/7.0f) - 1.0f;
  return (t <= 0.0f) ? 0.0f : 340.29f * sqrtf(5.0f*t) * KTS_PER_MS;
}
float calcTAS(float IAS, float alt_ft, float oat_C) {
  float Tk = oat_C + 273.15f;
  float Ti = 288.15f - LAPSE*(alt_ft/FT_PER_M);
  if (Ti < 216.65f) Ti = 216.65f;
  return IAS * sqrtf(Tk/Ti);
}
float calcMach(float TAS, float oat_C) {
  float a = sqrtf(GAMMA_AIR * R_DRY * (oat_C+273.15f));
  return (TAS/KTS_PER_MS) / a;
}
float calcAlt(float P_hPa, float QNH) {
  if (QNH   < 1.0f) QNH   = P0_HPA;
  if (P_hPa < 1.0f) return 0.0f;
  return (288.15f/LAPSE) * (1.0f - powf(P_hPa/QNH, R_DRY*LAPSE/GRAV)) * FT_PER_M;
}

// ═══════════════════════════════════════════════════════════
//  FILTERS
// ═══════════════════════════════════════════════════════════
float kalman(KalmanState &k, float z) {
  k.P+=k.Q; k.K=k.P/(k.P+k.R); k.x+=k.K*(z-k.x); k.P*=(1.0f-k.K); return k.x;
}
float ema(float p, float v, float a) { return a*v+(1.0f-a)*p; }
float medianF(float *buf, uint8_t sz, float v, uint8_t &idx) {
  buf[idx%sz]=v; idx++;
  float s[MED_SIZE]; memcpy(s,buf,sz*sizeof(float));
  for(uint8_t i=1;i<sz;i++){float k=s[i];int8_t j=i-1;
    while(j>=0&&s[j]>k){s[j+1]=s[j];j--;}s[j+1]=k;}
  return s[sz/2];
}
float movAvg(float *buf, uint8_t sz, float &sum, uint8_t &idx, float v) {
  sum-=buf[idx%sz]; buf[idx%sz]=v; sum+=v; idx++; return sum/(float)sz;
}
void bwInit(Butter2 &f, float fc, float fs) {
  float w=tanf((float)M_PI*fc/fs), a=1+(float)M_SQRT2*w+w*w;
  f.b0=w*w/a; f.b1=2*f.b0; f.b2=f.b0;
  f.a1=2*(w*w-1)/a; f.a2=(1-(float)M_SQRT2*w+w*w)/a;
  f.x1=f.x2=f.y1=f.y2=0;
}
float bwStep(Butter2 &f, float x) {
  float y=f.b0*x+f.b1*f.x1+f.b2*f.x2-f.a1*f.y1-f.a2*f.y2;
  f.x2=f.x1;f.x1=x;f.y2=f.y1;f.y1=y;return y;
}

// ═══════════════════════════════════════════════════════════
//  PFD TILED RENDERER
// ═══════════════════════════════════════════════════════════
/**
 * pfdFullFrame — renders the complete 480×320 PFD in 4 tile passes.
 *
 * WHITE SCREEN FIX:
 * Do NOT call tft.startWrite() / tft.endWrite() here.
 * spr.pushSprite() internally wraps its SPI transfer in
 * startWrite/endWrite. If you double-lock the bus the ILI9488
 * controller stalls and the screen stays white permanently.
 *
 * Simply call spr.pushSprite(x, y) directly — LovyanGFX
 * manages the bus transaction automatically and correctly.
 */
void pfdFullFrame(const FlightData &fd) {
  if (!sprOK) {
    // Sprite unavailable — direct minimal draw so screen is not blank
    tft.fillScreen(CK_BG);
    tft.setTextColor(CK_CYAN);
    tft.setTextSize(1);
    tft.drawCenterString("AbleTechPFD - Low Memory Mode", DW/2, DH/2-6);
    char ab[32];
    snprintf(ab,32,"ALT: %.0f ft  IAS: %.0f kts", fd.alt_ft, fd.IAS_kts);
    tft.setTextColor(CK_WHITE);
    tft.drawCenterString(ab, DW/2, DH/2+8);
    return;
  }
  for (int16_t tileY = 0; tileY < DH; tileY += TILE_H) {
    pfdRenderTile(fd, tileY);
    // Direct push — NO startWrite/endWrite wrapper
    spr.pushSprite(0, tileY);
  }
}

void pfdRenderTile(const FlightData &fd, int16_t tileY) {
  spr.fillSprite(CK_BG);
  drBackground(tileY);
  drFMA(tileY);
  drADI(fd.roll_deg, fd.pitch_deg, tileY);
  drSpdTape(fd.IAS_kts, fd.TAS_kts, fd.Mach, tileY);
  drAltTape(fd.alt_ft, fd.VSI_fpm, tileY);
  drVSI(fd.VSI_fpm, tileY);
  drHSI(fd.hdg_deg, tileY);
  drOAT(fd.OAT_C, tileY);
  drQNH(fd.QNH_hPa, tileY);
  drInfoBar(fd, tileY);
  drWarnings(fd, tileY);
}

// ─────────────────────────────────────────────────────────
//  BACKGROUND
// ─────────────────────────────────────────────────────────
void drBackground(int16_t tileY) {
  auto fillR=[&](int16_t rx,int16_t ry,int16_t rw,int16_t rh,uint16_t c){
    if(!inTile(ry,rh,tileY))return;
    int16_t sy=ty(ry,tileY);
    int16_t sh=imin16(rh, (int16_t)(tileY+TILE_H-ry));
    if(sy<0){sh+=sy;sy=0;}
    if(sh>0) spr.fillRect(rx,sy,rw,sh,c);
  };
  auto rectR=[&](int16_t rx,int16_t ry,int16_t rw,int16_t rh,uint16_t c){
    if(!inTile(ry,rh,tileY))return;
    spr.drawRect(rx,ty(ry,tileY),rw,rh,c);
  };
  fillR(SPD_X,SPD_Y,SPD_W,SPD_H,CK_PANEL);  rectR(SPD_X,SPD_Y,SPD_W-1,SPD_H,CK_GREY);
  fillR(ALT_X,ALT_Y,ALT_W,ALT_H,CK_PANEL);  rectR(ALT_X,ALT_Y,ALT_W,  ALT_H,CK_GREY);
  fillR(VSI_X,VSI_Y,VSI_W,VSI_H,CK_DKGREY); rectR(VSI_X,VSI_Y,VSI_W-1,VSI_H,CK_GREY);
  fillR(OAT_X,OAT_Y,OAT_W,OAT_H,CK_PANEL);
  fillR(HSI_X,HSI_Y,HSI_W,HSI_H,CK_PANEL);  rectR(HSI_X,HSI_Y,HSI_W,  HSI_H,CK_GREY);
  fillR(QNH_X,QNH_Y,QNH_W,QNH_H,CK_PANEL);
  fillR(VSID_X,VSID_Y,VSID_W,VSID_H,CK_PANEL);
  fillR(0,INFO_Y,DW,INFO_H,0x0820U);
  // Outer border lines clipped to this tile
  if(tileY==0) spr.drawFastHLine(0,0,DW,CK_GREY);
  if(tileY+TILE_H>=DH) spr.drawFastHLine(0,ty(DH-1,tileY),DW,CK_GREY);
  spr.drawFastVLine(0,0,TILE_H,CK_GREY);
  spr.drawFastVLine(DW-1,0,TILE_H,CK_GREY);
}

// ─────────────────────────────────────────────────────────
//  FMA — Flight Mode Annunciator
// ─────────────────────────────────────────────────────────
void drFMA(int16_t tileY) {
  if(!inTile(FMA_Y,FMA_H,tileY)) return;
  int16_t sy=ty(FMA_Y,tileY);
  spr.fillRect(FMA_X,sy,FMA_W,FMA_H,CK_DKGREY);
  spr.drawRect(FMA_X,sy,FMA_W-1,FMA_H-1,CK_GREY);
  spr.setTextSize(1);
  int cw=FMA_W/3;
  spr.setTextColor(CK_GREEN);  spr.drawString("SPEED",    FMA_X+6,        sy+5);
  spr.setTextColor(CK_WHITE);  spr.drawString("HDG SEL",  FMA_X+cw+4,     sy+5);
  spr.setTextColor(CK_CYAN);   spr.drawString("VNAV PTH", FMA_X+2*cw+8,   sy+5);
}

// ─────────────────────────────────────────────────────────
//  ADI — Attitude Direction Indicator
// ─────────────────────────────────────────────────────────
/**
 * Renders the artificial horizon for the tile band [tileY, tileY+TILE_H).
 * Sky/earth fill uses the tile's sprite-local coordinates.
 * No setClipRect is used (causes issues with tiling); instead
 * all geometry is computed in sprite-local space.
 */
void drADI(float roll, float pitch, int16_t tileY) {
  if(!inTile(ADI_Y,ADI_H,tileY)) return;

  const float PPD = 3.0f;
  float rollR = roll * D2R;
  float cosR  = cosf(rollR), sinR = sinf(rollR);
  float py    = pitch * PPD;   // horizon pixel offset (+ = nose up = horizon down)

  // ADI centre in sprite-local Y
  int16_t acy = ty(ADI_CY, tileY);

  // Sky fill — fill entire ADI column of this tile with sky
  int16_t ady_top = imax16(ty(ADI_Y,tileY), (int16_t)0);
  int16_t ady_bot = imin16(ty(ADI_Y+ADI_H,tileY), (int16_t)TILE_H);
  if(ady_top < ady_bot)
    spr.fillRect(ADI_X, ady_top, ADI_W, ady_bot-ady_top, CK_LTBLUE);

  // Earth polygon (rotated trapezoid below horizon line)
  float hw = ADI_W*0.6f, hh = ADI_H*0.65f;
  float pts[4][2] = {
    {-hw,-py},{hw,-py},{hw,hh+fabsf(py)+10},{-hw,hh+fabsf(py)+10}
  };
  int16_t ex[4],ey[4];
  for(int i=0;i<4;i++){
    ex[i]=(int16_t)(ADI_CX + pts[i][0]*cosR - pts[i][1]*sinR);
    ey[i]=(int16_t)(acy    + pts[i][0]*sinR + pts[i][1]*cosR);
  }
  spr.fillTriangle(ex[0],ey[0],ex[1],ey[1],ex[2],ey[2],CK_EARTH);
  spr.fillTriangle(ex[0],ey[0],ex[2],ey[2],ex[3],ey[3],CK_EARTH);

  // Horizon line (2 px)
  float hLen=ADI_W*0.53f;
  int16_t hx1=(int16_t)(ADI_CX - hLen*cosR + py*sinR);
  int16_t hy1=(int16_t)(acy    - hLen*sinR - py*cosR);
  int16_t hx2=(int16_t)(ADI_CX + hLen*cosR + py*sinR);
  int16_t hy2=(int16_t)(acy    + hLen*sinR - py*cosR);
  spr.drawLine(hx1,hy1,hx2,hy2,CK_WHITE);
  spr.drawLine(hx1+1,hy1,hx2+1,hy2,CK_WHITE);

  // Pitch ladder ±30°
  spr.setTextSize(1); spr.setTextColor(CK_WHITE);
  for(int deg=-30;deg<=30;deg+=5){
    if(deg==0) continue;
    float pOff=-(deg-pitch)*PPD;
    float len=(deg%10==0)?ADI_W*0.22f:ADI_W*0.12f;
    int16_t lx1=(int16_t)(ADI_CX-(len/2)*cosR-pOff*sinR);
    int16_t ly1=(int16_t)(acy   -(len/2)*sinR+pOff*cosR);
    int16_t lx2=(int16_t)(ADI_CX+(len/2)*cosR-pOff*sinR);
    int16_t ly2=(int16_t)(acy   +(len/2)*sinR+pOff*cosR);
    spr.drawLine(lx1,ly1,lx2,ly2,CK_WHITE);
    if(deg%10==0){
      int8_t cv=(deg>0)?5:-5;
      spr.drawLine(lx1,ly1,(int16_t)(lx1+cv*sinR),(int16_t)(ly1+cv*cosR),CK_WHITE);
      spr.drawLine(lx2,ly2,(int16_t)(lx2+cv*sinR),(int16_t)(ly2+cv*cosR),CK_WHITE);
      char lb[5]; snprintf(lb,5,"%d",abs(deg));
      spr.drawString(lb,(int16_t)(lx2+5),(int16_t)(ly2-4));
    }
  }

  // Roll arc (drawn in every tile that the top of ADI overlaps)
  int16_t arcR=(int16_t)(ADI_H*0.47f);
  spr.drawArc(ADI_CX, acy, arcR, arcR-4, 241, 299, CK_WHITE);
  const uint8_t mkArr[]={10,20,30,45,60};
  for(uint8_t i=0;i<5;i++) for(int8_t sg=-1;sg<=1;sg+=2){
    float a=(270.f+sg*mkArr[i])*D2R;
    spr.drawLine((int16_t)(ADI_CX+arcR*cosf(a)),    (int16_t)(acy+arcR*sinf(a)),
                 (int16_t)(ADI_CX+(arcR-8)*cosf(a)),(int16_t)(acy+(arcR-8)*sinf(a)),CK_WHITE);
  }

  // Roll pointer
  float rpa=(270.f-roll)*D2R;
  int16_t rpx=(int16_t)(ADI_CX+(arcR-12)*cosf(rpa));
  int16_t rpy=(int16_t)(acy+(arcR-12)*sinf(rpa));
  float cfx=cosf(rpa),cfy=sinf(rpa),csx=-sinf(rpa),csy=cosf(rpa);
  spr.fillTriangle(rpx+(int16_t)(7*cfx), rpy+(int16_t)(7*cfy),
                   rpx+(int16_t)(5*csx), rpy+(int16_t)(5*csy),
                   rpx-(int16_t)(5*csx), rpy-(int16_t)(5*csy), CK_YELLOW);

  // Aircraft reference symbol (fixed)
  int16_t aw=(int16_t)(ADI_W*0.16f);
  spr.fillRect(ADI_CX-aw-4, acy-2, aw, 4, CK_YELLOW);
  spr.fillRect(ADI_CX-aw-4, acy+2, 7,  5, CK_YELLOW);
  spr.fillRect(ADI_CX+4,    acy-2, aw, 4, CK_YELLOW);
  spr.fillRect(ADI_CX+aw-3, acy+2, 7,  5, CK_YELLOW);
  spr.fillCircle(ADI_CX, acy, 4, CK_YELLOW);

  // ADI borders
  if(inTile(ADI_Y,1,tileY))
    spr.drawFastHLine(ADI_X,ty(ADI_Y,tileY),ADI_W,CK_GREY);
  if(inTile(ADI_Y+ADI_H-1,1,tileY))
    spr.drawFastHLine(ADI_X,ty(ADI_Y+ADI_H-1,tileY),ADI_W,CK_GREY);
  spr.drawFastVLine(ADI_X,    ady_top, ady_bot-ady_top, CK_GREY);
  spr.drawFastVLine(ADI_X+ADI_W-1, ady_top, ady_bot-ady_top, CK_GREY);
}

// ─────────────────────────────────────────────────────────
//  SPEED TAPE
// ─────────────────────────────────────────────────────────
void drSpdTape(float IAS, float TAS, float Mach, int16_t tileY) {
  if(!inTile(SPD_Y, SPD_H+24, tileY)) return;

  const float SC = 6.0f;
  int ias_i = (int)IAS;
  int16_t midY = ty(SPD_Y + SPD_H/2, tileY);   // sprite-local centre

  // Vmo red band
  int16_t vmoSY = ty((int)(SPD_Y + SPD_H/2 - (350.0f-IAS)*SC), tileY);
  int16_t tapeTop = ty(SPD_Y, tileY);
  if(vmoSY > tapeTop && vmoSY < TILE_H && tapeTop < TILE_H) {
    int16_t bandH = vmoSY - imax16(tapeTop,(int16_t)0);
    if(bandH>0) spr.fillRect(SPD_X, imax16(tapeTop,(int16_t)0), SPD_W, bandH, 0x8000U);
  }

  // Ticks
  spr.setTextSize(1);
  for(int v=ias_i-35; v<=ias_i+35; v+=5){
    if(v<0) continue;
    int16_t yp = ty((int)(SPD_Y+SPD_H/2-(v-IAS)*SC), tileY);
    if(yp<0||yp>=TILE_H) continue;
    if(v%10==0){
      spr.drawFastHLine(SPD_X+SPD_W-18,yp,14,CK_WHITE);
      char lb[5]; snprintf(lb,5,"%3d",v);
      spr.setTextColor(CK_WHITE); spr.drawString(lb,SPD_X+1,yp-4);
    } else {
      spr.drawFastHLine(SPD_X+SPD_W-10,yp,6,CK_GREY);
    }
  }

  // Tape edge line
  if(inTile(SPD_Y,SPD_H,tileY))
    spr.drawFastVLine(SPD_X+SPD_W-4,
                      imax16((int16_t)0,ty(SPD_Y,tileY)),
                      imin16((int16_t)SPD_H,(int16_t)TILE_H), CK_WHITE);

  // Speed bugs
  struct B{float v;uint16_t c;const char*l;};
  B bugs[]={{135,CK_GREEN,"REF"},{150,CK_GREEN,"V2"},{165,CK_CYAN,"V1"}};
  for(auto &b:bugs){
    int16_t yb=ty((int)(SPD_Y+SPD_H/2-(b.v-IAS)*SC),tileY);
    if(yb>=0&&yb<TILE_H){
      spr.drawFastHLine(SPD_X+SPD_W-4,yb,8,b.c);
      spr.setTextColor(b.c); spr.drawString(b.l,SPD_X+SPD_W+1,(int16_t)(yb-4));
    }
  }

  // IAS readout window
  if(midY>=12&&midY<TILE_H-12){
    spr.fillRect(SPD_X,midY-11,SPD_W,22,CK_BG);
    spr.drawRect(SPD_X,midY-11,SPD_W,22,CK_WHITE);
    spr.setTextColor(CK_CYAN);
    char s[5]; snprintf(s,5,"%3d",ias_i);
    spr.drawString(s, SPD_X+SPD_W-30, midY-6);
  }

  // TAS/Mach below tape
  if(inTile(SPD_Y+SPD_H,20,tileY)){
    spr.setTextColor(CK_GREEN);
    char tas[12]; snprintf(tas,12,"TAS%3.0f",TAS);
    spr.drawString(tas,SPD_X+1,ty(SPD_Y+SPD_H+3,tileY));
    if(Mach>0.35f){
      spr.setTextColor(CK_WHITE);
      char mc[10]; snprintf(mc,10,"M%.3f",Mach);
      spr.drawString(mc,SPD_X+1,ty(SPD_Y+SPD_H+15,tileY));
    }
  }
}

// ─────────────────────────────────────────────────────────
//  ALTITUDE TAPE
// ─────────────────────────────────────────────────────────
void drAltTape(float alt, float VSI, int16_t tileY) {
  if(!inTile(ALT_Y, ALT_H+20, tileY)) return;

  const float SC = 0.08f;
  int alt_i = (int)alt;
  int16_t midY = ty(ALT_Y + ALT_H/2, tileY);

  spr.setTextSize(1);
  for(int a=alt_i-2000; a<=alt_i+2000; a+=100){
    int16_t yp=ty((int)(ALT_Y+ALT_H/2-(a-alt)*SC),tileY);
    if(yp<0||yp>=TILE_H) continue;
    spr.drawFastHLine(ALT_X+2,yp,12,CK_WHITE);
    if(a%500==0){
      char lb[8]; snprintf(lb,8,"%d",abs(a));
      spr.setTextColor(CK_WHITE); spr.drawString(lb,ALT_X+16,yp-4);
    }
  }

  // Tape edge
  if(inTile(ALT_Y,ALT_H,tileY))
    spr.drawFastVLine(ALT_X+2,
                      imax16((int16_t)0,ty(ALT_Y,tileY)),
                      imin16((int16_t)ALT_H,(int16_t)TILE_H), CK_WHITE);

  // Altitude window
  if(midY>=12&&midY<TILE_H-12){
    spr.fillRect(ALT_X+2,midY-12,ALT_W-4,24,CK_BG);
    spr.drawRect(ALT_X+2,midY-12,ALT_W-4,24,CK_WHITE);
    spr.setTextColor(CK_CYAN);
    char a[8]; snprintf(a,8,"%5d",alt_i);
    spr.drawString(a,ALT_X+4,midY-6);
  }

  // QNH below
  if(inTile(ALT_Y+ALT_H,14,tileY)){
    spr.setTextColor(CK_CYAN);
    char ql[12]; snprintf(ql,12,"QNH%4.0f",(float)g_QNH);
    spr.drawString(ql,ALT_X+2,ty(ALT_Y+ALT_H+3,tileY));
  }
}

// ─────────────────────────────────────────────────────────
//  VSI BAR
// ─────────────────────────────────────────────────────────
void drVSI(float VSI, int16_t tileY) {
  if(!inTile(VSI_Y,VSI_H,tileY)) return;
  int16_t sprMid = ty(VSI_Y+VSI_H/2, tileY);
  float pct=constrain(VSI/4000.f,-1.f,1.f);
  int16_t bH=(int16_t)(fabsf(pct)*(VSI_H/2));
  uint16_t col=(VSI>=0)?CK_GREEN:CK_AMBER;
  if(sprMid>0&&sprMid<TILE_H){
    if(VSI>=0) spr.fillRect(VSI_X+2,sprMid-bH,VSI_W-4,bH,col);
    else       spr.fillRect(VSI_X+2,sprMid,    VSI_W-4,bH,col);
  }
  if(inTile(VSID_Y,VSID_H,tileY)){
    char vs[9]; snprintf(vs,9,"%+.0f",VSI);
    spr.setTextColor(CK_WHITE); spr.setTextSize(1);
    spr.drawString(vs,   VSID_X+2, ty(VSID_Y+4,tileY));
    spr.drawString("fpm",VSID_X+2, ty(VSID_Y+16,tileY));
  }
}

// ─────────────────────────────────────────────────────────
//  HSI — Compass Tape
// ─────────────────────────────────────────────────────────
void drHSI(float hdg, int16_t tileY) {
  if(!inTile(HSI_Y,HSI_H,tileY)) return;
  int16_t topY = ty(HSI_Y+2,tileY);
  const float PPD=2.1f;
  int hdg_i=(int)hdg;
  static const char*const cards[12]={"N","030","060","E","120","150","S","210","240","W","300","330"};
  spr.setTextSize(1);
  for(int d=hdg_i-60;d<=hdg_i+60;d++){
    int dw=((d%360)+360)%360;
    int16_t xp=(int16_t)(HSI_CX+(d-hdg)*PPD);
    if(xp<HSI_X||xp>HSI_X+HSI_W) continue;
    if(dw%30==0){
      if(topY>=0&&topY<TILE_H) spr.drawFastVLine(xp,topY,12,CK_WHITE);
      uint16_t col=(dw==0||dw==90||dw==180||dw==270)?CK_CYAN:CK_WHITE;
      spr.setTextColor(col);
      int16_t lly=topY+13;
      if(lly>=0&&lly<TILE_H) spr.drawCenterString(cards[dw/30],xp,lly);
    } else if(dw%10==0){
      if(topY>=0&&topY<TILE_H) spr.drawFastVLine(xp,topY,7,CK_GREY);
    }
  }
  // Lubber triangle
  if(topY>0&&topY<TILE_H-10)
    spr.fillTriangle(HSI_CX-5,topY,HSI_CX+5,topY,HSI_CX,topY+10,CK_YELLOW);

  // Heading box
  int16_t bboxY=ty(HSI_Y+28,tileY);
  if(bboxY>=0&&bboxY<TILE_H-16){
    spr.fillRect(HSI_CX-20,bboxY,40,17,CK_BG);
    spr.drawRect(HSI_CX-20,bboxY,40,17,CK_WHITE);
    spr.setTextColor(CK_CYAN);
    char hb[5]; snprintf(hb,5,"%03d",hdg_i%360);
    spr.drawCenterString(hb,HSI_CX,bboxY+4);
  }
}

// ─────────────────────────────────────────────────────────
//  OAT / QNH / INFO BAR
// ─────────────────────────────────────────────────────────
void drOAT(float oat, int16_t tileY) {
  if(!inTile(OAT_Y,OAT_H,tileY)) return;
  spr.setTextSize(1);
  spr.setTextColor(CK_CYAN);   spr.drawString("OAT", OAT_X+4, ty(OAT_Y+4,tileY));
  char b[14]; snprintf(b,14,"%.1f C",oat);
  spr.setTextColor(CK_WHITE);  spr.drawString(b, OAT_X+4, ty(OAT_Y+18,tileY));
  spr.setTextColor(qmc_calDone?CK_GREEN:CK_AMBER);
  spr.drawString(qmc_calDone?"MAG:OK":"MAG:NC", OAT_X+4, ty(OAT_Y+32,tileY));
}

void drQNH(float qnh, int16_t tileY) {
  if(!inTile(QNH_Y,QNH_H,tileY)) return;
  spr.setTextSize(1);
  spr.setTextColor(CK_CYAN);  spr.drawString("BARO",  QNH_X+4, ty(QNH_Y+4,tileY));
  char b[12]; snprintf(b,12,"%.2f",qnh);
  spr.setTextColor(CK_WHITE); spr.drawString(b,        QNH_X+4, ty(QNH_Y+18,tileY));
  spr.setTextColor(CK_GREY);  spr.drawString("hPa",   QNH_X+4, ty(QNH_Y+32,tileY));
}

void drInfoBar(const FlightData &fd, int16_t tileY) {
  if(!inTile(INFO_Y,INFO_H,tileY)) return;
  int16_t iy=ty(INFO_Y,tileY);
  spr.setTextSize(1);
  spr.setTextColor(CK_GREEN);
  spr.drawString("AbleTechPFDProject v4.0",2,iy+1);
  uint32_t s=fd.ts_ms/1000;
  char ts[18]; snprintf(ts,18,"UP %02lu:%02lu:%02lu",s/3600,(s%3600)/60,s%60);
  spr.setTextColor(CK_GREY);   spr.drawString(ts,250,iy+1);
  spr.setTextColor(fd.valid?CK_GREEN:CK_RED);
  spr.drawString(fd.valid?"OK":"ERR",440,iy+1);
}

// ─────────────────────────────────────────────────────────
//  WARNINGS
// ─────────────────────────────────────────────────────────
void drWarnings(const FlightData &fd, int16_t tileY) {
  if(!fd.valid && inTile(ADI_CY-15,30,tileY)){
    spr.fillRect(ADI_CX-55,ty(ADI_CY-12,tileY),110,24,CK_RED);
    spr.setTextColor(CK_WHITE); spr.setTextSize(1);
    spr.drawCenterString("DATA INVALID",ADI_CX,ty(ADI_CY-3,tileY));
  }
  if(fd.IAS_kts>350 && inTile(SPD_Y+4,14,tileY)){
    spr.fillRect(SPD_X,ty(SPD_Y+4,tileY),SPD_W,14,CK_RED);
    spr.setTextColor(CK_WHITE);
    spr.drawCenterString("OVERSPD",SPD_X+SPD_W/2,ty(SPD_Y+7,tileY));
  }
  if(fabsf(fd.roll_deg)>60 && inTile(ADI_Y+4,12,tileY)){
    spr.setTextColor(CK_RED);
    spr.drawCenterString("BANK ANGLE",ADI_CX,ty(ADI_Y+6,tileY));
  }
  if(fabsf(fd.pitch_deg)>25 && inTile(ADI_Y+ADI_H-14,12,tileY)){
    spr.setTextColor(CK_AMBER);
    spr.drawCenterString(fd.pitch_deg>0?"PITCH UP":"PITCH DN",
                         ADI_CX,ty(ADI_Y+ADI_H-12,tileY));
  }
}

// ═══════════════════════════════════════════════════════════
//  SPLASH HELPER  (direct tft draw — no sprite needed)
// ═══════════════════════════════════════════════════════════
/**
 * splashPrint — draws one line of text on the physical display
 * using LovyanGFX direct rendering. No sprite required, so
 * this works even before sprite allocation succeeds.
 */
void splashPrint(const char *msg, uint16_t col, uint8_t size, int16_t y) {
  tft.setTextColor(col);
  tft.setTextSize(size);
  tft.drawCenterString(msg, DW/2, y);
}

// ═══════════════════════════════════════════════════════════
//  TOUCHSCREEN
// ═══════════════════════════════════════════════════════════
/**
 * handleTouch — polls XPT2046 (200 ms debounce).
 * Touch zones (landscape 480×320):
 *   Upper-right (x>430, y<100) → QNH +1 hPa
 *   Lower-right (x>430, y>200) → QNH -1 hPa
 *   Upper-left  (x<50,  y<100) → Brightness +20
 *   Lower-left  (x<50,  y>200) → Brightness -20
 *   HSI centre  (y>262)        → Compass recalibrate
 */
void handleTouch() {
  static uint32_t lastT=0;
  if(millis()-lastT<200) return;
  lgfx::touch_point_t tp;
  if(tft.getTouch(&tp,1)==0) return;
  lastT=millis();
  Serial.printf("[TOUCH] x=%d y=%d\n",tp.x,tp.y);
  if      (tp.x>430&&tp.y<100) { g_QNH=constrain((float)g_QNH+1,900.f,1100.f); }
  else if (tp.x>430&&tp.y>200) { g_QNH=constrain((float)g_QNH-1,900.f,1100.f); }
  else if (tp.x<50 &&tp.y<100) { g_brightness=min((int)g_brightness+20,255); tft.setBrightness(g_brightness); }
  else if (tp.x<50 &&tp.y>200) { g_brightness=max((int)g_brightness-20,20);  tft.setBrightness(g_brightness); }
  else if (tp.y>HSI_Y&&tp.x>HSI_CX-40&&tp.x<HSI_CX+40&&qmcOK) {
    Serial.println(F("[TOUCH] Compass recal triggered"));
    qmcCalibrate();
  }
}

// ═══════════════════════════════════════════════════════════
//  COMMUNICATION
// ═══════════════════════════════════════════════════════════
void initComm() {
#if COMM_MODE == COMM_WIFI
  WiFi.begin(WIFI_SSID,WIFI_PASS);
  Serial.print(F("[COMM] WiFi "));
  for(uint8_t i=0;i<40&&WiFi.status()!=WL_CONNECTED;i++){delay(500);Serial.print('.');}
  if(WiFi.status()==WL_CONNECTED){
    Serial.printf("\n[COMM] IP %s\n",WiFi.localIP().toString().c_str());
    udp.begin(UDP_PORT);
  } else errP("C-001","WiFi failed — check SSID/pass, must be 2.4 GHz");
#else
  Serial.println(F("[COMM] Mode: USB Serial 921600"));
#endif
}

void txData(const FlightData &fd) {
  char pkt[210];
  snprintf(pkt,sizeof(pkt),
    "$PFD,%.1f,%.1f,%.3f,%.0f,%.0f,%.2f,%.2f,%.1f,%.1f,%.2f,%.2f,%lu\n",
    fd.IAS_kts,fd.TAS_kts,fd.Mach,fd.alt_ft,fd.VSI_fpm,
    fd.roll_deg,fd.pitch_deg,fd.hdg_deg,fd.OAT_C,
    fd.QNH_hPa,fd.pres_hPa,fd.ts_ms);
#if COMM_MODE == COMM_WIFI
  if(WiFi.status()==WL_CONNECTED){udp.beginPacket(UDP_HOST,UDP_PORT);udp.print(pkt);udp.endPacket();}
#else
  Serial.print(pkt);
#endif
}

// ═══════════════════════════════════════════════════════════
//  I2C HELPERS
// ═══════════════════════════════════════════════════════════
void i2cWr(uint8_t a, uint8_t r, uint8_t v) {
  Wire.beginTransmission(a); Wire.write(r); Wire.write(v);
  uint8_t e=Wire.endTransmission();
  if(e){ char c[8],m[60];
         snprintf(c,8,"S-I%02X",a);
         snprintf(m,60,"I2C wr 0x%02X r=0x%02X e=%d",a,r,e);
         errP(c,m); }
}
uint8_t i2cRd(uint8_t a, uint8_t r) {
  Wire.beginTransmission(a); Wire.write(r); Wire.endTransmission(false);
  Wire.requestFrom(a,(uint8_t)1);
  if(Wire.available()) return Wire.read();
  errP("S-099","I2C rd 0 bytes"); return 0;
}
void i2cRdN(uint8_t a, uint8_t r, uint8_t *b, uint8_t n) {
  Wire.beginTransmission(a); Wire.write(r); Wire.endTransmission(false);
  Wire.requestFrom(a,n);
  uint8_t i=0; while(Wire.available()&&i<n) b[i++]=Wire.read();
  if(i<n) errP("S-098","I2C burst read incomplete");
}
void errP(const char *code, const char *msg) {
  Serial.printf("[ERR][%s] %s\n",code,msg);
}
