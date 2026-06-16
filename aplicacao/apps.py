from django.apps import AppConfig
from django.conf import settings
import os

class AplicacaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aplicacao'

    def ready(self):
        # RUN_MAIN=true só existe no processo filho (o real).
        # O processo pai (reloader) não tem essa variável — ignoramos ele.
        if os.environ.get('RUN_MAIN') == 'true':
            from .mqtt_client import MqttClient
            import threading

            client = MqttClient()
            thread = threading.Thread(target=client.connect, daemon=True)
            thread.start()