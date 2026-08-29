
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
# CREDENCIALES
# ==========================================================

DATOS_USUARIO = {
    "usuario": "admin",
    "clave": "1234",
    "fecha_cambio": datetime.datetime.now()
}


def requiere_cambio_clave():
    """
    Comprueba si han pasado 30 días desde el último
    cambio de credenciales.
    """

    fecha_cambio = DATOS_USUARIO.get("fecha_cambio")

    if not fecha_cambio:
        return False

    diferencia = datetime.datetime.now() - fecha_cambio

    return diferencia.days >= 30


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

    if temp == 0 and bpm == 0:

        return {
            "salud_mascota": "Sin Conexión de Sensores",
            "badge_class": "bg-secondary",
            "mensaje": (
                "A la espera de datos físicos desde el ESP32."
            )
        }

    elif temp > 39.2 and bpm > 140:

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

    if not DATOS_USUARIO["usuario"]:

        return redirect(
            url_for("cambiar_credenciales")
        )

    if request.method == "POST":

        usuario_ingresado = request.form.get(
            "usuario",
            ""
        ).strip()

        clave_ingresada = request.form.get(
            "clave",
            ""
        ).strip()


        # --------------------------------------------------
        # COMPROBAR CREDENCIALES
        # --------------------------------------------------

        if (
            usuario_ingresado
            == DATOS_USUARIO["usuario"]
            and
            clave_ingresada
            == DATOS_USUARIO["clave"]
        ):

            session["usuario_autenticado"] = True

            session["usuario"] = usuario_ingresado


            # --------------------------------------------------
            # COMPROBAR CAMBIO DE CLAVE
            # --------------------------------------------------

            if requiere_cambio_clave():

                flash(
                    "Han transcurrido 30 días. "
                    "Por seguridad actualice sus datos.",
                    "warning"
                )

                return redirect(
                    url_for("cambiar_credenciales")
                )


            return redirect(
                url_for("panel_medico")
            )


        else:

            flash(
                "Credenciales incorrectas.",
                "danger"
            )


    return render_template(
        "login.html"
    )


# ==========================================================
# PANEL MÉDICO
# ==========================================================

@app.route("/medico")
@login_required
def panel_medico():

    return render_template(
        "medico.html"
    )


# ==========================================================
# PANEL DEL DUEÑO
# ==========================================================

@app.route("/dueno")
@login_required
def panel_dueno():

    return render_template(
        "dueno.html"
    )


# ==========================================================
# CAMBIAR CREDENCIALES
# ==========================================================

@app.route(
    "/cambiar_credenciales",
    methods=["GET", "POST"]
)
@login_required
def cambiar_credenciales():

    global DATOS_USUARIO

    if request.method == "POST":

        usuario_nuevo = request.form.get(
            "usuario",
            ""
        ).strip()

        clave_nueva = request.form.get(
            "clave",
            ""
        ).strip()

        confirmar_clave = request.form.get(
            "confirmar_clave",
            ""
        ).strip()


        # --------------------------------------------------
        # VALIDAR USUARIO
        # --------------------------------------------------

        if not usuario_nuevo:

            flash(
                "Debe ingresar un usuario.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        # --------------------------------------------------
        # VALIDAR CLAVE
        # --------------------------------------------------

        if not clave_nueva:

            flash(
                "Debe ingresar una contraseña.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        if clave_nueva != confirmar_clave:

            flash(
                "Las contraseñas no coinciden.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        # --------------------------------------------------
        # ACTUALIZAR CREDENCIALES
        # --------------------------------------------------

        DATOS_USUARIO["usuario"] = usuario_nuevo

        DATOS_USUARIO["clave"] = clave_nueva

        DATOS_USUARIO["fecha_cambio"] = datetime.datetime.now()


        session["usuario"] = usuario_nuevo


        flash(
            "Credenciales actualizadas correctamente.",
            "success"
        )


        return redirect(
            url_for("panel_medico")
        )


    return render_template(
        "cambiar_credenciales.html"
    )


# ==========================================================
# RECIBIR TELEMETRÍA DEL ESP32
# ==========================================================

@app.route(
    "/api/actualizar_telemetria",
    methods=["POST"]
)
def actualizar_telemetria():

    global estado_telemetria_actual

    try:

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "status": "error",

                "mensaje":
                    "JSON vacío o inválido"

            }), 400


        # --------------------------------------------------
        # TEMPERATURA
        # --------------------------------------------------

        if "temperatura" in data:

            estado_telemetria_actual[
                "temperatura"
            ] = float(
                data["temperatura"]
            )


        # --------------------------------------------------
        # RITMO CARDÍACO
        # --------------------------------------------------

        if "ritmo_cardiaco" in data:

            estado_telemetria_actual[
                "ritmo_cardiaco"
            ] = int(
                float(
                    data["ritmo_cardiaco"]
                )
            )


        # --------------------------------------------------
        # ACELERÓMETRO X
        # --------------------------------------------------

        if "acx" in data:

            estado_telemetria_actual[
                "acx"
            ] = float(
                data["acx"]
            )


        # --------------------------------------------------
        # ACELERÓMETRO Y
        # --------------------------------------------------

        if "acy" in data:

            estado_telemetria_actual[
                "acy"
            ] = float(
                data["acy"]
            )


        # --------------------------------------------------
        # ACELERÓMETRO Z
        # --------------------------------------------------

        if "acz" in data:

            estado_telemetria_actual[
                "acz"
            ] = float(
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


        if actividad_recibida == "En Reposo":

            icono_actividad = "🟢"

        elif actividad_recibida == "En Movimiento":

            icono_actividad = "🟡"

        elif actividad_recibida == "Movimiento Intenso":

            icono_actividad = "🔴"

        else:

            icono_actividad = "⚪"


        estado_telemetria_actual[
            "actividad"
        ] = {

            "estado":
                actividad_recibida,

            "icono":
                icono_actividad
        }


        # --------------------------------------------------
        # PECHERA
        # --------------------------------------------------

        if "pechera_puesta" in data:

            valor_pechera = data[
                "pechera_puesta"
            ]

            if isinstance(
                valor_pechera,
                str
            ):

                valor_pechera = (
                    valor_pechera.lower()
                    in [
                        "true",
                        "1",
                        "si",
                        "sí"
                    ]
                )

            else:

                valor_pechera = bool(
                    valor_pechera
                )

            estado_telemetria_actual[
                "pechera_puesta"
            ] = valor_pechera

        else:

            estado_telemetria_actual[
                "pechera_puesta"
            ] = True


        # --------------------------------------------------
        # CONEXIÓN
        # --------------------------------------------------

        estado_telemetria_actual[
            "conectado"
        ] = True


        estado_telemetria_actual[
            "ultima_actualizacion"
        ] = obtener_hora_ecuador().strftime(
            "%H:%M:%S"
        )


        # --------------------------------------------------
        # CONSOLA
        # --------------------------------------------------

        print("\n================================")
        print("      TELEMETRÍA RECIBIDA")
        print("================================")

        print(
            "Temperatura:",
            estado_telemetria_actual[
                "temperatura"
            ],
            "°C"
        )

        print(
            "Ritmo cardíaco:",
            estado_telemetria_actual[
                "ritmo_cardiaco"
            ],
            "BPM"
        )

        print(
            "Actividad:",
            actividad_recibida
        )

        print(
            "ACX:",
            estado_telemetria_actual[
                "acx"
            ]
        )

        print(
            "ACY:",
            estado_telemetria_actual[
                "acy"
            ]
        )

        print(
            "ACZ:",
            estado_telemetria_actual[
                "acz"
            ]
        )

        print(
            "Pechera:",
            estado_telemetria_actual[
                "pechera_puesta"
            ]
        )

        print(
            "Actualización:",
            estado_telemetria_actual[
                "ultima_actualizacion"
            ]
        )

        print("================================\n")


        return jsonify({

            "status":
                "success",

            "mensaje":
                "Telemetría recibida correctamente",

            "temperatura":
                estado_telemetria_actual[
                    "temperatura"
                ],

            "ritmo_cardiaco":
                estado_telemetria_actual[
                    "ritmo_cardiaco"
                ],

            "actividad":
                estado_telemetria_actual[
                    "actividad"
                ]

        }), 200


    except (ValueError, TypeError) as e:

        print(
            "ERROR EN DATOS:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "mensaje":
                "Los datos recibidos no son válidos.",

            "detalle":
                str(e)

        }), 400


    except Exception as e:

        print(
            "ERROR TELEMETRÍA:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "mensaje":
                "Error interno del servidor.",

            "detalle":
                str(e)

        }), 500


# ==========================================================
# ENVIAR TELEMETRÍA A LA WEB
# ==========================================================

@app.route(
    "/api/telemetria",
    methods=["GET"]
)
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


    diagnostico = evaluar_estado_clinico(

        temperatura,

        ritmo_cardiaco
    )


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

@app.route(
    "/api/guardar_dosis",
    methods=["POST"]
)
@login_required
def guardar_dosis():

    global PROXIMO_ID_DOSIS

    try:

        data = request.get_json(
            silent=True
        ) or {}


        peso = float(
            data.get(
                "peso",
                0.0
            )
        )

        dosis_mg_kg = float(
            data.get(
                "dosis_mg_kg",
                0.0
            )
        )

        concentracion = float(
            data.get(
                "concentracion",
                1.0
            )
        )


        if peso <= 0:

            return jsonify({

                "status":
                    "error",

                "mensaje":
                    "El peso debe ser mayor que 0."

            }), 400


        if dosis_mg_kg <= 0:

            return jsonify({

                "status":
                    "error",

                "mensaje":
                    "La dosis debe ser mayor que 0."

            }), 400


        if concentracion <= 0:

            return jsonify({

                "status":
                    "error",

                "mensaje":
                    "La concentración debe ser mayor que 0."

            }), 400


        volumen_ml = round(

            (
                peso *
                dosis_mg_kg
            )
            /
            concentracion,

            2
        )


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

            "status":
                "success",

            "mensaje":
                "Dosis guardada correctamente.",

            "id":
                nuevo_registro["id"],

            "volumen_ml":
                volumen_ml

        }), 201


    except (ValueError, TypeError) as e:

        return jsonify({

            "status":
                "error",

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

            "status":
                "error",

            "mensaje":
                "Error interno al guardar la dosis.",

            "detalle":
                str(e)

        }), 500


# ==========================================================
# HISTORIAL DE DOSIS
# ==========================================================

@app.route(
    "/api/historial_dosis",
    methods=["GET"]
)
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


    if len(HISTORIAL_DOSIS) < cantidad_antes:

        return jsonify({

            "status":
                "success",

            "mensaje":
                "Registro eliminado correctamente.",

            "deleted_id":
                id_dosis

        }), 200


    return jsonify({

        "status":
            "error",

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
# EJECUTAR FLASK
# ==========================================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="0.0.0.0",

        port=5000
    )

