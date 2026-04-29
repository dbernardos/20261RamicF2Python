#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>
//#include <String.h>

#define FS 5000
#define TEMPO 2
#define N (FS * TEMPO)

#define INTERVALO 10000

// DAVI INICIO

int buttonPin = D6;
int lastButtonState = LOW;

// Configurações de rede
const char* ssid = "Ramic_Local_IoT_Router";
//const char* ssid = "trojan";
//const char* password = "myREDE01";
const char* password = "ramic123";

// Configurações MQTT
//const char* mqtt_server = "10.71.131.144";
const char* mqtt_server = "10.42.0.1";
const int mqtt_port = 1883;
const char* mqtt_user = "ramic";
const char* mqtt_password = "123456";

// Tópicos que o ESP32 vai escutar
//const char* topic1 = "motor/a110";
const char* topic1 = "dados/mpu";
const char* topic2 = "configuracao/#"; // wildcard
const char* topic_pub_motor = "motor/status";   // publica status

WiFiClient espClient;
PubSubClient client(espClient);

// DAVI FIM

volatile uint16_t buffer[N];
volatile int indice = 0;
volatile bool aquisicaoCompleta = false;

unsigned long ultimoCiclo = 0;

//String clientId = "ESP8266-" + String(ESP.getChipId());
//clientId += String(ESP.getChipId());

//void IRAM_ATTR onTimer() {
void onTimer() {
  if (indice < N) {
    buffer[indice] = analogRead(A0);
    indice++;
  } 
  else {
    timer1_disable();
    aquisicaoCompleta = true;
  }
}

void iniciarAquisicao() {
  indice = 0;
  aquisicaoCompleta = false;

  Serial.print("Davi inicio...");
  timer1_attachInterrupt(onTimer);
  Serial.print("Davi meio...");
  timer1_enable(TIM_DIV16, TIM_EDGE, TIM_LOOP);
  Serial.print("Davi fim...");

  // 80 MHz / 16 = 5 MHz
  // 5 MHz → 1 tick = 0.2 µs
  // 200 µs / 0.2 µs = 1000 ticks

  timer1_write(1000);
}

void enviarCSV() {
  Serial.println("amostra,valor");

  for (int i = 0; i < N; i++) {
    Serial.print(i);
    Serial.print(",");
    Serial.println(buffer[i]);
  }

  Serial.println("FIM");
}

void setup() {
  pinMode (buttonPin, INPUT_PULLUP);
  Serial.begin(115200);
  delay(2000);

  Serial.println("Sistema pronto");

  // INICIO DAVI
  // Conecta ao Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n Conectado ao Wi-Fi");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  // Configura o cliente MQTT
  client.setServer(mqtt_server, mqtt_port);
 // client.setCallback(callback);
  // FIM DAVI

}

void loop() {

  if (!client.connected()) {
    reconnect();
  }
  client.loop(); // escuta mensagens
  int buttonState = digitalRead(buttonPin);

  if (buttonState != lastButtonState) {
    delay(50); // debounce simples
    if (buttonState == LOW) { // ativo baixo (pressionado)
      Serial.println("Botão pressionado → publicando ligado");
      client.publish(topic_pub_motor, "botao ligado");
      // COMECAR NOVA COLETA 
      if (millis() - ultimoCiclo >= INTERVALO) {
        Serial.println("Iniciando aquisicao");
        iniciarAquisicao();
        while (!aquisicaoCompleta) {
          yield();
        }
        Serial.println("Enviando dados CSV");
        enviarCSV();

        Serial.println("amostra,valor");

        for (int i = 0; i < N; i++) {
          Serial.print(i);
          Serial.print(",");
          Serial.println(buffer[i]);
          Serial.println(buffer[i]);
          client.publish(topic_pub_motor, ""+buffer[i]);
        }

        Serial.println("FIM");

        Serial.println("Aquisicao finalizada");
        ultimoCiclo = millis();
      }
    } else {
      Serial.println("Botão solto → publicando desligado");
      client.publish(topic_pub_motor, "botao desligado");
    }
    lastButtonState = buttonState;
  }
}


void reconnect() {
  while (!client.connected()) {
    Serial.print("Tentando conectar ao MQTT...");
    // Nome do cliente deve ser único na rede MQTT
    if (client.connect("ESP8266Client", mqtt_user, mqtt_password)) {
    //Serial.print(String(ESP.getChipId()));
    //if (client.connect("ESP8266-8285683", mqtt_user, mqtt_password)){
      Serial.println(" Conectado ao broker MQTT");
      client.subscribe(topic1);
      client.subscribe(topic2);
      client.publish(topic_pub_motor, "botao inicializado");
    } else {
      Serial.print(" Falhou, rc=");
      Serial.print(client.state());
      Serial.println(" - Tentando novamente em 3s");
      delay(3000);
    }
  }
}
