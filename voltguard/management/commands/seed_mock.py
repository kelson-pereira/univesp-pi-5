import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from voltguard.models import Device, Sensor, SensorType

MOCK_MAC = "AA:BB:CC:DD:EE:FF"
MOCK_NAME = "Condomínio A (Simulação)"


class Command(BaseCommand):
    help = "Cria o dispositivo mock e insere leituras históricas dos últimos 10 minutos."

    def handle(self, *args, **options):
        sensor_type, _ = SensorType.objects.get_or_create(
            name="voltA",
            defaults={
                "description": "Tensão elétrica fase A",
                "unit": "Volts",
                "min_value": 215.0,
                "max_value": 225.0,
                "order": 1,
            },
        )

        device, created = Device.objects.get_or_create(
            mac_address=MOCK_MAC,
            defaults={"name": MOCK_NAME},
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Dispositivo mock criado: {MOCK_MAC}"))
        else:
            self.stdout.write(f"Dispositivo mock já existe: {MOCK_MAC}")

        # Remove leituras antigas (> 20 min) antes de recriar
        cutoff = timezone.now() - timedelta(minutes=20)
        deleted, _ = Sensor.objects.filter(device=device, created_at__lt=cutoff).delete()
        if deleted:
            self.stdout.write(f"{deleted} leitura(s) antiga(s) removida(s).")

        # Gera dados históricos a cada 10 segundos nos últimos 10 minutos
        now = timezone.now()
        start = now - timedelta(minutes=10)
        base_voltage = 220.0
        current_time = start
        readings = []

        while current_time <= now:
            base_voltage += random.uniform(-0.5, 0.5)
            base_voltage = max(216.0, min(224.0, base_voltage))
            value = round(base_voltage + random.uniform(-0.2, 0.2), 2)
            readings.append(
                Sensor(
                    device=device,
                    sensor_type=sensor_type,
                    value=value,
                    created_at=current_time,
                )
            )
            current_time += timedelta(seconds=10)

        Sensor.objects.bulk_create(readings)
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(readings)} leitura(s) históricas inseridas para {MOCK_MAC}."
            )
        )
