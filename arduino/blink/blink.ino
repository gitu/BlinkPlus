#include <XBee.h>
#include <Adafruit_NeoPixel.h>

#define RING_PIN           2

const uint8_t
  C_STATIC = 0,
  C_BLINK = 1;

const uint8_t
  C_GET_STATE = 1,
  C_RECEIVED_COMMAND = 2,
  C_RING = 0,
  C_BLINK = 1
  ;

XBee xbee = XBee();
XBeeResponse response = XBeeResponse();
ZBRxResponse rx = ZBRxResponse();
ModemStatusResponse msr = ModemStatusResponse();


uint8_t payload[] = { 0,0 };

XBeeAddress64 addr64 = XBeeAddress64(0x0013a200, 0x40b0a1ad);
ZBTxRequest zbTx = ZBTxRequest(addr64, payload, sizeof(payload));
ZBTxStatusResponse txStatus = ZBTxStatusResponse();


int8_t
  rot = 1,
  pos = 0,
  pos_i = 0;

uint8_t
  jump_speed = 0;

uint16_t
  fade[16],
  fade_count = 0,
  iColor[16][3];

boolean useGamma = true;



void drawLoop(int nr) {
  int i;
  for (i=0; i<nr; i++) {
    draw();
    delay(10);
  }
}

void setCode( uint16_t r, uint16_t g, uint16_t b, int x) {
  for (int i=0; i<16; i++) {
   if (i<x) { iColor[i][0] =   r; iColor[i][1] =   g; iColor[i][2] =   b; }
   else     { iColor[i][0] =   0; iColor[i][1] =   0; iColor[i][2] =   0; }
  }
}

void setColor( uint16_t r, uint16_t g, uint16_t b, boolean split) {
  if (split) {
    for (int i=0; i<16; i++) {
     if (i<6)       { iColor[i][0] =   r; iColor[i][1] =   g; iColor[i][2] =   b; }
     else if (i<8)  { iColor[i][0] =   0; iColor[i][1] =   0; iColor[i][2] =   0; }
     else if (i<14) { iColor[i][0] =   r; iColor[i][1] =   g; iColor[i][2] =   b; }
     else           { iColor[i][0] =   0; iColor[i][1] =   0; iColor[i][2] =   0; }
    }
  }
  else
  {
    for (int i=0; i<16; i++) {
      iColor[i][0] =   r; iColor[i][1] =   g; iColor[i][2] =   b;
    }
  }
}

void draw() {
  fade_count ++;
  if (jump_speed == 0 || rot == 0 ) {

  }
  else
  {
     pos = pos + rot;
     if (pos%jump_speed == 0) {
        pos_i = (pos_i + rot) % 16;
     }
  }

  for(int i=0; i<16; i++) {
    uint16_t r = iColor[i][0];
    uint16_t g = iColor[i][1];
    uint16_t b = iColor[i][2];
    if (fade[i]>0) {
      float fade_factor = 1;
      int32_t f = (fade_count % (fade[i]*2) );
      if (f>=fade[i]) {
        f=fade[i]-f;
      }
      fade_factor = ((float)f)/((float)fade[i]);

      r = (uint16_t)(fade_factor*(float)r);
      g = (uint16_t)(fade_factor*(float)g);
      b = (uint16_t)(fade_factor*(float)b);
      if (r>=256)
        r=255;
      if (g>=256)
        g=255;
      if (b>=256)
        b=255;

    }
    if (useGamma) {
      pixels.setPixelColor(((i + pos_i) & 15),
        pgm_read_byte(&gamma8[r]), // Gamma correct and set pixel
        pgm_read_byte(&gamma8[g]),
        pgm_read_byte(&gamma8[b])
        );
    } else {
      pixels.setPixelColor(((i + pos_i) & 15),r,g,b);
    }
  }
  pixels.show();
}

void resetFade() {
  uint8_t i;
  for (i=0; i<16; i++) {
    fade[i] = 0;
  }
}

void parseFade(uint8_t *data, uint8_t len) {
  int i;
  if (len != 32+1) {
     return;
  }
  for (i=0; i<16;i++) {
    fade[i] = 255U*((uint16_t)data[i*2+1]) + (uint16_t)data[i*2+2];
  }
}

void parseFullColor(uint8_t *data, uint8_t len){
  int i;
  if (len != 16*3+1) {
     return;
  }
  for (i=0;i<16;i++) {
    iColor[i][0] = data[i*3 + 1];
    iColor[i][1] = data[i*3 + 2];
    iColor[i][2] = data[i*3 + 3];
  }
}


void parseRX(uint8_t *data, uint8_t len) {
  switch (data[0]) {
    case C_FULL: parseFullColor(data, len); break;
    case C_COLOR: setColor(data[1],data[2],data[3], false); break;
    case C_POS: pos_i = data[1] % 16; break;
    case C_JUMP: jump_speed = data[1]; break;
    case C_LEVEL: setCode(data[2],data[3],data[4],data[1]);  break;
    case C_LEVEL_RED: setCode(255,0,0,data[1]); break;
    case C_LEVEL_GREEN: setCode(0,255,0,data[1]);  break;
    case C_LEVEL_BLUE: setCode(0,0,255,data[1]);   break;
    case C_RED: setColor(255,0,0,false);  break;
    case C_GREEN: setColor(0,255,0,false); break;
    case C_BLUE: setColor(0,0,255,false); break;
    case C_ROT_RIGHT: rot = 1; break;
    case C_ROT_LEFT: rot = -1; break;
    case C_ROT_OFF: rot = 0;  break;
    case C_FADE_OFF: resetFade(); break;
    case C_SET_FADE: parseFade(data, len); break;
    case C_BRIGHTNESS: pixels.setBrightness(data[1]); break;
    case C_USE_GAMMA: useGamma = true; break;
    case C_GAMMA_OFF: useGamma = false; break;
    default: rot = -1; setCode(255,0,0,5); jump_speed=2; break;
  }
}

void confirm(uint8_t command) {
  payload[0]=C_RECEIVED_COMMAND;
  payload[1]=command;
  xbee.send(zbTx);
}

void requestStatus() {
  payload[0]=C_GET_STATE;
  payload[1]=C_BLINK;
  xbee.send(zbTx);
}

void readXBee() {
    xbee.readPacket();
    if (xbee.getResponse().isAvailable()) {
      if (xbee.getResponse().getApiId() == ZB_RX_RESPONSE) {
        xbee.getResponse().getZBRxResponse(rx);
        if (rx.getOption() == ZB_PACKET_ACKNOWLEDGED) {
          parseRX(rx.getData(), rx.getDataLength());
          confirm(rx.getData()[0]);
        } else {
          setCode(255,0,0,5);
          rot=0;
        }
      } else if (xbee.getResponse().getApiId() == MODEM_STATUS_RESPONSE) {
        xbee.getResponse().getModemStatusResponse(msr);
        if (msr.getStatus() == ASSOCIATED) {
          requestStatus();
        } else if (msr.getStatus() == DISASSOCIATED) {
          setCode(255,0,0,4);
          rot=0;
        } else {
          setCode(255,0,0,3);
          rot=0;
        }
      } else {
      }
    } else if (xbee.getResponse().isError()) {
      setCode(255,0,0,1);
      rot=0;
    }
}

void setup() {
  uint8_t i;
  pixels.begin();
  xbee.begin(9600);

}

void loop() {
  readXBee();
  drawLoop(2);
}



