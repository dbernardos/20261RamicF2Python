import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.cache import cache  # Usando cache do Django (Redis/Memcached/Local)
import json
import logging
import time
from datetime import timedelta

logger = logging.getLogger(__name__)

# Configurações do buffer de montagem
BLOCK_TIMEOUT = 30  # segundos para aguardar todos os blocos
CACHE_PREFIX = "vibration_buffer:"

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
            client.subscribe("dados/sensor")
        else:
            logger.error(f"❌ Falha na conexão MQTT, código: {rc}")

    def on_message(self, client, userdata, msg):
        logger.info(f"📩 Mensagem recebida em {msg.topic}: {msg.payload.decode()[:100]}...")
        try:
            self.handle_message(msg.topic, msg.payload.decode())
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)

    def _get_cache_key(self, motor_id: str, collection_id: str) -> str:
        """Gera chave única para o buffer de montagem"""
        return f"{CACHE_PREFIX}{motor_id}:{collection_id}"

    def _assemble_and_save(self, motor_id: str, collection_id: str, buffer: dict):
        """Monta os blocos ordenados e salva no banco de dados"""
        from .models import VibrationCollection
        
        # Ordena blocos pelo índice
        sorted_blocks = sorted(buffer['blocks'].items(), key=lambda x: int(x[0]))
        vibration_data = []
        
        for _, block_data in sorted_blocks:
            vibration_data.extend(block_data)
        
        # Salva no banco - APENAS UM INSERT!
        VibrationCollection.objects.create(
            motor_id=motor_id,
            vibration_data=vibration_data,
            status='pending'
        )
        
        logger.info(f"✅ Coleta #{collection_id} salva: {len(vibration_data)} amostras")
        
        # Limpa buffer do cache
        cache_key = self._get_cache_key(motor_id, collection_id)
        cache.delete(cache_key)

    def _check_and_assemble(self, motor_id: str, collection_id: str, buffer: dict):
        """Verifica se todos os blocos foram recebidos e monta os dados"""
        expected_total = buffer['total']
        received_count = len(buffer['blocks'])
        
        logger.info(f"📦 Coleta {collection_id}: {received_count}/{expected_total} blocos recebidos")
        
        if received_count == expected_total:
            self._assemble_and_save(motor_id, collection_id, buffer)
            return True
        return False

    def _schedule_timeout_check(self, motor_id: str, collection_id: str, buffer: dict):
        """Agenda verificação de timeout para blocos perdidos"""
        from django.core.cache import cache
        
        def timeout_handler():
            cache_key = self._get_cache_key(motor_id, collection_id)
            current_buffer = cache.get(cache_key)
            
            if current_buffer:  # Ainda não foi montado
                logger.warning(f"⏰ Timeout para coleta {collection_id}. Salvando com {len(current_buffer['blocks'])} blocos...")
                self._assemble_and_save(motor_id, collection_id, current_buffer)
        
        # Agenda execução assíncrona (usando threading para simplicidade)
        import threading
        timer = threading.Timer(BLOCK_TIMEOUT, timeout_handler)
        timer.daemon = True
        timer.start()

    def handle_message(self, topic, payload):
        """Processa mensagens MQTT e agrupa blocos antes de salvar"""
        from .models import VibrationCollection
        
        if topic == "dados/sensor":
            data = json.loads(payload)
            
            motor_id = data.get('motor_id', 'MOTOR_01')
            bloco_idx = data.get('bloco')
            total_blocos = data.get('total')
            vibration_chunk = data.get('vibration_data', [])
            
            # Validações básicas
            if bloco_idx is None or total_blocos is None:
                logger.warning("❌ Mensagem sem metadados de bloco, ignorando")
                return
            
            # Gera ID único para esta coleta (motor_id + timestamp aproximado)
            # O Arduino poderia enviar um "collection_id", mas vamos derivar do tempo
            collection_id = f"{motor_id}_{int(time.time() // (BLOCK_TIMEOUT * 2))}"
            cache_key = self._get_cache_key(motor_id, collection_id)
            
            # Tenta obter buffer existente ou cria novo
            buffer = cache.get(cache_key)
            is_new_collection = buffer is None
            
            if is_new_collection:
                buffer = {
                    'motor_id': motor_id,
                    'total': total_blocos,
                    'blocks': {},
                    'first_received': time.time()
                }
                logger.info(f"🆕 Nova coleta iniciada: {collection_id} (esperando {total_blocos} blocos)")
            
            # Armazena o bloco recebido (evita duplicatas)
            if str(bloco_idx) not in buffer['blocks']:
                buffer['blocks'][str(bloco_idx)] = vibration_chunk
                logger.debug(f"📥 Bloco {bloco_idx}/{total_blocos} armazenado")
            
            # Atualiza cache com timeout estendido a cada novo bloco
            cache.set(cache_key, buffer, timeout=BLOCK_TIMEOUT)
            
            # Se for a primeira mensagem, agenda timeout handler
            if is_new_collection:
                self._schedule_timeout_check(motor_id, collection_id, buffer)
            
            # Verifica se completou a coleta
            if self._check_and_assemble(motor_id, collection_id, buffer):
                logger.info(f"🎯 Coleta {collection_id} COMPLETA e salva!")

    def on_disconnect(self, client, userdata, rc):
        logger.warning("⚠️ Desconectado do broker MQTT")

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Erro ao conectar no broker: {e}", exc_info=True)

    def publish(self, topic, payload):
        try:
            result = self.client.publish(topic, payload)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"📤 Publicado em {topic}: {payload[:50]}...")
            else:
                logger.error(f"❌ Falha ao publicar em {topic}")
        except Exception as e:
            logger.error(f"Erro ao publicar: {e}", exc_info=True)

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()