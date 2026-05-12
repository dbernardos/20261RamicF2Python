# CLIENTE MQTT: DAVI

import paho.mqtt.client as mqtt
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)

class MqttClient:
    def __init__(self, broker=settings.MQTT_BROKER, port=settings.MQTT_PORT, 
                 username=settings.MQTT_USERNAME, password=settings.MQTT_PASSWORD):
        self.client = mqtt.Client()
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password

        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("✅ Conectado ao broker MQTT")
            # Inscreva-se nos tópicos aqui
            client.subscribe("dados/sensor")
            # client.subscribe("meuapp/sensor/temperatura")
            # client.subscribe("meuapp/dispositivos/#")
        else:
            logger.error(f"❌ Falha na conexão MQTT, código: {rc}")

    def on_message(self, client, userdata, msg):
        logger.info(f"📩 Mensagem recebida em {msg.topic}: {msg.payload.decode()}")
        try:
            # Aqui você pode chamar funções do Django, salvar no banco, etc.
            self.handle_message(msg.topic, msg.payload.decode())
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")

    def handle_message(self, topic, payload):
        """
        Função personalizada para lidar com mensagens recebidas.
        Exemplo: Salvar no banco, disparar sinais, atualizar modelos, etc.
        """
        from .models import VibrationCollection  # Importe aqui para evitar circular import no início

        if topic == "dados/sensor":
            data = json.loads(payload)
            VibrationCollection.objects.create(
                motor_id=data.get('motor_id', 'MOTOR_01'),
                vibration_data=data.get('vibration_data'), # ISSO PRECISA AJUSTAR (como esses dados sao coletados um a um, talvez criar uma lista aqui)
                status='pending'
            )
            logger.info("✅ Dados de vibração salvos no banco.")

    def on_disconnect(self, client, userdata, rc):
        logger.warning("⚠️ Desconectado do broker MQTT")

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()  # Roda em thread separada
        except Exception as e:
            logger.error(f"Erro ao conectar no broker: {e}")

    def publish(self, topic, payload):
        try:
            result = self.client.publish(topic, payload)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"📤 Publicado em {topic}: {payload}")
            else:
                logger.error(f"❌ Falha ao publicar em {topic}")
        except Exception as e:
            logger.error(f"Erro ao publicar: {e}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()