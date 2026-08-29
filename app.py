

import datetime
from datetime import timezone, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory
)


# ==========================================================
# CONFIGURACIÓN FLASK
# ==========================================================

app = Flask(__name__)

app.secret_key = "vettag_telemetry_secure_key"


# ==========================================================
# HISTORIAL DE DOSIS
# ==========================================================

HISTORIAL_DOSIS = []
PROXIMO_ID_DOSIS = 1


# ==========================================================
# ESTADO ACTUAL DE TELEMETRÍA
# ==========================================================

estado_telemetria_actual = {

    "ritmo_cardiaco": 0,

    "temperatura": 0.0,

    "acx": 0.0,

    "acy": 0.0,

    "acz": 0.0,

    "actividad": {
        "estado": "En espera de sensor",
        "icono": "⏳"
    },

    "pechera_puesta": False,

    "conectado": False,

    "ultima_actualizacion": "---"
}


# ==========================================================
# DIAGNÓSTICO CLÍNICO
# ==========================================================

def evaluar_estado_clinico(temp, bpm):

    if temp > 39.2 and bpm > 140:

        return {
            "salud_mascota": "Estado Crítico",
            "badge_class": "bg-danger",
            "mensaje": (
                "Alerta de hipertermia severa y taquicardia. "
                "Requiere intervención médica inmediata."
            )
        }

    elif temp > 39.2:

        return {
            "salud_mascota": "Fiebre Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": (
                "Temperatura corporal elevada por encima "
                "del rango normal (37.5°C - 39.2°C)."
            )
        }

    elif 0 < temp < 37.5:

        return {
            "salud_mascota": "Hipotermia Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": (
                "Temperatura corporal por debajo del límite "
                "seguro. Mantener al paciente abrigado."
            )
        }

    elif bpm > 140:

        return {
            "salud_mascota": "Taquicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": (
                "Frecuencia cardíaca acelerada por encima "
                "de los valores basales en reposo."
            )
        }

    elif 0 < bpm < 60:

        return {
            "salud_mascota": "Bradicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": (
                "Frecuencia cardíaca anormalmente baja. "
                "Se sugiere monitoreo del pulso."
            )
        }

    elif temp == 0 and bpm == 0:

        return {
            "salud_mascota": "Sin Conexión de Sensores",
            "badge_class": "bg-secondary",
            "mensaje": (
                "A la espera de datos físicos desde el ESP32."
            )
        }

    else:

        return {
            "salud_mascota": "Estado Normal",
            "badge_class": "bg-success",
            "mensaje": (
                "Constantes vitales dentro de rangos "
                "fisiológicos estables."
            )
        }


# ==========================================================
# AUTENTICACIÓN
# ==========================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("usuario_autenticado"):

            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


# ==========================================================
# PÁGINA DE INICIO
# ==========================================================

@app.route("/")
def inicio():

    return render_template("logotipo.html")


# ==========================================================
# LOGIN
# ==========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        # --------------------------------------------------
        # AUTENTICACIÓN SIMPLE
        # --------------------------------------------------

        session["usuario_autenticado"] = True

        return redirect(url_for("panel_medico"))

    return render_template("login.html")


# ==========================================================
# PANEL DEL DUEÑO
# ==========================================================

@app.route("/dueno")
@login_required
def panel_dueno():

    return render_template("dueno.html")


# ==========================================================
# PANEL DEL MÉDICO
# ==========================================================

@app.route("/medico")
@login_required
def panel_medico():

    return render_template("medico.html")


# ==========================================================
# CAMBIAR CREDENCIALES
# ==========================================================

@app.route("/cambiar_credenciales", methods=["GET", "POST"])
@login_required
def cambiar_credenciales():

    if request.method == "POST":

        flash(
            "Credenciales actualizadas correctamente.",
            "success"
        )

        return redirect(url_for("panel_medico"))

    return render_template("cambiar_credenciales.html")


# ==========================================================
# RECIBIR TELEMETRÍA DEL ESP32
# ==========================================================

@app.route("/api/actualizar_telemetria", methods=["POST"])
def actualizar_telemetria():

    global estado_telemetria_actual

    try:

        data = request.get_json(silent=True)

        if not data:

            return jsonify({
                "status": "error",
                "mensaje": "JSON vacío o inválido"
            }), 400


        # --------------------------------------------------
        # TEMPERATURA
        # --------------------------------------------------

        if "temperatura" in data:

            estado_telemetria_actual["temperatura"] = float(
                data["temperatura"]
            )


        # --------------------------------------------------
        # RITMO CARDIACO
        # --------------------------------------------------

        if "ritmo_cardiaco" in data:

            estado_telemetria_actual["ritmo_cardiaco"] = int(
                float(data["ritmo_cardiaco"])
            )


        # --------------------------------------------------
        # ACELERÓMETRO X
        # --------------------------------------------------

        if "acx" in data:

            estado_telemetria_actual["acx"] = float(
                data["acx"]
            )


        # --------------------------------------------------
        # ACELERÓMETRO Y
        # --------------------------------------------------

        if "acy" in data:

            estado_telemetria_actual["acy"] = float(
                data["acy"]
            )


        # --------------------------------------------------
        # ACELERÓMETRO Z
        # --------------------------------------------------

        if "acz" in data:

            estado_telemetria_actual["acz"] = float(
                data["acz"]
            )


        # --------------------------------------------------
        # ACTIVIDAD
        # --------------------------------------------------

        actividad_recibida = str(
            data.get(
                "actividad",
                "En Reposo"
            )
        )


        # --------------------------------------------------
        # ICONO DE ACTIVIDAD
        # --------------------------------------------------

        if actividad_recibida == "En Reposo":

            icono_actividad = "🟢"

        elif actividad_recibida == "En Movimiento":

            icono_actividad = "🟡"

        elif actividad_recibida == "Movimiento Intenso":

            icono_actividad = "🔴"

        else:

            icono_actividad = "⚪"


        # --------------------------------------------------
        # GUARDAR ACTIVIDAD
        # --------------------------------------------------

        estado_telemetria_actual["actividad"] = {

            "estado": actividad_recibida,

            "icono": icono_actividad
        }


        # --------------------------------------------------
        # PECHERA
        # --------------------------------------------------

        if "pechera_puesta" in data:

            estado_telemetria_actual["pechera_puesta"] = bool(
                data["pechera_puesta"]
            )

        else:

            estado_telemetria_actual["pechera_puesta"] = True


        # --------------------------------------------------
        # ESTADO DE CONEXIÓN
        # --------------------------------------------------

        estado_telemetria_actual["conectado"] = True

        estado_telemetria_actual[
            "ultima_actualizacion"
        ] = obtener_hora_ecuador().strftime("%H:%M:%S")


        # --------------------------------------------------
        # MOSTRAR TELEMETRÍA EN CONSOLA
        # --------------------------------------------------

        print("\n================================")
        print("      TELEMETRÍA RECIBIDA")
        print("================================")

        print(
            "Temperatura:",
            estado_telemetria_actual["temperatura"],
            "°C"
        )

        print(
            "Ritmo cardíaco:",
            estado_telemetria_actual["ritmo_cardiaco"],
            "BPM"
        )

        print(
            "Actividad:",
            actividad_recibida
        )

        print(
            "ACX:",
            estado_telemetria_actual["acx"]
        )

        print(
            "ACY:",
            estado_telemetria_actual["acy"]
        )

        print(
            "ACZ:",
            estado_telemetria_actual["acz"]
        )

        print(
            "Pechera:",
            estado_telemetria_actual["pechera_puesta"]
        )

        print(
            "Actualización:",
            estado_telemetria_actual[
                "ultima_actualizacion"
            ]
        )

        print("================================\n")


        # --------------------------------------------------
        # RESPUESTA AL ESP32
        # --------------------------------------------------

        return jsonify({

            "status": "success",

            "mensaje":
                "Telemetría recibida correctamente",

            "temperatura":
                estado_telemetria_actual["temperatura"],

            "ritmo_cardiaco":
                estado_telemetria_actual["ritmo_cardiaco"],

            "actividad":
                estado_telemetria_actual["actividad"]

        }), 200


    except (ValueError, TypeError) as e:

        print(
            "ERROR EN LOS DATOS RECIBIDOS:",
            str(e)
        )

        return jsonify({

            "status": "error",

            "mensaje":
                "Los datos enviados tienen un formato incorrecto.",

            "detalle":
                str(e)

        }), 400


    except Exception as e:

        print(
            "ERROR TELEMETRÍA:",
            str(e)
        )

        return jsonify({

            "status": "error",

            "mensaje":
                "Error interno del servidor.",

            "detalle":
                str(e)

        }), 500


# ==========================================================
# ENVIAR TELEMETRÍA A LA APLICACIÓN WEB
# ==========================================================

@app.route("/api/telemetria", methods=["GET"])
@login_required
def api_telemetria():

    temperatura = estado_telemetria_actual.get(
        "temperatura",
        0.0
    )

    ritmo_cardiaco = estado_telemetria_actual.get(
        "ritmo_cardiaco",
        0
    )

    actividad = estado_telemetria_actual.get(

        "actividad",

        {
            "estado": "En espera de sensor",
            "icono": "⏳"
        }
    )

    pechera = estado_telemetria_actual.get(
        "pechera_puesta",
        False
    )

    conectado = estado_telemetria_actual.get(
        "conectado",
        False
    )

    ultima_actualizacion = estado_telemetria_actual.get(
        "ultima_actualizacion",
        "---"
    )


    # --------------------------------------------------
    # DIAGNÓSTICO
    # --------------------------------------------------

    diagnostico = evaluar_estado_clinico(

        temperatura,

        ritmo_cardiaco
    )


    # --------------------------------------------------
    # RESPUESTA JSON
    # --------------------------------------------------

    return jsonify({

        "temperatura":
            temperatura,

        "ritmo_cardiaco":
            ritmo_cardiaco,

        "pechera_puesta":
            pechera,

        "actividad":
            actividad,

        "diagnostico":
            diagnostico,

        "conectado":
            conectado,

        "ultima_actualizacion":
            ultima_actualizacion,

        "acx":
            estado_telemetria_actual.get(
                "acx",
                0.0
            ),

        "acy":
            estado_telemetria_actual.get(
                "acy",
                0.0
            ),

        "acz":
            estado_telemetria_actual.get(
                "acz",
                0.0
            )
    })


# ==========================================================
# GUARDAR DOSIS
# ==========================================================

@app.route("/api/guardar_dosis", methods=["POST"])
@login_required
def guardar_dosis():

    global PROXIMO_ID_DOSIS

    try:

        data = request.get_json(silent=True) or {}


        peso = float(
            data.get("peso", 0.0)
        )

        dosis_mg_kg = float(
            data.get("dosis_mg_kg", 0.0)
        )

        concentracion = float(
            data.get("concentracion", 1.0)
        )


        # --------------------------------------------------
        # VALIDACIONES
        # --------------------------------------------------

        if peso <= 0:

            return jsonify({
                "status": "error",
                "mensaje": "El peso debe ser mayor que 0."
            }), 400


        if dosis_mg_kg <= 0:

            return jsonify({
                "status": "error",
                "mensaje": "La dosis debe ser mayor que 0."
            }), 400


        if concentracion <= 0:

            return jsonify({
                "status": "error",
                "mensaje":
                    "La concentración debe ser mayor que 0."
            }), 400


        # --------------------------------------------------
        # CÁLCULO
        # --------------------------------------------------

        volumen_ml = round(

            (
                peso *
                dosis_mg_kg
            ) /
            concentracion,

            2
        )


        # --------------------------------------------------
        # NUEVO REGISTRO
        # --------------------------------------------------

        nuevo_registro = {

            "id":
                PROXIMO_ID_DOSIS,

            "fecha":
                obtener_hora_ecuador().strftime(
                    "%Y-%m-%d %H:%M"
                ),

            "paciente":
                data.get(
                    "paciente",
                    "Desconocido"
                ),

            "peso":
                peso,

            "propietario":
                data.get(
                    "propietario",
                    "N/A"
                ),

            "telefono":
                data.get(
                    "telefono",
                    "N/A"
                ),

            "correo":
                data.get(
                    "correo",
                    "N/A"
                ),

            "direccion":
                data.get(
                    "direccion",
                    "N/A"
                ),

            "farmaco":
                data.get(
                    "farmaco",
                    "N/A"
                ),

            "dosis_mg_kg":
                dosis_mg_kg,

            "concentracion":
                concentracion,

            "volumen_ml":
                volumen_ml,

            "sugerencias":
                data.get(
                    "sugerencias",
                    "Sin observaciones."
                )
        }


        HISTORIAL_DOSIS.append(
            nuevo_registro
        )

        PROXIMO_ID_DOSIS += 1


        return jsonify({

            "status": "success",

            "mensaje":
                "Dosis guardada correctamente.",

            "id":
                nuevo_registro["id"],

            "volumen_ml":
                volumen_ml

        }), 201


    except (ValueError, TypeError) as e:

        return jsonify({

            "status": "error",

            "mensaje":
                "Los datos de la dosis no son válidos.",

            "detalle":
                str(e)

        }), 400


    except Exception as e:

        print(
            "ERROR GUARDANDO DOSIS:",
            str(e)
        )

        return jsonify({

            "status": "error",

            "mensaje":
                "Error interno al guardar la dosis.",

            "detalle":
                str(e)

        }), 500


# ==========================================================
# OBTENER HISTORIAL DE DOSIS
# ==========================================================

@app.route("/api/historial_dosis", methods=["GET"])
@login_required
def obtener_historial_dosis():

    return jsonify(
        HISTORIAL_DOSIS
    )


# ==========================================================
# ELIMINAR DOSIS
# ==========================================================

@app.route(
    "/api/eliminar_dosis/<int:id_dosis>",
    methods=["DELETE"]
)
@login_required
def eliminar_dosis(id_dosis):

    global HISTORIAL_DOSIS

    cantidad_antes = len(
        HISTORIAL_DOSIS
    )


    HISTORIAL_DOSIS = [

        item

        for item in HISTORIAL_DOSIS

        if item["id"] != id_dosis
    ]


    eliminado = (
        len(HISTORIAL_DOSIS)
        < cantidad_antes
    )


    if eliminado:

        return jsonify({

            "status": "success",

            "mensaje":
                "Registro eliminado correctamente.",

            "deleted_id":
                id_dosis

        }), 200


    return jsonify({

        "status": "error",

        "mensaje":
            "No se encontró el registro.",

        "deleted_id":
            id_dosis

    }), 404


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==========================================================
# MANIFEST
# ==========================================================

@app.route("/manifest.json")
def serve_manifest():

    return send_from_directory(
        ".",
        "manifest.json"
    )


# ==========================================================
# HORA ECUADOR
# ==========================================================

def obtener_hora_ecuador():

    zona_ecuador = timezone(
        timedelta(hours=-5)
    )

    return datetime.datetime.now(
        zona_ecuador
    )


# ==========================================================
# EJECUTAR APLICACIÓN
# ==========================================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="0.0.0.0",

        port=5000
    )


