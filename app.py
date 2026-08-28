
```python
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

# Estado global para recibir los datos físicos del ESP32
ESTADO_HARDWARE = {
    "conectado": False,
    "temperatura": 0.0,
    "ritmo_cardiaco": 0,
    "actividad": {
        "estado": "En espera de sensor",
        "icono": "⏳"
    },
    "ultima_actualizacion": "---"
}


def obtener_hora_ecuador():
    zona_ecuador = timezone(timedelta(hours=-5))
    return datetime.datetime.now(zona_ecuador)


def evaluar_estado_clinico(temp, bpm):
    """Calcula el diagnóstico según los rangos vitales."""

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


# ==========================================================
# TELEMETRÍA
# ==========================================================

estado_telemetria_actual = {
    "ritmo_cardiaco": 0,
    "temperatura": 38.0,
    "actividad": "En espera de sensor",
    "acx": 0.0,
    "acy": 0.0,
    "acz": 0.0,
    "pechera_puesta": True,
    "conectado": False,
    "ultima_actualizacion": "---"
}


# ==========================================================
# ESP32 → FLASK
# ==========================================================

@app.route('/api/actualizar_telemetria', methods=['POST'])
def actualizar_telemetria():

    global estado_telemetria_actual

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "mensaje": "JSON vacío"
            }), 400

        # Temperatura
        if "temperatura" in data:
            estado_telemetria_actual["temperatura"] = float(
                data["temperatura"]
            )

        # Ritmo cardíaco
        if "ritmo_cardiaco" in data:
            estado_telemetria_actual["ritmo_cardiaco"] = int(
                data["ritmo_cardiaco"]
            )

        # Actividad
        if "actividad" in data:
            estado_telemetria_actual["actividad"] = str(
                data["actividad"]
            )

        # MPU6050 X
        if "acx" in data:
            estado_telemetria_actual["acx"] = float(
                data["acx"]
            )

        # MPU6050 Y
        if "acy" in data:
            estado_telemetria_actual["acy"] = float(
                data["acy"]
            )

        # MPU6050 Z
        if "acz" in data:
            estado_telemetria_actual["acz"] = float(
                data["acz"]
            )

        # El ESP32 está conectado
        estado_telemetria_actual["conectado"] = True

        # Pechera conectada
        estado_telemetria_actual["pechera_puesta"] = True

        # Hora de última actualización
        ahora = obtener_hora_ecuador()

        estado_telemetria_actual["ultima_actualizacion"] = (
            ahora.strftime("%H:%M:%S")
        )

        # Mostrar en consola
        print("================================")
        print("TELEMETRIA RECIBIDA")
        print("Temperatura:",
              estado_telemetria_actual["temperatura"])
        print("Ritmo:",
              estado_telemetria_actual["ritmo_cardiaco"])
        print("Actividad:",
              estado_telemetria_actual["actividad"])
        print("ACC X:",
              estado_telemetria_actual["acx"])
        print("ACC Y:",
              estado_telemetria_actual["acy"])
        print("ACC Z:",
              estado_telemetria_actual["acz"])
        print("================================")

        return jsonify({
            "status": "success",
            "mensaje": "Telemetría recibida correctamente"
        }), 200

    except Exception as e:

        print("ERROR TELEMETRIA:", str(e))

        return jsonify({
            "status": "error",
            "mensaje": str(e)
        }), 500


# ==========================================================
# FLASK → DUENO.HTML
# ==========================================================

@app.route('/api/telemetria', methods=['GET'])
@login_required
def api_telemetria():

    global estado_telemetria_actual

    ahora = obtener_hora_ecuador()

    # Obtener temperatura
    temperatura = estado_telemetria_actual.get(
        "temperatura",
        0.0
    )

    # Obtener ritmo cardíaco
    ritmo_cardiaco = estado_telemetria_actual.get(
        "ritmo_cardiaco",
        0
    )

    # Obtener actividad
    actividad = estado_telemetria_actual.get(
        "actividad",
        "En espera de sensor"
    )

    # Obtener pechera
    pechera = estado_telemetria_actual.get(
        "pechera_puesta",
        False
    )

    # Obtener conexión
    conectado = estado_telemetria_actual.get(
        "conectado",
        False
    )

    # Obtener acelerómetro
    acx = estado_telemetria_actual.get(
        "acx",
        0.0
    )

    acy = estado_telemetria_actual.get(
        "acy",
        0.0
    )

    acz = estado_telemetria_actual.get(
        "acz",
        0.0
    )

    # ======================================================
    # ICONO DE ACTIVIDAD
    # ======================================================

    actividad_lower = actividad.lower()

    if "corriendo" in actividad_lower or "agitado" in actividad_lower:
        icono = "🔴"

    elif "caminando" in actividad_lower or "movimiento" in actividad_lower:
        icono = "🟡"

    elif "reposo" in actividad_lower:
        icono = "🟢"

    elif "espera" in actividad_lower:
        icono = "⏳"

    else:
        icono = "📡"


    # ======================================================
    # DIAGNÓSTICO
    # ======================================================

    diagnostico = evaluar_estado_clinico(
        temperatura,
        ritmo_cardiaco
    )


    # ======================================================
    # RESPUESTA
    # ======================================================

    return jsonify({

        "conectado": conectado,

        "temperatura": temperatura,

        "ritmo_cardiaco": ritmo_cardiaco,

        "pechera_puesta": pechera,

        "actividad": {
            "estado": actividad,
            "icono": icono
        },

        "diagnostico": diagnostico,

        "acx": acx,

        "acy": acy,

        "acz": acz,

        "ultima_actualizacion":
            estado_telemetria_actual.get(
                "ultima_actualizacion",
                ahora.strftime("%H:%M:%S")
            )
    })


# ==========================================================
# GUARDAR DOSIS
# ==========================================================

@app.route('/api/guardar_dosis', methods=['POST'])
def guardar_dosis():

    global PROXIMO_ID_DOSIS

    data = request.get_json() or {}

    peso = float(
        data.get('peso', 0.0)
    )

    dosis_mg_kg = float(
        data.get('dosis_mg_kg', 0.0)
    )

    concentracion = float(
        data.get('concentracion', 1.0)
    )

    volumen_ml = (
        round(
            (peso * dosis_mg_kg) / concentracion,
            2
        )
        if concentracion > 0
        else 0.0
    )

    nuevo_registro = {

        "id": PROXIMO_ID_DOSIS,

        "fecha":
            datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ),

        "paciente":
            data.get(
                'paciente',
                'Desconocido'
            ),

        "peso": peso,

        "propietario":
            data.get(
                'propietario',
                'N/A'
            ),

        "telefono":
            data.get(
                'telefono',
                'N/A'
            ),

        "correo":
            data.get(
                'correo',
                'N/A'
            ),

        "direccion":
            data.get(
                'direccion',
                'N/A'
            ),

        "farmaco":
            data.get(
                'farmaco',
                'N/A'
            ),

        "dosis_mg_kg":
            dosis_mg_kg,

        "concentracion":
            concentracion,

        "volumen_ml":
            volumen_ml,

        "sugerencias":
            data.get(
                'sugerencias',
                'Sin observaciones.'
            )
    }

    HISTORIAL_DOSIS.append(
        nuevo_registro
    )

    PROXIMO_ID_DOSIS += 1

    return jsonify({
        "status": "success",
        "id": nuevo_registro["id"]
    }), 201


# ==========================================================
# HISTORIAL DE DOSIS
# ==========================================================

@app.route('/api/historial_dosis', methods=['GET'])
def obtener_historial_dosis():

    return jsonify(
        HISTORIAL_DOSIS
    )


# ==========================================================
# ELIMINAR DOSIS
# ==========================================================

@app.route(
    '/api/eliminar_dosis/<int:id_dosis>',
    methods=['DELETE']
)
def eliminar_dosis(id_dosis):

    global HISTORIAL_DOSIS

    HISTORIAL_DOSIS = [
        item
        for item in HISTORIAL_DOSIS
        if item['id'] != id_dosis
    ]

    return jsonify({
        "status": "success",
        "deleted_id": id_dosis
    })


# ==========================================================
# LOGOUT
# ==========================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect(
        url_for('login')
    )


# ==========================================================
# MANIFEST
# ==========================================================

@app.route('/manifest.json')
def serve_manifest():

    return send_from_directory(
        '.',
        'manifest.json'
    )


# ==========================================================
# EJECUCIÓN LOCAL
# ==========================================================

if __name__ == '__main__':

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000
    )
```
