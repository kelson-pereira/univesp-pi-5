# voltguard/signals.py

import random
from datetime import timedelta
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.utils import timezone

from .models import Device, SensorType, Sensor


@receiver(post_migrate)
def seed_initial_data(sender, **kwargs):

    # Executa apenas para este app
    if sender.name != "voltguard":
        return

    print("🔹 Verificando seed inicial do VoltGuard...")

    # Criar ou recuperar SensorType
    sensor_type, _ = SensorType.objects.get_or_create(
        name="voltA",
        defaults={
            "description": "Tensão elétrica fase A",
            "unit": "Volts",
            "min_value": 215.0,
            "max_value": 225.0,
            "order": 1
        }
    )

    # Criar ou recuperar Device
    device, _ = Device.objects.get_or_create(
        mac_address="AA:BB:CC:DD:EE:FF",
        defaults={"name": "Condomínio A (Simulação)"}
    )

    # Se já houver sensores para esse device, não recriar
    if Sensor.objects.filter(device=device, sensor_type=sensor_type).exists():
        print("Dados já existem. Seed ignorado.")
    else:
        print("Seed concluído com sucesso.")
