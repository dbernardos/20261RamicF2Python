# execute no Django Shell: python manage.py shell < populate_vibration_data.py
# ou copie o conteúdo para dentro do shell interativo

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projeto1.settings')
django.setup()

import numpy as np
import json
from datetime import datetime, timedelta
from django.utils import timezone
from aplicacao.models import VibrationCollection

def generate_realistic_vibration(n_points=10000, fs=10000, base_freq=60, 
                                  noise_level=0.15, fault=False):
    """
    Gera um sinal de vibração simulando um motor trifásico.
    
    Parâmetros:
    - n_points: número de amostras (padrão: 10000)
    - fs: frequência de amostragem em Hz (padrão: 10000 Hz)
    - base_freq: frequência fundamental do motor em Hz (ex: 60 Hz = 3600 RPM)
    - noise_level: nível de ruído gaussiano adicionado
    - fault: se True, adiciona componentes de falha (ex: desbalanceamento)
    
    Retorna:
    - lista de floats com os valores de vibração
    """
    t = np.arange(n_points) / fs  # vetor tempo
    
    # Componente fundamental (rotação do eixo)
    signal = 1.0 * np.sin(2 * np.pi * base_freq * t)
    
    # Harmônicos típicos de motores (2x e 3x a frequência fundamental)
    signal += 0.3 * np.sin(2 * np.pi * 2 * base_freq * t)
    signal += 0.15 * np.sin(2 * np.pi * 3 * base_freq * t)
    
    # Ruído branco gaussiano (simula interferências e medição)
    signal += noise_level * np.random.randn(n_points)
    
    # Se houver "falha", adiciona componente de baixa frequência (ex: desalinhamento)
    if fault:
        signal += 0.5 * np.sin(2 * np.pi * 0.5 * base_freq * t)  # sub-harmônico
        signal += 0.25 * np.sin(2 * np.pi * 120 * t)  # frequência de rolamento (exemplo)
    
    # Normaliza para faixa típica de sensores (ex: -5V a +5V ou mm/s)
    signal = signal / np.max(np.abs(signal)) * 4.5
    
    return signal.tolist()


def populate_sample_collections(n_collections=5):
    """Cria N coletas simuladas no banco de dados."""
    
    motors = ["MOTOR_01", "MOTOR_02", "MOTOR_03"]
    base_time = timezone.now() - timedelta(hours=n_collections*2)
    
    print(f"🔄 Gerando {n_collections} coletas simuladas...")
    
    for i in range(n_collections):
        motor_id = motors[i % len(motors)]
        collected_at = base_time + timedelta(hours=i*2)
        
        # Alterna entre condições normais e com "falha simulada"
        has_fault = (i % 2 == 0)
        
        vibration_data = generate_realistic_vibration(
            n_points=10000,
            fs=10000,
            base_freq=60,  # 60 Hz = 3600 RPM (típico para motores 4 polos/60Hz)
            noise_level=0.12 if not has_fault else 0.25,
            fault=has_fault
        )
        
        collection = VibrationCollection.objects.create(
            motor_id=motor_id,
            collected_at=collected_at,
            vibration_data=vibration_data,
            status='processed' if i < 3 else 'pending'  # simula diferentes status
        )
        
        condition = "⚠️ COM FALHA SIMULADA" if has_fault else "✅ NORMAL"
        print(f"  [{i+1}/{n_collections}] {collection} | {condition}")
    
    print("✅ População concluída! Dados prontos para teste de FFT e visualização.")


# Executa a população
if __name__ == "__main__":
    populate_sample_collections(5)