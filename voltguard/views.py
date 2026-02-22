from datetime import timedelta
import random
from django.utils import timezone
from django.db.models import Min, Max, OuterRef, Subquery
from django.shortcuts import render
import json

from .models import Device, Sensor, SensorType

# Create your views here.

def get_chart_data(device, sensor_type, last_24h, now):
    sensors = (
        Sensor.objects
        .filter(
            device=device,
            sensor_type=sensor_type,
            created_at__gte=last_24h,
            created_at__lte=now
        )
        .order_by("created_at")
        .values_list("created_at", "value")
    )
    
    sensors_list = list(sensors)
    if not sensors_list:
        return []
    
    # Criar buckets de 10 minutos - usar o primeiro sensor como referência base
    buckets = {}
    base_time = sensors_list[0][0].replace(minute=0, second=0, microsecond=0)

    # Criar buckets de 10 minutos - usar o primeiro sensor como referência base
    for i in range(144):  # 144 buckets de 10min em 24h
        bucket_start = base_time + timedelta(minutes=10 * i)
        buckets[bucket_start] = {"max": None, "color": "gray"}
    
    # Preencher buckets com dados
    buckets_filled = {}
    bucket_all_values = {}
    
    for created_at, value in sensors_list:
        # Calcular qual bucket este sensor pertence
        diff_minutes = (created_at - base_time).total_seconds() / 60
        bucket_index = int(diff_minutes // 10)
        bucket_start = base_time + timedelta(minutes=10 * bucket_index)
        
        if bucket_start not in bucket_all_values:
            bucket_all_values[bucket_start] = []
        
        bucket_all_values[bucket_start].append(value)
    
    # Calcular PERCENTIL 75 para cada bucket (mais sensível a problemas)
    import statistics
    for bucket_start, values in bucket_all_values.items():
        # Usar percentil 75: 75% dos valores estão abaixo deste valor
        sorted_values = sorted(values)
        p75_index = int(len(sorted_values) * 0.75)
        p75_value = sorted_values[p75_index] if p75_index < len(sorted_values) else sorted_values[-1]
        buckets_filled[bucket_start] = p75_value
    
    # Determinar cores
    chart_data = []
    
    for bucket_start, data in sorted(buckets.items()):
        max_value = buckets_filled.get(bucket_start)
        
        if max_value is None:
            color = "gray"
        elif max_value > sensor_type.max_value:
            color = "red"
        elif max_value < sensor_type.min_value + 15:
            color = "yellow"
        else:
            color = "green"
        
        chart_data.append({
            "time": bucket_start.strftime("%H:%M"),
            "value": round(max_value, 2) if max_value else None,
            "color": color
        })
    
    return chart_data

def home(request):
    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    try:
        sensor_type = SensorType.objects.get(name="voltA")
    except SensorType.DoesNotExist:
        return render(request, "home.html", {"devices": []})

    # Subquery para pegar o último valor de cada device
    last_value_subquery = (
        Sensor.objects
        .filter(
            device=OuterRef("pk"),
            sensor_type=sensor_type,
            created_at__gte=last_24h
        )
        .order_by("-created_at")
        .values("value")[:1]
    )

    # Devices anotados com último valor
    devices = (
        Device.objects
        .annotate(current_value=Subquery(last_value_subquery))
    )

    devices_data = []

    for device in devices:

        stats = (
            Sensor.objects
            .filter(
                device=device,
                sensor_type=sensor_type,
                created_at__gte=last_24h
            )
            .aggregate(
                min_24h=Min("value"),
                max_24h=Max("value")
            )
        )

        if stats["min_24h"] is not None and stats["max_24h"] is not None:
            chart_min = max(200, stats["min_24h"] - 2)
            chart_max = min(240, stats["max_24h"] + 2)
        else:
            chart_min = 200
            chart_max = 240

        current = device.current_value
        if current is not None:
            current = random.uniform(200.00, 240.00)  # Simulação de valor atual

        tensao = "NORMAL"
        if current is not None:
            if current > sensor_type.max_value:
                tensao = "ELEVADA"
            if current < sensor_type.min_value:
                tensao = "BAIXA"

        # Gerar dados do gráfico
        chart_data = get_chart_data(device, sensor_type, last_24h, now)

        devices_data.append({
            "id": device.mac_address,
            "name": device.name,
            "current": round(current, 2) if current else None,
            "min_24h": round(stats["min_24h"], 2) if stats["min_24h"] else None,
            "max_24h": round(stats["max_24h"], 2) if stats["max_24h"] else None,
            "unit": sensor_type.unit,
            "tensao": tensao,
            "chart_data": json.dumps(chart_data),
            "chart_min": chart_min,
            "chart_max": chart_max,
        })

    return render(request, "home.html", {
        "devices": devices_data
    })