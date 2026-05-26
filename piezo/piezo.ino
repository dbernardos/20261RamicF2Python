#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ================= CONFIGURAÇÕES DE REDE =================
const char* ssid = "Ramic_Local_IoT_Router";
const char* password = "ramic123";

// ================= CONFIGURAÇÕES MQTT =================
const char* mqtt_server = "10.42.0.1";
const int mqtt_port = 1883;
const char* mqtt_user = "ramic";
const char* mqtt_password = "123456";
const char* mqtt_subscribe_topic = "comando/sensor";
const char* mqtt_publish_topic = "dados/sensor";
const char* mqtt_publish_status = "status/sensor";

WiFiClient espClient;
PubSubClient client(espClient);

// ================= CONFIGURAÇÕES DE AQUISIÇÃO =================
#define FS        5000          // Frequência de amostragem (Hz)
#define TEMPO     2             // Duração da coleta (segundos)
#define N         (FS * TEMPO)  // Total de amostras = 10.000
#define INTERVALO 1000          // Intervalo mínimo entre ciclos (ms)

// FIX 1: Renomeado de "buffer" para "amostras" para evitar conflito de nome
// com o buffer local que existia em imprimirDados()
volatile uint16_t amostras[N];
volatile int indice = 0;
volatile bool aquisicaoCompleta = false;

int buttonPin = D6;
int lastButtonState = LOW;
bool isCollecting = false;

unsigned long ultimoCiclo = 0;

// FIX 2: motor_id movido para constante global, fora do documento JSON
// para não ser recriado a cada publicação
const char* motor_id = "MOTOR_09";

// ================= FUNÇÃO ONTIMER =================
void onTimer() {
  if (indice < N) {
    amostras[indice] = analogRead(A0);
    indice++;
  } else {
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
  // 80 MHz / 16 = 5 MHz → 1 tick = 0.2 µs
  // Para 5000 Hz: período = 200 µs → 200 / 0.2 = 1000 ticks
  timer1_write(1000);
}

// ================= PUBLICAÇÃO EM BLOCOS =================
// FIX 3: Substituída a função imprimirDados() que tentava serializar
// 10.000 amostras num único JSON (estouro de memória e payload MQTT).
// Agora os dados são enviados em blocos de BLOCO_SIZE amostras por mensagem.
// O broker local recebe todos os blocos e pode reassemblá-los pelo campo "bloco".

#define BLOCO_SIZE 100   // Amostras por mensagem MQTT (ajuste conforme necessário)
// Tamanho estimado por mensagem: ~700 bytes — bem abaixo do limite de 2048

void publicarEmBlocos() {
  int totalBlocos = (N + BLOCO_SIZE - 1) / BLOCO_SIZE;

  for (int b = 0; b < totalBlocos; b++) {
    // FIX 4: Documento JSON recriado a cada bloco para evitar fragmentação de memória
    StaticJsonDocument<1024> doc;
    doc["motor_id"] = motor_id;
    doc["bloco"]    = b;
    doc["total"]    = totalBlocos;

    JsonArray vib = doc.createNestedArray("vibration_data");

    int inicio = b * BLOCO_SIZE;
    int fim    = min(inicio + BLOCO_SIZE, N);

    for (int i = inicio; i < fim; i++) {
      // FIX 5: Adicionado como inteiro (não string) — mais compacto e correto
      vib.add((int)amostras[i]);
    }

    // FIX 6: Buffer local com nome distinto "jsonBuf" — sem conflito com "amostras"
    char jsonBuf[1024];
    serializeJson(doc, jsonBuf, sizeof(jsonBuf));
    client.publish(mqtt_publish_topic, jsonBuf);

    // Pequena pausa para não sobrecarregar o broker e o stack TCP do ESP8266
    delay(10);
    client.loop();
  }

  Serial.print("Publicados ");
  Serial.print((N + BLOCO_SIZE - 1) / BLOCO_SIZE);
  Serial.println(" blocos MQTT.");
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

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  client.setBufferSize(2048);
}

// ================= FUNÇÃO DE LOOP =================
void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  int buttonState = digitalRead(buttonPin);

  if (buttonState != lastButtonState || isCollecting) {
    delay(50); // debounce
    if (buttonState == LOW || isCollecting) {
      Serial.println("Botão pressionado / comando recebido");
      client.publish(mqtt_publish_status, "botao ligado");

      if (millis() - ultimoCiclo >= INTERVALO) {
        Serial.println("Iniciando aquisição...");
        iniciarAquisicao();

        while (!aquisicaoCompleta) {
          yield(); // Evita watchdog reset durante a coleta
        }

        Serial.println("Aquisição finalizada. Publicando blocos...");
        publicarEmBlocos();

        ultimoCiclo = millis();
      }

      isCollecting = false;
    } else {
      Serial.println("Botão solto");
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

// ================= CALLBACK MQTT =================
void callback(char* topic, byte* payload, unsigned int length) {
  // FIX 7: String "message" agora é local e limpa a cada chamada.
  // Antes era global e acumulava strings entre chamadas (bug crítico).
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == mqtt_subscribe_topic && message == "coletar") {
    Serial.println("Comando 'coletar' recebido. Iniciando coleta...");
    isCollecting = true;
  }
}
