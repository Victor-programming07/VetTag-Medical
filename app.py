import os
import datetime
from datetime import timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "vettag_telemetry_secure_key"

# Base de datos en memoria para el historial de prescripciones
HISTORIAL_DOSIS = []
PROXIMO_ID_DOSIS = 1

# Estado global para recibir los datos físicos del ESP32 paso a paso
ESTADO_HARDWARE = {
    "conectado": False,
    "temperatura": 0.0,
    "ritmo_cardiaco": 0,
    "actividad": {"estado": "En espera de sensor", "icono": "⏳"},
    "ultima_actualizacion": "---"
}

def evaluar_estado_clinico(temp, bpm):
    """Calcula el diagnóstico por IA según los rangos vitales del paciente."""
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
    elif temp < 37.5 and temp > 0:
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
    elif bpm < 60 and bpm > 0:
        return {
            "salud_mascota": "Bradicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Frecuencia cardíaca anormalmente baja. Se sugiere monitoreo de pulso."
        }
    elif temp == 0 and bpm == 0:
        return {
            "salud_mascota": "Sin Conexión de Sensores",
            "badge_class": "bg-secondary",
            "mensaje": "A la espera de datos físicos desde el ESP32."
        }
    else:
        return {
            "salud_mascota": "Estado Normal",
            "badge_class": "bg-success",
            "mensaje": "Constantes vitales dentro de rangos fisiológicos estables."
        }

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('usuario_autenticado'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['usuario_autenticado'] = True
        return redirect(url_for('panel_dueno'))
    return render_template('login.html')

@app.route('/dueno')
@login_required
def panel_dueno():
    return render_template('dueno.html')

@app.route('/medico')
@login_required
def panel_medico():
    return render_template('medico.html')

@app.route('/cambiar_credenciales', methods=['GET', 'POST'])
@login_required
def cambiar_credenciales():
    if request.method == 'POST':
        flash("Credenciales actualizadas correctamente.", "success")
        return redirect(url_for('panel_medico'))
    return render_template('cambiar_credenciales.html')

@app.route('/api/datos', methods=['POST'])
def recibir_esp32():
    """Endpoint para recibir los datos del ESP32 de forma modular."""
    global ESTADO_HARDWARE
    data = request.get_json() or {}
    
    ESTADO_HARDWARE["conectado"] = True
    
    if "temperatura" in data:
        ESTADO_HARDWARE["temperatura"] = float(data["temperatura"])
    if "ritmo_cardiaco" in data:
        ESTADO_HARDWARE["ritmo_cardiaco"] = int(data["ritmo_cardiaco"])
    if "actividad" in data:
        ESTADO_HARDWARE["actividad"] = data["actividad"]
        
    ESTADO_HARDWARE["ultima_actualizacion"] = datetime.datetime.now().strftime("%H:%M:%S")
    return jsonify({"status": "success", "mensaje": "Datos recibidos con éxito"}), 200

@app.route('/api/telemetria', methods=['GET'])
def api_telemetria():
    """Devuelve a los paneles web los datos reales leídos por el ESP32."""
    global ESTADO_HARDWARE
    temp = ESTADO_HARDWARE["temperatura"]
    bpm = ESTADO_HARDWARE["ritmo_cardiaco"]
    
    diag = evaluar_estado_clinico(temp, bpm)
    
    return jsonify({
        "conectado": ESTADO_HARDWARE["conectado"],
        "temperatura": temp,
        "ritmo_cardiaco": bpm,
        "actividad": ESTADO_HARDWARE["actividad"],
        "ultima_actualizacion": ESTADO_HARDWARE["ultima_actualizacion"],
        "diagnostico": diag
    })

@app.route('/api/guardar_dosis', methods=['POST'])
def guardar_dosis():
    global PROXIMO_ID_DOSIS
    data = request.get_json() or {}
    peso = float(data.get('peso', 0.0))
    dosis_mg_kg = float(data.get('dosis_mg_kg', 0.0))
    concentracion = float(data.get('concentracion', 1.0))
    volumen_ml = round((peso * dosis_mg_kg) / concentracion, 2) if concentracion > 0 else 0.0

    nuevo_registro = {
        "id": PROXIMO_ID_DOSIS,
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "paciente": data.get('paciente', 'Desconocido'),
        "peso": peso,
        "propietario": data.get('propietario', 'N/A'),
        "telefono": data.get('telefono', 'N/A'),
        "correo": data.get('correo', 'N/A'),
        "direccion": data.get('direccion', 'N/A'),
        "farmaco": data.get('farmaco', 'N/A'),
        "dosis_mg_kg": dosis_mg_kg,
        "concentracion": concentracion,
        "volumen_ml": volumen_ml,
        "sugerencias": data.get('sugerencias', 'Sin observaciones.')
    }
    HISTORIAL_DOSIS.append(nuevo_registro)
    PROXIMO_ID_DOSIS += 1
    return jsonify({"status": "success", "id": nuevo_registro["id"]}), 201

@app.route('/api/historial_dosis', methods=['GET'])
def obtener_historial_dosis():
    return jsonify(HISTORIAL_DOSIS)

@app.route('/api/eliminar_dosis/<int:id_dosis>', methods=['DELETE'])
def eliminar_dosis(id_dosis):
    global HISTORIAL_DOSIS
    HISTORIAL_DOSIS = [item for item in HISTORIAL_DOSIS if item['id'] != id_dosis]
    return jsonify({"status": "success", "deleted_id": id_dosis})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
