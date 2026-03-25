from datetime import timedelta
import random
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Min, Max, OuterRef, Subquery
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

from .models import Device, Sensor, SensorType

# Create your views here.

def get_chart_data(device, sensor_type, last_10min, now):
    sensors = (
        Sensor.objects
        .filter(
            device=device,
            sensor_type=sensor_type,
            created_at__gte=last_10min,
            created_at__lte=now
        )
        .order_by("created_at")
        .values_list("created_at", "value")
    )

    chart_data = []

    for created_at, value in sensors:
        # Definir cor direto no ponto (sem agregação)
        if value > sensor_type.max_value:
            color = "red"
        elif value < sensor_type.min_value + 15:
            color = "yellow"
        else:
            color = "green"

        chart_data.append({
            "time": created_at.strftime("%H:%M:%S"),
            "value": round(value, 2),
            "color": color
        })

    return chart_data

def home(request):
    now = timezone.now()
    last_10min = now - timedelta(minutes=10)

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
            created_at__gte=last_10min
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
                created_at__gte=last_10min
            )
            .aggregate(
                min_10min=Min("value"),
                max_10min=Max("value")
            )
        )

        if stats["min_10min"] is not None and stats["max_10min"] is not None:
            chart_min = max(200, stats["min_10min"] - 2)
            chart_max = min(240, stats["max_10min"] + 2)
        else:
            chart_min = 200
            chart_max = 240

        current = device.current_value

        tensao = "NORMAL"
        if current is not None:
            if current > sensor_type.max_value:
                tensao = "ELEVADA"
            if current < sensor_type.min_value:
                tensao = "BAIXA"

        # Gerar dados do gráfico
        chart_data = get_chart_data(device, sensor_type, last_10min, now)

        devices_data.append({
            "id": device.mac_address,
            "name": device.name,
            "current": round(current, 2) if current else None,
            "min_10min": round(stats["min_10min"], 2) if stats["min_10min"] else None,
            "max_10min": round(stats["max_10min"], 2) if stats["max_10min"] else None,
            "unit": sensor_type.unit,
            "tensao": tensao,
            "chart_data": json.dumps(chart_data),
            "chart_min": chart_min,
            "chart_max": chart_max,
        })

    return render(request, "home.html", {
        "devices": devices_data
    })

@require_POST
def delete_device(request, mac):
    try:
        device = Device.objects.get(mac_address=mac)
    except Device.DoesNotExist:
        return JsonResponse({'error': 'Dispositivo não encontrado'}, status=404)

    device.delete()
    return JsonResponse({'success': True})

@require_POST
def edit_device_name(request, mac):
    try:
        device = Device.objects.get(mac_address=mac)
    except Device.DoesNotExist:
        return JsonResponse({'error': 'Dispositivo não encontrado'}, status=404)

    data = json.loads(request.body.decode('utf-8'))
    new_name = data.get('name', '').strip()

    if not new_name:
        return JsonResponse({'error': 'Nome inválido'}, status=400)

    device.name = new_name
    device.save(update_fields=['name', 'updated_at'])

    return JsonResponse({'success': True, 'name': device.name})

@csrf_exempt
def update(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    mac_address = data.get('mac')
    if not mac_address:
        return JsonResponse({'error': 'MAC address não fornecido'}, status=400)

    # Cria ou atualiza o device
    device, _ = Device.objects.update_or_create(mac_address=mac_address)
    updated_now = (timezone.now() - device.updated_at).total_seconds() < 60

    # Salva dados dos sensores (mantendo histórico de 12h)
    from datetime import timedelta
    if "sensors" in data:
        now = timezone.now()
        for sensor in data['sensors']:
            sensor_type_name = sensor.get('type')
            value = sensor.get('value')

            if not sensor_type_name or value is None:
                continue  # ignora entradas incompletas

            try:
                sensor_type = SensorType.objects.get(name=sensor_type_name)
            except SensorType.DoesNotExist:
                continue  # ignora sensores não cadastrados

            # Remove dados mais antigos que 12h para este sensor/dispositivo
            Sensor.objects.filter(device=device,sensor_type=sensor_type,created_at__lt=now - timedelta(hours=12)).delete()

            # Salva novo dado (não substitui)
            Sensor.objects.create(device=device,sensor_type=sensor_type,value=value,)

    # Monta resposta com valores e intervalos válidos (apenas o dado mais recente de cada sensor)
    sensors = Sensor.objects.filter(device=device).order_by('sensor_type', '-created_at')
    latest_sensors = {}
    for s in sensors:
        if s.sensor_type.name not in latest_sensors:
            latest_sensors[s.sensor_type.name] = s

    response_json = {}
    for name, s in latest_sensors.items():
        response_json[name] = s.value
        response_json[f"{name}_min"] = s.sensor_type.min_value
        response_json[f"{name}_max"] = s.sensor_type.max_value

    return JsonResponse(response_json)