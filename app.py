import os
import random
import datetime
from datetime import timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "vettag_telemetry_secure_key"

# Base de datos en memoria para el historial de prescripciones
HISTORIAL_DOSIS = []
PROXIMO_ID_DOSIS = 1

def evaluar_estado_clinico(temp, bpm, arnes_puesto):
    """Calcula el diagnóstico por IA según los rangos vitales del paciente."""
    if not arnes_puesto:
        return {
            "salud_mascota": "Arnés Desconectado",
            "badge_class": "bg-danger",
            "mensaje": "El arnés capacitivo no detecta contacto. Verifique la sujeción del dispositivo."
        }
    
    if temp > 39.2 and bpm > 140:
        return {
            "salud_mascota": "Estado Crítico",
            "badge_class": "bg-danger",
            "mensaje": "Alerta de Hipertermia severa y Taquicardia. Requiere intervención médica inmediata."
        }
    elif temp > 39.2:
        return {
            "salud_mascota": "Fiebre Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Temperatura corporal elevada por encima del rango normal (37.5°C - 39.2°C)."
        }
    elif temp < 37.5:
        return {
            "salud_mascota": "Hipotermia Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Temperatura corporal por debajo del límite seguro. Mantener abrigado."
        }
    elif bpm > 140:
        return {
            "salud_mascota": "Taquicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Frecuencia cardíaca acelerada por encima de los valores basales en reposo."
        }
    elif bpm < 60:
        return {
            "salud_mascota": "Bradicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Frecuencia cardíaca anormalmente baja. Se sugiere monitoreo de pulso."
        }
    else:
        return {
            "salud_mascota": "Estado Normal",
            "badge_class": "bg-success",
            "mensaje": "Constantes vitales dentro de rangos fisiológicos estables."
        }

def login_required(f):
    """Protege las rutas que requieren sesión activa."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('usuario_autenticado'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# RUTAS DE NAVEGACIÓN (VISTAS HTML)
# ==========================================
@app.route('/cambiar_credenciales', methods=['GET', 'POST'])
@login_required
def cambiar_credenciales():
    """Ruta para actualizar las credenciales del sistema."""
    if request.method == 'POST':
        # Lógica para guardar la nueva contraseña
        flash("Contraseña actualizada exitosamente.", "success")
        return redirect(url_for('panel_dueno'))
    return render_template('cambiar_credenciales.html')
    
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gestiona el inicio de sesión para desbloquear los paneles."""
    if request.method == 'POST':
        # Aquí puedes validar tu contraseña o credenciales personalizadas
        # Por ahora, activamos la sesión de manera segura al enviar el formulario:
        session['usuario_autenticado'] = True
        return redirect(url_for('panel_dueno')) # O la vista que prefieras por defecto
        
    return render_template('login.html')

@app.route('/dueno')
@login_required
def panel_dueno():
    """Ruta protegida para la interfaz del dueño."""
    return render_template('dueno.html')

@app.route('/medico')
@login_required
def panel_medico():
    """Ruta protegida para la interfaz del médico."""
    return render_template('medico.html')

# ==========================================
# ENDPOINTS DE TELEMETRÍA Y DATOS (API)
# ==========================================

@app.route('/api/telemetria', methods=['GET'])
def api_telemetria():
    """Devuelve valores en cero a la espera de la integración física con el ESP32."""
    return jsonify({
        "conectado": False,
        "temperatura": 0.0,
        "ritmo_cardiaco": 0,
        "pechera_puesta": False,
        "actividad": {"estado": "En Espera", "icono": "⚪"},
        "ultima_actualizacion": "---",
        "diagnostico": {
            "salud_mascota": "Sin Dispositivo",
            "badge_class": "bg-secondary",
            "mensaje": "A la espera de la conexión con el microcontrolador ESP32."
        },
        "gps": {
            "valido": False,
            "latitud": -1.3458,
            "longitud": -80.4285
        }
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
