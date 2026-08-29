
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime
import sqlite3
import os

# =========================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# =========================================================

app = Flask(__name__)

app.secret_key = "vetetech_telemetry_secure_key_2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "vettag.db")


# =========================================================
# CONEXIÓN A BASE DE DATOS
# =========================================================

def conectar_db():
    conexion = sqlite3.connect(DATABASE)
    conexion.row_factory = sqlite3.Row
    return conexion


# =========================================================
# INICIALIZACIÓN DE BASE DE DATOS
# =========================================================

def inicializar_db():

    conexion = conectar_db()
    cursor = conexion.cursor()

    # -----------------------------------------------------
    # TABLA DE USUARIOS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # TABLA DE MASCOTAS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mascotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            especie TEXT DEFAULT 'Perro',
            raza TEXT DEFAULT '',
            edad TEXT DEFAULT '',
            propietario TEXT DEFAULT ''
        )
    """)

    conexion.commit()
    conexion.close()


# =========================================================
# ESTADO ACTUAL DE TELEMETRÍA
# =========================================================

estado_telemetria_actual = {

    "ritmo_cardiaco": 0,

    "temperatura": 38.0,

    "acx": 0.0,

    "acy": 0.0,

    "acz": 0.0,

    "actividad": {
        "estado": "En espera de sensor",
        "icono": "⏳"
    },

    "pechera_puesta": False,

    "gps": {
        "latitud": 0.0,
        "longitud": 0.0
    },

    "ultima_actualizacion": None
}


# =========================================================
# DETERMINAR ACTIVIDAD
# =========================================================

def determinar_actividad(acx, acy, acz):

    try:

        movimiento = (
            abs(float(acx)) +
            abs(float(acy)) +
            abs(float(acz))
        )

        if movimiento < 1.5:

            return {
                "estado": "En reposo",
                "icono": "😴"
            }

        elif movimiento < 4:

            return {
                "estado": "Actividad ligera",
                "icono": "🐕"
            }

        elif movimiento < 8:

            return {
                "estado": "Actividad moderada",
                "icono": "🏃"
            }

        else:

            return {
                "estado": "Actividad intensa",
                "icono": "⚡"
            }

    except Exception:

        return {
            "estado": "Sensor no disponible",
            "icono": "⚠️"
        }


# =========================================================
# INICIO
# =========================================================

@app.route("/", methods=["GET"])
def inicio():

    if "usuario" in session:

        if session.get("rol") == "dueno":

            return redirect(url_for("dueno"))

    return redirect(url_for("login"))


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "").strip()

        conexion = conectar_db()

        try:

            user = conexion.execute("""
                SELECT *
                FROM usuarios
                WHERE usuario = ?
                AND password = ?
            """, (
                usuario,
                password
            )).fetchone()

        finally:

            conexion.close()

        if user:

            # -------------------------------------------------
            # MANTENER SESIÓN DEL USUARIO
            # -------------------------------------------------

            session["usuario"] = user["usuario"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]

            # -------------------------------------------------
            # ACCESO DEL DUEÑO
            # -------------------------------------------------

            if user["rol"] == "dueno":

                return redirect(url_for("dueno"))

            flash(
                "Este usuario no pertenece a la aplicación del dueño."
            )

        else:

            flash("Credenciales incorrectas.")

    return render_template("login.html")


# =========================================================
# DASHBOARD DEL DUEÑO
# =========================================================

@app.route("/dueno")
def dueno():

    # -----------------------------------------------------
    # VERIFICAR SESIÓN
    # -----------------------------------------------------

    if "usuario" not in session:

        return redirect(url_for("login"))

    # -----------------------------------------------------
    # VERIFICAR ROL
    # -----------------------------------------------------

    if session.get("rol") != "dueno":

        flash(
            "No tienes permiso para acceder a esta sección."
        )

        return redirect(url_for("login"))

    # -----------------------------------------------------
    # CONECTAR BASE DE DATOS
    # -----------------------------------------------------

    conexion = conectar_db()

    try:

        mascotas = conexion.execute("""
            SELECT *
            FROM mascotas
            WHERE propietario = ?
            OR propietario = ?
        """, (
            session.get("nombre"),
            ""
        )).fetchall()

    finally:

        conexion.close()

    # -----------------------------------------------------
    # CARGAR DUENO.HTML
    # -----------------------------------------------------
    #
    # IMPORTANTE:
    # NO se carga medico.html.
    #
    # -----------------------------------------------------

    return render_template(
        "dueno.html",
        nombre=session.get("nombre"),
        mascotas=mascotas,
        telemetria=estado_telemetria_actual
    )


# =========================================================
# API - OBTENER TELEMETRÍA
# =========================================================

@app.route("/api/telemetria", methods=["GET"])
def obtener_telemetria():

    return jsonify({

        "ok": True,

        "telemetria": estado_telemetria_actual

    })


# =========================================================
# API - RECIBIR TELEMETRÍA
# =========================================================

@app.route("/api/actualizar_telemetria", methods=["POST"])
def actualizar_telemetria():

    global estado_telemetria_actual

    try:

        datos = request.get_json(silent=True)

        if not datos:

            return jsonify({

                "ok": False,

                "error": "No se recibieron datos"

            }), 400

        # -------------------------------------------------
        # RITMO CARDIACO
        # -------------------------------------------------

        if "ritmo_cardiaco" in datos:

            estado_telemetria_actual[
                "ritmo_cardiaco"
            ] = float(
                datos["ritmo_cardiaco"]
            )

        elif "bpm" in datos:

            estado_telemetria_actual[
                "ritmo_cardiaco"
            ] = float(
                datos["bpm"]
            )

        # -------------------------------------------------
        # TEMPERATURA
        # -------------------------------------------------

        if "temperatura" in datos:

            estado_telemetria_actual[
                "temperatura"
            ] = float(
                datos["temperatura"]
            )

        elif "temperature" in datos:

            estado_telemetria_actual[
                "temperatura"
            ] = float(
                datos["temperature"]
            )

        # -------------------------------------------------
        # MPU6050
        # -------------------------------------------------

        if "acx" in datos:

            estado_telemetria_actual["acx"] = float(
                datos["acx"]
            )

        if "acy" in datos:

            estado_telemetria_actual["acy"] = float(
                datos["acy"]
            )

        if "acz" in datos:

            estado_telemetria_actual["acz"] = float(
                datos["acz"]
            )

        # -------------------------------------------------
        # ACTIVIDAD
        # -------------------------------------------------

        estado_telemetria_actual["actividad"] = (
            determinar_actividad(
                estado_telemetria_actual["acx"],
                estado_telemetria_actual["acy"],
                estado_telemetria_actual["acz"]
            )
        )

        # -------------------------------------------------
        # PECHERA
        # -------------------------------------------------

        if "pechera_puesta" in datos:

            valor = datos["pechera_puesta"]

            if isinstance(valor, bool):

                estado_telemetria_actual[
                    "pechera_puesta"
                ] = valor

            else:

                estado_telemetria_actual[
                    "pechera_puesta"
                ] = str(valor).lower() in [
                    "true",
                    "1",
                    "si",
                    "sí",
                    "puesta"
                ]

        elif "pechera" in datos:

            valor = datos["pechera"]

            estado_telemetria_actual[
                "pechera_puesta"
            ] = str(valor).lower() in [
                "true",
                "1",
                "si",
                "sí",
                "puesta"
            ]

        # -------------------------------------------------
        # GPS
        # -------------------------------------------------

        if "latitud" in datos:

            estado_telemetria_actual[
                "gps"
            ]["latitud"] = float(
                datos["latitud"]
            )

        elif "latitude" in datos:

            estado_telemetria_actual[
                "gps"
            ]["latitud"] = float(
                datos["latitude"]
            )

        if "longitud" in datos:

            estado_telemetria_actual[
                "gps"
            ]["longitud"] = float(
                datos["longitud"]
            )

        elif "longitude" in datos:

            estado_telemetria_actual[
                "gps"
            ]["longitud"] = float(
                datos["longitude"]
            )

        # -------------------------------------------------
        # FECHA Y HORA
        # -------------------------------------------------

        estado_telemetria_actual[
            "ultima_actualizacion"
        ] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # -------------------------------------------------
        # RESPUESTA
        # -------------------------------------------------

        return jsonify({

            "ok": True,

            "mensaje": "Telemetría actualizada correctamente",

            "telemetria": estado_telemetria_actual

        })

    except ValueError as e:

        return jsonify({

            "ok": False,

            "error": "Dato numérico inválido",

            "detalle": str(e)

        }), 400

    except Exception as e:

        return jsonify({

            "ok": False,

            "error": "Error al actualizar telemetría",

            "detalle": str(e)

        }), 500


# =========================================================
# API ESP32
# =========================================================

@app.route("/api/esp32", methods=["POST"])
def recibir_esp32():

    return actualizar_telemetria()


# =========================================================
# ESTADO DEL SERVIDOR
# =========================================================

@app.route("/api/estado", methods=["GET"])
def estado():

    return jsonify({

        "servidor": "VETTAG",

        "estado": "online",

        "rol": session.get("rol"),

        "telemetria": estado_telemetria_actual

    })


# =========================================================
# CERRAR SESIÓN
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# ERROR 404
# =========================================================

@app.errorhandler(404)
def pagina_no_encontrada(error):

    return jsonify({

        "error": "Página no encontrada",

        "ruta": request.path

    }), 404


# =========================================================
# ERROR 500
# =========================================================

@app.errorhandler(500)
def error_servidor(error):

    return jsonify({

        "error": "Error interno del servidor",

        "detalle": str(error)

    }), 500


# =========================================================
# INICIALIZAR BASE DE DATOS
# =========================================================

inicializar_db()


# =========================================================
# EJECUCIÓN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 5000)
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
