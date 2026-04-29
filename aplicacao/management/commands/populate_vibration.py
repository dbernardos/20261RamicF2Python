# populate_vibration_data.py

# management/commands/populate_vibration.py
from django.core.management.base import BaseCommand
from populate_vibration_data import populate_sample_collections  # importe a função acima

class Command(BaseCommand):
    help = 'Popula o banco com coletas simuladas de vibração'

    def handle(self, *args, **options):
        populate_sample_collections(5)
        self.stdout.write(self.style.SUCCESS('Dados simulados inseridos com sucesso!'))