from django.db import models
from django.utils import timezone

# Create your models here.

class Device(models.Model):
    mac_address = models.CharField(primary_key=True, max_length=17, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=32, default='Novo Dispositivo IoT')

class SensorType(models.Model):
    name = models.CharField(primary_key=True, max_length=50)
    description = models.TextField()
    unit = models.CharField(max_length=20)
    min_value = models.FloatField()
    max_value = models.FloatField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']

class Sensor(models.Model):
    sensor_type = models.ForeignKey(SensorType, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    value = models.FloatField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)