#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>

// ================= CONFIGURAÇÕES DE REDE =================
// Configurações de rede
const char* ssid = "Ramic_Local_IoT_Router";
const char* password = "ramic123";
//const char* ssid = "trojan";
//const char* password = "myREDE01";

// ================= CONFIGURAÇÕES MQTT =================
//const char* mqtt_server = "10.71.131.144";
const char* mqtt_server = "10.42.0.1";
const int mqtt_port = 1883;
const char* mqtt_user = "ramic";
const char* mqtt_password = "123456";
const char* mqtt_subscribe_topic = "comando/sensor"; // Tópico para receber comandos
const char* mqtt_publish_topic = "dados/sensor";    // Tópico para publicar dados
const char* mqtt_publish_status = "status/sensor";   // publica status

WiFiClient espClient;
PubSubClient client(espClient);

// ================= CONFIGURAÇÕES LEONARDO =================
#define FS 5000
#define TEMPO 2
#define N (FS * TEMPO)
#define INTERVALO 10000

int buttonPin = D6;
int lastButtonState = LOW;
String message = "";
bool isCollecting = false; // Variável de controle de coleta

volatile uint16_t buffer[N];
volatile int indice = 0;
volatile bool aquisicaoCompleta = false;

unsigned long ultimoCiclo = 0;

// ================= FUNÇÃO ONTIMER =================
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

// ================= FUNÇÃO DE AQUISIÇÃO =================
void iniciarAquisicao() {
  indice = 0;
  aquisicaoCompleta = false;

  timer1_attachInterrupt(onTimer);
  timer1_enable(TIM_DIV16, TIM_EDGE, TIM_LOOP);
  // 80 MHz / 16 = 5 MHz
  // 5 MHz → 1 tick = 0.2 µs
  // 200 µs / 0.2 µs = 1000 ticks
  timer1_write(1000);
}

// ================= FUNÇÃO PARA IMPRIMIR O RESULTADO =================
void imprimirDados() {
  char mensagem[100];

  Serial.println("amostra,valor");
  for (int i = 0; i < N; i++) {
    Serial.print(i);
    Serial.print(",");
    Serial.println(buffer[i]);
    //mensagem += (char)buffer[i];
    sprintf(mensagem, "%d", buffer[i]);
    client.publish(mqtt_publish_topic, mensagem);
  }
}


void enviarBlocos(){
  char mensagem[100];
  int idx = 0;

  for (int i = 0; i < N; i++) {
    idx += sprintf(mensagem + idx, "%d", buffer[i]);
    
    if(idx > 20){
      client.publish(mqtt_publish_topic, mensagem);
      idx = 0;
    }
  }
}

// ================= FUNÇÃO SETUP =================
void setup() {
  pinMode(buttonPin, INPUT_PULLUP);
  Serial.begin(115200);
  Serial.println("Sistema pronto");

  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado ao Wi-Fi");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Congigurando servidor MQTT");
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback); // Define a função de callback para mensagens recebidas
  client.setBufferSize(2048); 
}

// ================= FUNÇÃO DE LOOP =================
void loop() {

  if (!client.connected()) {
    reconnect();
  }
  client.loop(); // escuta mensagens
  int buttonState = digitalRead(buttonPin);

  if (buttonState != lastButtonState || isCollecting) {
    delay(50); // debounce simples
    if (buttonState == LOW || isCollecting) { // ativo baixo (pressionado)
      Serial.println("Botão pressionado -> publicando ligado");
      client.publish(mqtt_publish_status, "botao ligado");
      // COMECAR NOVA COLETA 
      if (millis() - ultimoCiclo >= INTERVALO) {
        Serial.println("Iniciando aquisicao");
        iniciarAquisicao();
        while (!aquisicaoCompleta) {
          yield();
        }
        
        imprimirDados();

        Serial.print("Enviando dados: ");
        Serial.println(mqtt_publish_topic);
        //client.publish(mqtt_publish_topic, (uint8_t*)buffer, sizeof(buffer));
        //client.publish(mqtt_publish_topic, (byte*)buffer, sizeof(buffer));
        //enviarBlocos();
        client.publish(mqtt_publish_topic, "mensagem<<<<<<<");

        Serial.println("Aquisicao finalizada");
        ultimoCiclo = millis();
      }
      isCollecting = false;
    } else {
      Serial.println("Botão solto -> publicando desligado");
      client.publish(mqtt_publish_status, "botao desligado");
    }
    lastButtonState = buttonState;
  }
}

// ================= FUNÇÃO DE CONEXÃO =================
void reconnect() {
  while (!client.connected()) {
    Serial.print("\nTentando conectar ao MQTT...");
    if (client.connect("ESP8266Client", mqtt_user, mqtt_password)) {
    //Serial.print(String(ESP.getChipId()));
    //if (client.connect("ESP8266-8285683", mqtt_user, mqtt_password)){
      Serial.println("\nConectado ao broker MQTT");
      client.subscribe(mqtt_subscribe_topic);
      client.publish(mqtt_publish_status, "botao inicializado");
    } else {
      Serial.print(" Falhou, rc=");
      Serial.print(client.state());
      Serial.println(" - Tentando novamente em 3s");
      delay(3000);
    }
  }
}


void callback(char* topic, byte* payload, unsigned int length) {
  // Converte o payload para uma string
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  // Verifica se a mensagem recebida é "coletar" no tópico de comando
  if (String(topic) == mqtt_subscribe_topic && message == "coletar") {
    Serial.println("Comando 'coletar' recebido. Iniciando coleta...");
    isCollecting = true;
    // sampleIndex = 0; // Reinicia o índice para uma nova coleta
    // previousMicros = micros(); // Sincroniza o tempo inicial
  }
}