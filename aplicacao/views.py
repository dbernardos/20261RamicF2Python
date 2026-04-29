from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .form import UsuarioForm
from .mqtt_client import MqttClient
from django.urls import reverse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io, urllib, base64

# vibration/views.py
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import VibrationCollection

def historico(request):
    collections = VibrationCollection.objects.all()
    return render(request, 'historico.html', {'collections': collections})

def coleta(request):
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


# ---------------------- CONFIGURAÇÕES MQTT: DAVI ----------------------
def mqtt_pub_view(comando):
    cliente = MqttClient()
    cliente.connect()

    #payload = json.dumps({"comando": comando})
    cliente.publish("motor/a110", comando)

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

@login_required(login_url="urlentrar")
def index(request):
    return render(request, 'index.html')

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

def sair(request):
    logout(request)
    return redirect('urlentrar')

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

def grafico(request):
    return render(request, 'grafico.html')


def geragraficos(dfa, eixo, cor, posicao, intervalo_grade, arquivo):
    fs = 1000  # frequência de amostragem HZ
    signal = dfa.values
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
    plt.title(f'{arquivo}: Espectro de Frequência - Eixo {eixo} ({posicao})', fontsize=14, fontweight='bold')
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
    return plt