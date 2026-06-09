#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ================= CONFIGURAÇÕES DE REDE =================
const char* ssid     = "Ramic_Local_IoT_Router";
const char* password = "ramic123";

// ================= CONFIGURAÇÕES MQTT =================
const char* mqtt_server          = "10.42.0.1";
const int   mqtt_port            = 1883;
const char* mqtt_user            = "ramic";
const char* mqtt_password        = "123456";
const char* mqtt_subscribe_topic = "comando/sensor";
const char* mqtt_publish_topic   = "dados/sensor";
const char* mqtt_publish_status  = "status/sensor";
const char* motor_id             = "MOTOR_09";
//const char* collection_id;

WiFiClient   espClient;
PubSubClient client(espClient);

// ================= CONFIGURAÇÕES DE AQUISIÇÃO =================
#define FS         2000
#define TEMPO      2
#define N          (FS * TEMPO)   // 4.000 amostras = 8 KB de RAM
#define INTERVALO  2000           // ms entre ciclos (aumentado para dar tempo ao stack)
#define BLOCO_SIZE 50             // amostras por mensagem MQTT

// FIX-RAM: array declarado como PROGMEM não é opção para escrita;
// mas colocá-lo como global estático garante que fique na heap e não no stack.
// 10.000 x 2 bytes = 20 KB — cabe, mas é a maior alocação do sistema.
static uint16_t amostras[N];

volatile int  indice          = 0;
volatile bool aquisicaoCompleta = false;

int  buttonPin      = D6;
int  lastButtonState = LOW;
bool isCollecting   = false;

unsigned long ultimoCiclo = 0;

// ================= TIMER ISR =================
// IRAM_ATTR garante que a função esteja na RAM de instruções (IRAM),
// evitando o Exception(0) que ocorria porque o handler estava na flash
// e o cache de instruções não estava disponível durante a ISR.
void IRAM_ATTR onTimer() {
  if (indice < N) {
    amostras[indice++] = analogRead(A0);
  } else {
    timer1_disable();
    // FIX-TIMER: detach após disable para garantir que não dispare novamente
    // na próxima iniciarAquisicao(). Sem isso, a segunda coleta crashava.
    timer1_detachInterrupt();
    aquisicaoCompleta = true;
  }
}

// ================= INICIAR AQUISIÇÃO =================
void iniciarAquisicao() {
  // FIX-TIMER: garantir timer completamente parado antes de reconfigurar
  timer1_disable();
  timer1_detachInterrupt();
  delay(5); // pequena pausa para o hardware estabilizar

  indice           = 0;
  aquisicaoCompleta = false;

  timer1_attachInterrupt(onTimer);
  timer1_enable(TIM_DIV16, TIM_EDGE, TIM_LOOP);
  // 80 MHz / 16 = 5 MHz → 1 tick = 0.2 µs
  // 5000 Hz → período = 200 µs → 1000 ticks
  timer1_write(2500);
}

// ================= PUBLICAÇÃO EM BLOCOS =================
void publicarEmBlocos() {
  int totalBlocos = (N + BLOCO_SIZE - 1) / BLOCO_SIZE;

  //static uint32_t collection_counter=0;
  //uint32_t collection_id = collection_counter++;


  for (int b = 0; b < totalBlocos; b++) {

    // FIX-JSON: StaticJsonDocument no stack dentro do loop;
    // tamanho calculado: 50 ints * ~5 chars + overhead JSON ~ 400 bytes
    StaticJsonDocument<768> doc;
    //doc["collection_id"] = collection_id;
    doc["motor_id"] = motor_id;
    doc["bloco"]    = b;
    doc["total"]    = totalBlocos;

    JsonArray vib = doc.createNestedArray("vibration_data");

    int inicio = b * BLOCO_SIZE;
    int fim    = min(inicio + BLOCO_SIZE, (int)N);
    for (int i = inicio; i < fim; i++) {
      vib.add((int)amostras[i]);
    }

    char jsonBuf[768];
    serializeJson(doc, jsonBuf, sizeof(jsonBuf));
    client.publish(mqtt_publish_topic, jsonBuf);

    // Pausa e yield para manter o stack Wi-Fi/TCP saudável
    delay(20);
    client.loop();
  }

  Serial.printf("Publicados %d blocos de %d amostras.\n", totalBlocos, BLOCO_SIZE);
  Serial.printf("Heap livre apos publicacao: %d bytes\n", ESP.getFreeHeap());
}

// ================= SETUP =================
void setup() {
  pinMode(buttonPin, INPUT_PULLUP);
  Serial.begin(115200);
  Serial.println("\nSistema iniciando...");
  Serial.printf("Heap livre no boot: %d bytes\n", ESP.getFreeHeap());

  // FIX-TIMER: garantir timer desligado no boot
  timer1_disable();
  timer1_detachInterrupt();

  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nConectado. IP: %s\n", WiFi.localIP().toString().c_str());

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  client.setBufferSize(2048);
}

// ================= LOOP =================
void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  int buttonState = digitalRead(buttonPin);

  if (buttonState != lastButtonState || isCollecting) {
    delay(50);
    if (buttonState == LOW || isCollecting) {
      client.publish(mqtt_publish_status, "botao ligado");

      if (millis() - ultimoCiclo >= INTERVALO) {
        Serial.println("Iniciando aquisicao...");
        Serial.printf("Heap livre antes da coleta: %d bytes\n", ESP.getFreeHeap());

        iniciarAquisicao();

        // Aguarda coleta com yield para não travar o watchdog
        while (!aquisicaoCompleta) {
          yield();
        }

        Serial.println("Coleta finalizada. Publicando...");
        publicarEmBlocos();

        ultimoCiclo = millis();
      }

      isCollecting = false;

    } else {
      client.publish(mqtt_publish_status, "botao desligado");
    }
    lastButtonState = buttonState;
  }
}

// ================= RECONEXÃO MQTT =================
void reconnect() {
  while (!client.connected()) {
    Serial.print("Conectando ao MQTT...");
    if (client.connect("ESP8266Client", mqtt_user, mqtt_password)) {
      Serial.println(" OK");
      client.subscribe(mqtt_subscribe_topic);
      client.publish(mqtt_publish_status, "inicializado");
    } else {
      Serial.printf(" Falhou (rc=%d). Tentando em 3s\n", client.state());
      delay(3000);
    }
  }
}

// ================= CALLBACK MQTT =================
void callback(char* topic, byte* payload, unsigned int length) {
  // FIX: message local — não acumula entre chamadas
  String message = "";
  message.reserve(length);
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == mqtt_subscribe_topic && message == "coletar") {
    Serial.println("Comando 'coletar' recebido.");
    isCollecting = true;
  }
}
