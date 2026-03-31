import random
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from voltguard.models import Device, Sensor, SensorType

MOCK_MAC = "AA:BB:CC:DD:EE:FF"
INTERVAL_SECONDS = 10
REAL_DEVICE_WINDOW = timedelta(minutes=2)


class Command(BaseCommand):
    help = (
        "Alimenta o dispositivo mock com leituras a cada 10 s. "
        "Encerra e remove o mock automaticamente quando outro dispositivo real estiver ativo."
    )

    def handle(self, *args, **options):
        self.stdout.write("Simulação do dispositivo mock iniciada. Pressione Ctrl+C para parar.")

        base_voltage = 220.0

        while True:
            try:
                if self._real_device_active():
                    self.stdout.write(
                        self.style.WARNING(
                            "Dispositivo real detectado. Removendo mock e encerrando simulação."
                        )
                    )
                    self._remove_mock()
                    break

                base_voltage = self._clamp(base_voltage + random.uniform(-0.5, 0.5), 216.0, 224.0)
                self._insert_reading(base_voltage)

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\nSimulação interrompida pelo usuário."))
                break
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Erro inesperado: {exc}"))

            time.sleep(INTERVAL_SECONDS)

        self.stdout.write("Simulação encerrada.")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _real_device_active(self) -> bool:
        """Retorna True se qualquer dispositivo diferente do mock tiver enviado dados recentemente."""
        cutoff = timezone.now() - REAL_DEVICE_WINDOW
        return (
            Sensor.objects.filter(created_at__gte=cutoff)
            .exclude(device__mac_address=MOCK_MAC)
            .exists()
        )

    def _insert_reading(self, base_voltage: float) -> None:
        try:
            sensor_type = SensorType.objects.get(name="voltA")
            device = Device.objects.get(mac_address=MOCK_MAC)
        except (SensorType.DoesNotExist, Device.DoesNotExist):
            self.stdout.write(
                self.style.ERROR(
                    "Mock device ou SensorType não encontrado. Execute seed_mock primeiro."
                )
            )
            return

        now = timezone.now()

        # Mantém apenas últimos 20 minutos (mesma política do endpoint /update/)
        Sensor.objects.filter(device=device, created_at__lt=now - timedelta(minutes=20)).delete()

        value = round(base_voltage + random.uniform(-0.2, 0.2), 2)
        Sensor.objects.create(device=device, sensor_type=sensor_type, value=value)
        self.stdout.write(f"[{now.strftime('%H:%M:%S')}] {MOCK_MAC} → {value} V")

    def _remove_mock(self) -> None:
        try:
            Device.objects.get(mac_address=MOCK_MAC).delete()
            self.stdout.write(self.style.SUCCESS("Dispositivo mock removido do banco de dados."))
        except Device.DoesNotExist:
            pass

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))
