# management/commands/run_mqtt_client.py
from django.core.management.base import BaseCommand
from aplicacao.mqtt_client import MqttClient  # sua classe
import time

class Command(BaseCommand):
    help = 'Inicia o cliente MQTT em background'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Iniciando cliente MQTT...")
        mqtt = MqttClient()
        mqtt.connect()
        
        try:
            while True:
                time.sleep(1)  # Mantém o processo vivo
        except KeyboardInterrupt:
            mqtt.disconnect()
            self.stdout.write("✅ Cliente MQTT encerrado")