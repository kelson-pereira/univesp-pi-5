from datetime import timedelta
from collections import defaultdict
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
    interval = 10  # segundos
    total_seconds = int((now - last_10min).total_seconds())
    total_slots = total_seconds // interval  # ~60 slots de 10s em 10 minutos

    # Busca dados reais
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

    # Cria slot para indexar valores por intervalo de 10s
    slot_map = defaultdict(list)

    # Preencher valores nos slots correspondentes
    for created_at, value in sensors:
        delta = int((created_at - last_10min).total_seconds())
        # slot_index = delta // interval
        slot_index = max(0, min(delta // interval, total_slots))
        slot_map[slot_index].append((created_at, value))

    chart_data = []

    for i in range(total_slots + 1):
        slot_time = last_10min + timedelta(seconds=i * interval)

        if i in slot_map:
            values = [v for _, v in slot_map[i]]

            # Se houver zero, prioriza zero (garante que queda de energia não seja suavizada pela média)
            if 0 in values:
                value = 0
            else:
                value = sum(values) / len(values)  # média

            if value == 0:
                color = "black"
            elif value > 225:
                color = "red"
            elif value < 215:
                color = "yellow"
            else:
                color = "green"

            chart_data.append({
                "time": slot_time.strftime("%d/%m/%Y %H:%M:%S"),
                "value": round(value, 2),
                "color": color
            })
        else:
            # SLOT VAZIO
            chart_data.append({
                "time": slot_time.strftime("%d/%m/%Y %H:%M:%S"),
                "value": None,
                "color": None
            })

    return chart_data

def get_table_data(device, sensor_type, last_10min, now):
    sensors = (
        Sensor.objects
        .filter(
            device=device,
            sensor_type=sensor_type,
            created_at__gte=last_10min,
            created_at__lte=now
        )
        .order_by("-created_at")  # mais recente primeiro
        .values_list("created_at", "value")
    )

    table_data = []

    for created_at, value in sensors:

        if value == 0:
            color = "black"
        elif value > 225:
            color = "red"
        elif value < 215:
            color = "yellow"
        else:
            color = "green"

        table_data.append({
            "time": created_at.strftime("%d/%m/%Y %H:%M:%S"),
            "value": round(value, 2),
            "color": color
        })

    return table_data

def floor_time(dt, seconds=10):
    return dt - timedelta(
        seconds=dt.second % seconds,
        microseconds=dt.microsecond
    )

def home(request):
    now = floor_time(timezone.now(), 10)
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
                created_at__gte=last_10min,
                value__gt=0
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
            if current > 225:
                tensao = "ELEVADA"
            if current < 215:
                tensao = "BAIXA"

        # Gerar dados do gráfico (últimos 10 minutos) - Slot de 10s para suavisar e prevenir falhas de leitura
        chart_data = get_chart_data(device, sensor_type, last_10min, now)

        # Gerar dados da tabela (últimos 10 minutos)
        table_data = get_table_data(device, sensor_type, last_10min, now)

        devices_data.append({
            "id": device.mac_address,
            "name": device.name,
            "current": round(current, 2) if current is not None else None,
            "min_10min": round(stats["min_10min"], 2) if stats["min_10min"] else None,
            "max_10min": round(stats["max_10min"], 2) if stats["max_10min"] else None,
            "unit": sensor_type.unit,
            "tensao": tensao,
            "chart_data": json.dumps(chart_data),
            "chart_min": chart_min,
            "chart_max": chart_max,
            "table_data": json.dumps(table_data),
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
    
    if "sensors" in data:
        now = timezone.now()

        # Mantém apenas últimos 20 minutos
        cutoff = now - timedelta(minutes=20)
        Sensor.objects.filter(
            device=device,
            created_at__lt=cutoff
        ).delete()
        
        for sensor in data['sensors']:
            sensor_type_name = sensor.get('type')
            value = sensor.get('value')

            if not sensor_type_name or value is None:
                continue  # ignora entradas incompletas

            try:
                sensor_type = SensorType.objects.get(name=sensor_type_name)
            except SensorType.DoesNotExist:
                continue  # ignora sensores não cadastrados

            # Filtro de valores inválidos
            if value < 0 or value > 250:
                print(f"[IGNORADO] Valor fora da faixa: {value}V ({mac_address})")
                continue

            # Filtro de Spike (variação brusca)
            last = (
                Sensor.objects
                .filter(device=device, sensor_type=sensor_type)
                .order_by('-created_at')
                .first()
            )

            if last:
                # Ignora spike APENAS se ambos valores forem diferentes de zero
                if last.value != 0 and value != 0:
                    if abs(value - last.value) > 50:
                        print(f"Spike detectado (ignorando): {value}V (último: {last.value}V)")
                        continue

            # Salva somente valores válidos
            Sensor.objects.create(
                device=device,
                sensor_type=sensor_type,
                value=value,
            )

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