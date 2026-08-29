
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
# DATOS DEL USUARIO
# ==========================================================

DATOS_USUARIO = {
    "usuario": "admin",
    "clave": "1234",
    "fecha_cambio": datetime.datetime.now()
}


# ==========================================================
# COMPROBAR SI LA CONTRASEÑA TIENE MÁS DE 30 DÍAS
# ==========================================================

def requiere_cambio_clave():

    fecha_cambio = DATOS_USUARIO.get("fecha_cambio")

    if not fecha_cambio:
        return False

    diferencia = (
        datetime.datetime.now()
        - fecha_cambio
    )

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
            "mensaje":
                "A la espera de datos físicos desde el ESP32."
        }

    elif temp > 39.2 and bpm > 140:

        return {
            "salud_mascota": "Estado Crítico",
            "badge_class": "bg-danger",
            "mensaje":
                "Alerta de hipertermia severa y taquicardia. "
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
                "seguro. Mantener al paciente abrigado."
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
                "Se sugiere monitoreo del pulso."
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
# AUTENTICACIÓN
# ==========================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("usuario_autenticado"):

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return decorated_function


# ==========================================================
# INICIO
# ==========================================================

@app.route("/")
def inicio():

    return render_template(
        "logotipo.html"
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    # ------------------------------------------------------
    # SI NO EXISTE USUARIO
    # ------------------------------------------------------

    if not DATOS_USUARIO.get("usuario"):

        return render_template(
            "login.html",
            modo="registro"
        )


    # ------------------------------------------------------
    # PROCESAR LOGIN
    # ------------------------------------------------------

    if request.method == "POST":

        accion = request.form.get(
            "accion",
            "login"
        )

        usuario_ingresado = request.form.get(
            "usuario",
            ""
        ).strip()

        # IMPORTANTE:
        # Tu login.html utiliza name="password"
        password_ingresada = request.form.get(
            "password",
            ""
        ).strip()


        # --------------------------------------------------
        # LOGIN NORMAL
        # --------------------------------------------------

        if accion == "login":

            if (
                usuario_ingresado
                == DATOS_USUARIO.get("usuario")
                and
                password_ingresada
                == DATOS_USUARIO.get("clave")
            ):

                session["usuario_autenticado"] = True

                session["usuario"] = (
                    usuario_ingresado
                )


                # ------------------------------------------
                # COMPROBAR CONTRASEÑA
                # ------------------------------------------

                if requiere_cambio_clave():

                    flash(
                        "Han transcurrido 30 días. "
                        "Por seguridad actualice sus datos.",
                        "warning"
                    )

                    return redirect(
                        url_for(
                            "cambiar_credenciales"
                        )
                    )


                return redirect(
                    url_for(
                        "panel_medico"
                    )
                )


            else:

                flash(
                    "Credenciales incorrectas.",
                    "danger"
                )


    # ------------------------------------------------------
    # MOSTRAR LOGIN
    # ------------------------------------------------------

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

        password_nueva = request.form.get(
            "password",
            ""
        ).strip()

        confirmar_password = request.form.get(
            "confirmar_password",
            ""
        ).strip()


        # --------------------------------------------------
        # SI TU HTML UTILIZA OTROS NOMBRES
        # --------------------------------------------------

        if not password_nueva:

            password_nueva = request.form.get(
                "clave",
                ""
            ).strip()

        if not confirmar_password:

            confirmar_password = request.form.get(
                "confirmar_clave",
                ""
            ).strip()


        # --------------------------------------------------
        # VALIDAR USUARIO
        # --------------------------------------------------

        if not usuario_nuevo:

            usuario_nuevo = DATOS_USUARIO[
                "usuario"
            ]


        # --------------------------------------------------
        # VALIDAR CONTRASEÑA
        # --------------------------------------------------

        if not password_nueva:

            flash(
                "Debe ingresar una contraseña.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        if (
            confirmar_password
            and
            password_nueva != confirmar_password
        ):

            flash(
                "Las contraseñas no coinciden.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        # --------------------------------------------------
        # GUARDAR NUEVAS CREDENCIALES
        # --------------------------------------------------

        DATOS_USUARIO["usuario"] = (
            usuario_nuevo
        )

        DATOS_USUARIO["clave"] = (
            password_nueva
        )

        DATOS_USUARIO["fecha_cambio"] = (
            datetime.datetime.now()
        )


        session["usuario"] = (
            usuario_nuevo
        )

        session["usuario_autenticado"] = True


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


        # --------------------------------------------------
        # MOSTRAR EN CONSOLA
        # --------------------------------------------------

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
            "Hora:",
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
            "ERROR EN LOS DATOS:",
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
# ENVIAR TELEMETRÍA A LA APLICACIÓN
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
            "estado":
                "En espera de sensor",

            "icono":
                "⏳"
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

    ultima_actualizacion = (
        estado_telemetria_actual.get(
            "ultima_actualizacion",
            "---"
        )
    )


    # ------------------------------------------------------
    # DIAGNÓSTICO
    # ------------------------------------------------------

    diagnostico = evaluar_estado_clinico(

        temperatura,

        ritmo_cardiaco
    )


    # ------------------------------------------------------
    # RESPUESTA
    # ------------------------------------------------------

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


        # --------------------------------------------------
        # CÁLCULO DEL VOLUMEN
        # --------------------------------------------------

        volumen_ml = round(

            (
                peso *
                dosis_mg_kg
            )
            /
            concentracion,

            2
        )


        # --------------------------------------------------
        # REGISTRO
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
                "Error interno del servidor.",

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
# HORA DE ECUADOR
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

