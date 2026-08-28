import os
import datetime
from datetime import timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory

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
def inicio():
    # Muestra primero la pantalla con el logotipo y la frase para el código QR
    return render_template('logotipo.html')

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

# Estructura ampliada para guardar tanto pulso como acelerómetro
estado_telemetria_actual = {
    "ritmo_cardiaco": 0,
    "temperatura": 38.0,
    "acx": 0,
    "acy": 0,
    "acz": 0,
    "pechera_puesta": True
}

@app.route('/api/actualizar_telemetria', methods=['POST'])
def actualizar_telemetria():
    global estado_telemetria_actual
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "mensaje": "JSON vacío"}), 400
    
    # Capturar opcionalmente ritmo cardíaco si se envía
    if "ritmo_cardiaco" in data:
        estado_telemetria_actual["ritmo_cardiaco"] = int(data["ritmo_cardiaco"])
    
    # Capturar ejes del MPU6050
    if "acx" in data:
        estado_telemetria_actual["acx"] = int(data["acx"])
    if "acy" in data:
        estado_telemetria_actual["acy"] = int(data["acy"])
    if "acz" in data:
        estado_telemetria_actual["acz"] = int(data["acz"])
        
    estado_telemetria_actual["pechera_puesta"] = True
    return jsonify({"status": "success"}), 200

@app.route('/api/telemetria', methods=['GET'])
@login_required
def api_telemetria():
    global estado_telemetria_actual
    ahora = obtener_hora_ecuador()
    diag = evaluar_estado_clinico(estado_telemetria_actual["temperatura"], estado_telemetria_actual["ritmo_cardiaco"], True)
    
    return jsonify({
        "temperatura": estado_telemetria_actual["temperatura"],
        "ritmo_cardiaco": estado_telemetria_actual["ritmo_cardiaco"],
        "acx": estado_telemetria_actual["acx"],
        "acy": estado_telemetria_actual["acy"],
        "acz": estado_telemetria_actual["acz"],
        "pechera_puesta": estado_telemetria_actual["pechera_puesta"],
        "actividad": {"estado": "Monitoreo MPU6050 Activo"},
        "ultima_actualizacion": ahora.strftime("%H:%M:%S"),
        "diagnostico": diag,
        "gps": {"valido": False, "latitud": -1.3458, "longitud": -80.4285}
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

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
