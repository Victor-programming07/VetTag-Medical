
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
    flash
)


# ==========================================================
# CONFIGURACIÓN FLASK
# ==========================================================

app = Flask(__name__)

app.secret_key = "vettag_telemetry_secure_key"


# ==========================================================
# CREDENCIALES DEL SISTEMA
# ==========================================================

USUARIO = "admin"
CONTRASENA = "1234"


# ==========================================================
# HISTORIAL DE PRESCRIPCIONES
# ==========================================================

HISTORIAL_DOSIS = []

PROXIMO_ID_DOSIS = 1


# ==========================================================
# ESTADO ACTUAL DE TELEMETRÍA
# ==========================================================

estado_telemetria_actual = {

    "conectado": False,

    "temperatura": 0.0,

    "ritmo_cardiaco": 0,

    "acx": 0.0,

    "acy": 0.0,

    "acz": 0.0,

    "pechera_puesta": False,

    "actividad": {
        "estado": "En Espera",
        "icono": "⚪"
    },

    "ultima_actualizacion": "---"
}


# ==========================================================
# DIAGNÓSTICO CLÍNICO
# ==========================================================

def evaluar_estado_clinico(
    temp,
    bpm,
    arnes_puesto
):

    if not arnes_puesto:

        return {
            "salud_mascota": "Arnés Desconectado",
            "badge_class": "bg-danger",
            "mensaje":
                "El arnés capacitivo no detecta contacto. "
                "Verifique la sujeción del dispositivo."
        }


    if temp > 39.2 and bpm > 140:

        return {
            "salud_mascota": "Estado Crítico",
            "badge_class": "bg-danger",
            "mensaje":
                "Alerta de Hipertermia severa y Taquicardia. "
                "Requiere intervención médica inmediata."
        }


    elif temp > 39.2:

        return {
            "salud_mascota": "Fiebre Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje":
                "Temperatura corporal elevada por encima "
                "del rango normal (37.5°C - 39.2°C)."
        }


    elif 0 < temp < 37.5:

        return {
            "salud_mascota": "Hipotermia Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje":
                "Temperatura corporal por debajo del límite "
                "seguro. Mantener abrigado."
        }


    elif bpm > 140:

        return {
            "salud_mascota": "Taquicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje":
                "Frecuencia cardíaca acelerada por encima "
                "de los valores basales en reposo."
        }


    elif 0 < bpm < 60:

        return {
            "salud_mascota": "Bradicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje":
                "Frecuencia cardíaca anormalmente baja. "
                "Se sugiere monitoreo de pulso."
        }


    elif temp == 0 and bpm == 0:

        return {
            "salud_mascota": "Sin Dispositivo",
            "badge_class": "bg-secondary",
            "mensaje":
                "A la espera de la conexión con el "
                "microcontrolador ESP32."
        }


    else:

        return {
            "salud_mascota": "Estado Normal",
            "badge_class": "bg-success",
            "mensaje":
                "Constantes vitales dentro de rangos "
                "fisiológicos estables."
        }


# ==========================================================
# PROTEGER RUTAS
# ==========================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get(
            "usuario_autenticado"
        ):

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return decorated_function


# ==========================================================
# INICIO
# ==========================================================

@app.route("/")
def index():

    return redirect(
        url_for("login")
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        usuario_ingresado = request.form.get(
            "usuario",
            ""
        ).strip()

        contrasena_ingresada = request.form.get(
            "password",
            ""
        ).strip()


        # ==================================================
        # COMPROBAR CREDENCIALES
        # ==================================================

        if (
            usuario_ingresado == USUARIO
            and
            contrasena_ingresada == CONTRASENA
        ):

            session["usuario_autenticado"] = True

            session["usuario"] = (
                usuario_ingresado
            )


            print(
                "LOGIN CORRECTO:",
                usuario_ingresado
            )


            # IMPORTANTE:
            # El sistema entra directamente al médico.

            return redirect(
                url_for("panel_medico")
            )


        else:

            print(
                "LOGIN INCORRECTO:",
                usuario_ingresado
            )

            flash(
                "Credenciales incorrectas.",
                "danger"
            )


    return render_template(
        "login.html",
        modo="login"
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
# CAMBIAR CREDENCIALES
# ==========================================================

@app.route(
    "/cambiar_credenciales",
    methods=["GET", "POST"]
)
@login_required
def cambiar_credenciales():

    global USUARIO
    global CONTRASENA


    if request.method == "POST":

        nuevo_usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        nueva_password = request.form.get(
            "password",
            ""
        ).strip()


        if nuevo_usuario:

            USUARIO = nuevo_usuario


        if nueva_password:

            CONTRASENA = nueva_password


        flash(
            "Credenciales actualizadas exitosamente.",
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
        # ACELERÓMETRO
        # --------------------------------------------------

        if "acx" in data:

            estado_telemetria_actual[
                "acx"
            ] = float(
                data["acx"]
            )


        if "acy" in data:

            estado_telemetria_actual[
                "acy"
            ] = float(
                data["acy"]
            )


        if "acz" in data:

            estado_telemetria_actual[
                "acz"
            ] = float(
                data["acz"]
            )


        # --------------------------------------------------
        # ACTIVIDAD
        # --------------------------------------------------

        actividad = str(
            data.get(
                "actividad",
                "En Reposo"
            )
        )


        if actividad == "En Reposo":

            icono = "🟢"

        elif actividad == "En Movimiento":

            icono = "🟡"

        elif actividad == "Movimiento Intenso":

            icono = "🔴"

        else:

            icono = "⚪"


        estado_telemetria_actual[
            "actividad"
        ] = {

            "estado": actividad,

            "icono": icono
        }


        # --------------------------------------------------
        # PECHERA
        # --------------------------------------------------

        if "pechera_puesta" in data:

            valor = data[
                "pechera_puesta"
            ]

            if isinstance(
                valor,
                str
            ):

                valor = (
                    valor.lower()
                    in [
                        "true",
                        "1",
                        "si",
                        "sí"
                    ]
                )

            else:

                valor = bool(valor)


            estado_telemetria_actual[
                "pechera_puesta"
            ] = valor


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
            "Ritmo:",
            estado_telemetria_actual[
                "ritmo_cardiaco"
            ],
            "BPM"
        )

        print(
            "Actividad:",
            actividad
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

        print("================================\n")


        return jsonify({

            "status":
                "success",

            "mensaje":
                "Telemetría recibida correctamente"

        }), 200


    except Exception as e:

        print(
            "ERROR TELEMETRÍA:",
            str(e)
        )


        return jsonify({

            "status":
                "error",

            "mensaje":
                str(e)

        }), 500


# ==========================================================
# ENVIAR TELEMETRÍA A MEDICO.HTML
# ==========================================================

@app.route(
    "/api/telemetria",
    methods=["GET"]
)
@login_required
def api_telemetria():

    temperatura = estado_telemetria_actual[
        "temperatura"
    ]

    bpm = estado_telemetria_actual[
        "ritmo_cardiaco"
    ]

    arnes = estado_telemetria_actual[
        "pechera_puesta"
    ]


    diagnostico = evaluar_estado_clinico(
        temperatura,
        bpm,
        arnes
    )


    return jsonify({

        "conectado":
            estado_telemetria_actual[
                "conectado"
            ],

        "temperatura":
            temperatura,

        "ritmo_cardiaco":
            bpm,

        "pechera_puesta":
            arnes,

        "actividad":
            estado_telemetria_actual[
                "actividad"
            ],

        "ultima_actualizacion":
            estado_telemetria_actual[
                "ultima_actualizacion"
            ],

        "acx":
            estado_telemetria_actual[
                "acx"
            ],

        "acy":
            estado_telemetria_actual[
                "acy"
            ],

        "acz":
            estado_telemetria_actual[
                "acz"
            ],

        "diagnostico":
            diagnostico,

        "gps": {

            "valido": False,

            "latitud": -1.3458,

            "longitud": -80.4285
        }

    })


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
