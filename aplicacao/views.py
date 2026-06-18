from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .form import UsuarioForm
from .mqtt_client import MqttClient
from django.urls import reverse
from django.views.decorators.http import require_POST
import paho.mqtt.publish as publish
from django.conf import settings

import numpy as np
import pandas as pd
import io
import urllib, base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# vibration/views.py
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import VibrationCollection

@login_required(login_url="urlentrar")
def historico(request):
    collections = VibrationCollection.objects.all()
    return render(request, 'historico.html', {'collections': collections})

@require_POST
def excluir_coleta(request, pk):
    """View para excluir uma coleta de vibração"""
    coleta = get_object_or_404(VibrationCollection, pk=pk)
    motor_id = coleta.motor_id  # Guarda para redirecionamento
    
    try:
        coleta.delete()
        messages.success(request, f'Coleta #{pk} excluída com sucesso!')
    except Exception as e:
        messages.error(request, f'Erro ao excluir coleta: {str(e)}')
    
    # Redireciona de volta para o histórico
    return redirect('urlhistorico')  # Ajuste o nome da URL conforme seu projeto

@login_required(login_url="urlentrar")
def coletaManual(request):
    if request.method == 'POST':
        motor_id = request.POST.get('motor_id', 'MOTOR_01').strip()
        raw_data = request.POST.get('vibration_data', '').strip()
        
        try:
            data_list = json.loads(raw_data)
            if not isinstance(data_list, list) or len(data_list) != 10000:
                messages.error(request, "O vetor deve conter exatamente 10.000 valores numéricos.")
                return redirect('urlcoleta')
                
            # Validação básica de tipos
            if not all(isinstance(x, (int, float)) for x in data_list):
                messages.error(request, "Todos os valores devem ser numéricos.")
                return redirect('urlcoleta')

            VibrationCollection.objects.create(
                motor_id=motor_id,
                vibration_data=data_list,
                status='pending'
            )
            messages.success(request, "Coleta registrada com sucesso!")
            return redirect('urlhistorico')
            
        except json.JSONDecodeError:
            messages.error(request, "Formato inválido. Envie uma lista JSON válida (ex: [1.2, 3.4, ...]).")
            return redirect('urlcoleta')
            
    return render(request, 'coleta.html')


# ---------------------- CONFIGURAÇÕES MQTT ----------------------
@login_required(login_url="urlentrar")
def coleta(request):
    #comando = "coletar"
    #topico = "comando/sensor"
    #cliente = MqttClient()
    #cliente.connect()
    #cliente.publish(topico, comando)

    try:
        publish.single(
            topic="comando/sensor",
            payload="coletar",
            hostname=settings.MQTT_BROKER,
            port=settings.MQTT_PORT,
            auth={
                'username': settings.MQTT_USERNAME,
                'password': settings.MQTT_PASSWORD,
            },
        )
    except Exception as e:
        messages.error(request, f"Erro ao enviar comando MQTT: {e}")

    return render(request, 'index.html')

# ---------------------- Index ----------------------
@login_required(login_url="urlentrar")
def index(request):
    return render(request, 'index.html')

# ---------------------- Entrar ----------------------
def entrar(request):
    if request.method == "GET":
        return render(request, "entrar.html")
    elif request.method == "POST":
        usuario = request.POST.get("txtUser")
        senha = request.POST.get("txtPass")
        user = authenticate(username=usuario, password=senha)

        if user:
            login(request, user)
            return redirect('urlindex')
        messages.error(request, "Falha na autenticação!")    
        return render(request, 'entrar.html')

# ---------------------- Sair ----------------------
def sair(request):
    logout(request)
    return redirect('urlentrar')

# ---------------------- Novo usuário ----------------------
def cadastrarUsuario(request):
    if request.method == "GET":
        form = UsuarioForm()
        context = {'form': form}
        return render(request, 'cadastrarUsuario.html', context)
    else:
        form = UsuarioForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('urlentrar')

# ---------------------- Gráficos ----------------------
def get_dataframe(id):
    # Busca todos os dados do banco e retorna um DataFrame do Pandas
    # dados = VibrationCollection.objects.all().values()
    # dados = VibrationCollection.objects.filter(pk=id).values()
    dados = get_object_or_404(VibrationCollection, pk=id)
    print(dados)
    df = pd.DataFrame(data=dados.vibration_data, columns=['vibration'])
    # df = pd.DataFrame(data=dados['vibration_data'], columns=['vibration']) 
    return df

def plot_to_base64(fig):
    # Converte uma figura Matplotlib para uma string base64 para ser usada no HTML
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    string = base64.b64encode(buf.read())
    return urllib.parse.quote(string)

@login_required(login_url="urlentrar")
def grafico(request, pk):
    df = get_dataframe(pk)
    context = {
           'grafico': geragraficos(df['vibration'])
    }
    return render(request, 'grafico.html', context)

def geragraficos2(dfa, eixo='x', cor='blue', posicao='Axial', intervalo_grade=60):
    fs = 2000  # frequência de amostragem HZ

    signal = dfa.values
    # signal = signal - 512
    print(signal)
    signal = signal - np.mean(signal)
    
    # Aplicar janela de Hann para reduzir vazamento espectral
    window = np.hanning(len(signal))
    signal_windowed = signal * window
    
    # Calcular FFT
    N = len(signal)
    yf = np.fft.rfft(signal_windowed)  # só metade (frequências positivas)
    xf = np.fft.rfftfreq(N, 1 / fs)
    
    # Calcular magnitude (em escala linear ou logarítmica)
    magnitude = np.abs(yf)
    
    # Plotar
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(xf, magnitude, color=cor, linewidth=1.5)
    plt.title(f'Espectro de Frequência - Eixo {eixo} ({posicao})', fontsize=14, fontweight='bold')
    ax.set_xlabel('Frequência (Hz)', fontsize=12)
    ax.set_ylabel('Magnitude', fontsize=12)
    ax.set_xlim(0, fs/2)
    
    ax.margins(0)
    max_x = fs / 2
    ticks = np.arange(0, max_x, intervalo_grade)
    ax.set_xticks(ticks)
    ax.grid(True, axis='x', linestyle='-', linewidth=0.8, color='gray', alpha=0.5)
    ax.grid(True, axis='y', linestyle='-', linewidth=0.8, color='gray', alpha=0.5)
    plt.tight_layout()
    grafico_base64 = plot_to_base64(plt.gcf())
    plt.close(fig)  # Fecha a figura para liberar memória

    return grafico_base64

# ---------------------- AÇÕES ----------------------
# @login_required
# def ligar_motor(request, motor_id):
#     mqtt_pub_view("ligar")
#     motor = get_object_or_404(Motor, id=motor_id)
#     motor.ligado = True
#     motor.save()
#     LogAcionamento.objects.create(motor=motor, acao="LIGADO", usuario=request.user)
    
#     q = request.POST.get('q', '')
#     return redirect(f"{reverse('painel')}?q={q}")

# @login_required
# def desligar_motor(request, motor_id):
#     mqtt_pub_view("desligar")
#     motor = get_object_or_404(Motor, id=motor_id)
#     motor.ligado = False
#     motor.save()
#     LogAcionamento.objects.create(motor=motor, acao="DESLIGADO", usuario=request.user)

    # q = request.POST.get('q', '')
    # return redirect(f"{reverse('painel')}?q={q}")

def geragraficos(dfa, eixo='x', cor='blue', posicao='Axial', intervalo_grade=60):
    # ------------------------------------------------------------------
    # Parâmetros de aquisição e do circuito de condicionamento
    # ------------------------------------------------------------------
    fs   = 2000   # frequência de amostragem em Hz
                  # CORRIGIDO: era 1000, causando eixo X com metade do valor real

    VREF = 3.3    # tensão de referência do ADC (V)
    BITS = 1024   # resolução do ADC (10 bits → 2^10)
    GANHO = 1.5   # ganho do amplificador de condicionamento
                  # calculado a partir do esquemático: R5/R3 = 15kΩ / 10kΩ

    # ------------------------------------------------------------------
    # 1. Remoção do offset DC
    #    O circuito polariza o sinal em VCC/2 (~512 counts) para que o
    #    sinal AC do sensor ocupe toda a faixa do ADC (0 a 1023).
    #    A subtração da média remove esse offset antes da FFT.
    # ------------------------------------------------------------------
    signal = dfa.values.astype(float)
    signal = signal - np.mean(signal)

    # ------------------------------------------------------------------
    # 2. Conversão de contagens ADC para Volts
    #    Desfaz o ganho do amplificador para expressar o sinal na escala
    #    de tensão real na saída do sensor piezoelétrico.
    # ------------------------------------------------------------------
    signal_v = signal * (VREF / BITS) / GANHO

    # ------------------------------------------------------------------
    # 3. Janela de Hann
    #    Reduz o vazamento espectral causado pela descontinuidade nas
    #    bordas do bloco de amostras.
    # ------------------------------------------------------------------
    N = len(signal_v)
    window = np.hanning(N)
    signal_windowed = signal_v * window

    # ------------------------------------------------------------------
    # 4. FFT unilateral (somente frequências positivas)
    # ------------------------------------------------------------------
    yf = np.fft.rfft(signal_windowed)
    xf = np.fft.rfftfreq(N, 1 / fs)

    # ------------------------------------------------------------------
    # 5. Magnitude normalizada pelo fator de correção da janela
    #    CORRIGIDO: era np.abs(yf) sem normalização, o que fazia a
    #    amplitude escalar com N e perder sentido físico.
    #    A normalização por sum(window) corrige o ganho introduzido pela
    #    janela, e o fator 2 compensa o descarte das frequências negativas
    #    no espectro unilateral.
    # ------------------------------------------------------------------
    magnitude = (2 / np.sum(window)) * np.abs(yf)

    # ------------------------------------------------------------------
    # 6. Plot
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(xf, magnitude, color=cor, linewidth=1.5)
    plt.title(
        f'Espectro de Frequência - Eixo {eixo} ({posicao})',
        fontsize=14, fontweight='bold'
    )
    ax.set_xlabel('Frequência (Hz)', fontsize=12)
    ax.set_ylabel('Amplitude (V)', fontsize=12)  # CORRIGIDO: era 'Magnitude'
    # max_x = fs / 2
    # ax.set_xlim(0, fs / 2)
    max_x = 600
    ax.set_xlim(0, max_x)
    ax.margins(0)
    
    ticks = np.arange(0, max_x + intervalo_grade, intervalo_grade)
    ax.set_xticks(ticks)
    ax.grid(True, axis='x', linestyle='-', linewidth=0.8, color='gray', alpha=0.5)
    ax.grid(True, axis='y', linestyle='-', linewidth=0.8, color='gray', alpha=0.5)
    plt.tight_layout()
    grafico_base64 = plot_to_base64(plt.gcf())
    plt.close(fig)  # Fecha a figura para liberar memória

    return grafico_base64