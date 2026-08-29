
import os
import json
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
# CONFIGURACIÓN
# ==========================================================

app = Flask(__name__)

app.secret_key = "vettag_telemetry_secure_key"

ARCHIVO_CREDENCIALES = "credenciales.json"


# ==========================================================
# CREDENCIALES
# ==========================================================

def cargar_credenciales():

    if not os.path.exists(ARCHIVO_CREDENCIALES):
        return {
            "usuario": "",
            "password": "",
            "fecha_cambio": ""
        }

    try:

        with open(
            ARCHIVO_CREDENCIALES,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(archivo)

        return datos

    except Exception:

        return {
            "usuario": "",
            "password": "",
            "fecha_cambio": ""
        }


def guardar_credenciales(
    usuario,
    password
):

    datos = {

        "usuario": usuario,

        "password": password,

        "fecha_cambio":
            datetime.datetime.now().isoformat()
    }

    with open(
        ARCHIVO_CREDENCIALES,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=4
        )


def requiere_cambio_clave():

    datos = cargar_credenciales()

    fecha = datos.get(
        "fecha_cambio",
        ""
    )

    if not fecha:
        return False

    try:

        fecha_cambio = datetime.datetime.fromisoformat(
            fecha
        )

        diferencia = (
            datetime.datetime.now()
            - fecha_cambio
        )

        return diferencia.days >= 30

    except Exception:

        return False


# ==========================================================
# HISTORIAL DE DOSIS
# ==========================================================

HISTORIAL_DOSIS = []

PROXIMO_ID_DOSIS = 1


# ==========================================================
# ESTADO DE TELEMETRÍA
# ==========================================================

estado_telemetria_actual = {

    "conectado": False,

    "temperatura": 0.0,

    "ritmo_cardiaco": 0,

    "acx": 0.0,

    "acy": 0.0,

    "acz": 0.0,

    "actividad": {
        "estado": "En Espera",
        "icono": "⚪"
    },

    "pechera_puesta": False,

    "ultima_actualizacion": "---"
}


# ==========================================================
# DIAGNÓSTICO
# ==========================================================

def evaluar_estado_clinico(
    temp,
    bpm,
    arnes_puesto
):

    if not arnes_puesto:

        return {
            "salud_mascota":
                "Arnés Desconectado",

            "badge_class":
                "bg-danger",

            "mensaje":
                "El arnés capacitivo no detecta contacto. "
                "Verifique la sujeción del dispositivo."
        }

    if temp > 39.2 and bpm > 140:

        return {
            "salud_mascota":
                "Estado Crítico",

            "badge_class":
                "bg-danger",

            "mensaje":
                "Alerta de hipertermia severa y taquicardia. "
                "Requiere intervención médica inmediata."
        }

    elif temp > 39.2:

        return {
            "salud_mascota":
                "Fiebre Detectada",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Temperatura corporal elevada por encima "
                "del rango normal (37.5°C - 39.2°C)."
        }

    elif 0 < temp < 37.5:

        return {
            "salud_mascota":
                "Hipotermia Detectada",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Temperatura corporal por debajo del límite "
                "seguro. Mantener abrigado."
        }

    elif bpm > 140:

        return {
            "salud_mascota":
                "Taquicardia",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Frecuencia cardíaca acelerada por encima "
                "de los valores basales en reposo."
        }

    elif 0 < bpm < 60:

        return {
            "salud_mascota":
                "Bradicardia",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Frecuencia cardíaca anormalmente baja. "
                "Se sugiere monitoreo del pulso."
        }

    elif temp == 0 and bpm == 0:

        return {
            "salud_mascota":
                "Sin Dispositivo",

            "badge_class":
                "bg-secondary",

            "mensaje":
                "A la espera de la conexión con el ESP32."
        }

    else:

        return {
            "salud_mascota":
                "Estado Normal",

            "badge_class":
                "bg-success",

            "mensaje":
                "Constantes vitales dentro de rangos "
                "fisiológicos estables."
        }


# ==========================================================
# PROTEGER RUTAS
# ==========================================================

def login_required(f):

    @wraps(f)
    def decorated_function(
        *args,
        **kwargs
    ):

        if not session.get(
            "usuario_autenticado"
        ):

            return redirect(
                url_for("login")
            )

        return f(
            *args,
            **kwargs
        )

    return decorated_function


# ==========================================================
# INICIO
# ==========================================================

@app.route("/")
def index():

    datos = cargar_credenciales()

    if not datos.get("usuario"):

        return redirect(
            url_for("login")
        )

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

    datos = cargar_credenciales()


    # ======================================================
    # PRIMER INGRESO: CREAR CREDENCIALES
    # ======================================================

    if not datos.get("usuario"):

        if request.method == "POST":

            accion = request.form.get(
                "accion",
                "registro"
            )

            if accion == "registro":

                usuario = request.form.get(
                    "usuario",
                    ""
                ).strip()

                password = request.form.get(
                    "password",
                    ""
                ).strip()


                if not usuario:

                    flash(
                        "Debe ingresar un usuario.",
                        "danger"
                    )

                    return render_template(
                        "login.html",
                        modo="registro"
                    )


                if not password:

                    flash(
                        "Debe ingresar una contraseña.",
                        "danger"
                    )

                    return render_template(
                        "login.html",
                        modo="registro"
                    )


                guardar_credenciales(
                    usuario,
                    password
                )


                session[
                    "usuario_autenticado"
                ] = True

                session[
                    "usuario"
                ] = usuario


                flash(
                    "Credenciales creadas correctamente.",
                    "success"
                )


                return redirect(
                    url_for(
                        "panel_medico"
                    )
                )


        return render_template(
            "login.html",
            modo="registro"
        )


    # ======================================================
    # LOGIN NORMAL
    # ======================================================

    if request.method == "POST":

        accion = request.form.get(
            "accion",
            "login"
        )


        # --------------------------------------------------
        # ACTUALIZAR CONTRASEÑA
        # --------------------------------------------------

        if accion == "actualizar":

            usuario = request.form.get(
                "usuario",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            ).strip()


            if usuario != datos.get(
                "usuario"
            ):

                flash(
                    "Usuario incorrecto.",
                    "danger"
                )

                return render_template(
                    "login.html",
                    modo="expirado",
                    usuario_expirado=
                        datos.get("usuario", "")
                )


            if not password:

                flash(
                    "Debe ingresar una nueva contraseña.",
                    "danger"
                )

                return render_template(
                    "login.html",
                    modo="expirado",
                    usuario_expirado=
                        datos.get("usuario", "")
                )


            guardar_credenciales(
                usuario,
                password
            )


            session[
                "usuario_autenticado"
            ] = True

            session[
                "usuario"
            ] = usuario


            flash(
                "Contraseña actualizada correctamente.",
                "success"
            )


            return redirect(
                url_for(
                    "panel_medico"
                )
            )


        # --------------------------------------------------
        # LOGIN
        # --------------------------------------------------

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()


        if (
            usuario == datos.get("usuario")
            and
            password == datos.get("password")
        ):

            session[
                "usuario_autenticado"
            ] = True

            session[
                "usuario"
            ] = usuario


            if requiere_cambio_clave():

                return render_template(
                    "login.html",
                    modo="expirado",
                    usuario_expirado=usuario
                )


            return redirect(
                url_for(
                    "panel_medico"
                )
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

    datos = cargar_credenciales()


    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()


        if not usuario:

            usuario = datos.get(
                "usuario"
            )


        if not password:

            flash(
                "Debe ingresar una contraseña.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        guardar_credenciales(
            usuario,
            password
        )


        session[
            "usuario"
        ] = usuario


        flash(
            "Credenciales actualizadas correctamente.",
            "success"
        )


        return redirect(
            url_for(
                "panel_medico"
            )
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

                "status":
                    "error",

                "mensaje":
                    "JSON vacío o inválido"

            }), 400


        if "temperatura" in data:

            estado_telemetria_actual[
                "temperatura"
            ] = float(
                data["temperatura"]
            )


        if "ritmo_cardiaco" in data:

            estado_telemetria_actual[
                "ritmo_cardiaco"
            ] = int(
                float(
                    data["ritmo_cardiaco"]
                )
            )


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

            "estado":
                actividad,

            "icono":
                icono
        }


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


        estado_telemetria_actual[
            "conectado"
        ] = True


        estado_telemetria_actual[
            "ultima_actualizacion"
        ] = obtener_hora_ecuador().strftime(
            "%H:%M:%S"
        )


        print("\n================================")
        print("       TELEMETRÍA RECIBIDA")
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
# ENVIAR TELEMETRÍA
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
                0
            )
        )

        dosis_mg_kg = float(
            data.get(
                "dosis_mg_kg",
                0
            )
        )

        concentracion = float(
            data.get(
                "concentracion",
                0
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


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "mensaje":
                "Error al guardar la dosis.",

            "detalle":
                str(e)

        }), 400


# ==========================================================
# HISTORIAL
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
            "No se encontró el registro."

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
# EJECUTAR
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
