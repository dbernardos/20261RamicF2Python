from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class VibrationCollection(models.Model):
    motor_id = models.CharField(max_length=50, default="MOTOR_01")
    collected_at = models.DateTimeField(default=timezone.now)
    vibration_data = models.JSONField(help_text="Lista JSON com 10000 valores de vibração (float)")
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processed', 'Processado (FFT gerado)'),
        ('error', 'Erro no processamento'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        ordering = ['-collected_at']

    def __str__(self):
        return f"Coleta #{self.pk} | {self.motor_id} | {self.collected_at.strftime('%d/%m/%Y %H:%M')}"