
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

app.secret_key = "vetetech_telemetry_secure_key_2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "vettag.db")


# ---------------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------------

def conectar_db():
    conexion = sqlite3.connect(DATABASE)
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_db():
    conexion = conectar_db()
    cursor = conexion.cursor()

    # Tabla de usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    """)

    # Tabla de mascotas
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

    # Usuario dueño de prueba
    cursor.execute("""
        SELECT * FROM usuarios WHERE usuario = ?
    """, ("dueno",))

    usuario = cursor.fetchone()

    if usuario is None:
        cursor.execute("""
            INSERT INTO usuarios
            (usuario, password, nombre, rol)
            VALUES (?, ?, ?, ?)
        """, (
            "dueno",
            "1234",
            "Dueño de Mascota",
            "dueno"
        ))

    # Mascota de prueba
    cursor.execute("SELECT COUNT(*) AS total FROM mascotas")
    total = cursor.fetchone()["total"]

    if total == 0:
        cursor.execute("""
            INSERT INTO mascotas
            (nombre, especie, raza, edad, propietario)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Mi Mascota",
            "Perro",
            "Mestizo",
            "2 años",
            "Dueño de Mascota"
        ))

    conexion.commit()
    conexion.close()


# ---------------------------------------------------------
# TELEMETRÍA ACTUAL DEL ESP32
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# FUNCIÓN PARA DETERMINAR ACTIVIDAD
# ---------------------------------------------------------

def determinar_actividad(acx, acy, acz):

    try:
        movimiento = abs(float(acx)) + abs(float(acy)) + abs(float(acz))

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


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

@app.route("/", methods=["GET"])
def inicio():

    if "usuario" in session:

        if session.get("rol") == "dueno":
            return redirect(url_for("dueno"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "").strip()

        conexion = conectar_db()

        user = conexion.execute("""
            SELECT *
            FROM usuarios
            WHERE usuario = ?
            AND password = ?
        """, (usuario, password)).fetchone()

        conexion.close()

        if user:

            session["usuario"] = user["usuario"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]

            if user["rol"] == "dueno":
                return redirect(url_for("dueno"))

            flash("Este usuario no pertenece a la aplicación del dueño.")

        else:

            flash("Credenciales incorrectas.")

    return render_template("login.html")


# ---------------------------------------------------------
# DASHBOARD DEL DUEÑO
# ---------------------------------------------------------

@app.route("/dueno")
def dueno():

    if "usuario" not in session:
        return redirect(url_for("login"))

    if session.get("rol") != "dueno":
        flash("No tienes permiso para acceder a esta sección.")
        return redirect(url_for("login"))

    conexion = conectar_db()

    mascotas = conexion.execute("""
        SELECT *
        FROM mascotas
        WHERE propietario = ?
        OR propietario = ?
    """, (
        session.get("nombre"),
        ""
    )).fetchall()

    conexion.close()

    # -----------------------------------------------------
    # IMPORTANTE:
    # AQUÍ SE CARGA dueno.html
    # NO medico.html
    # -----------------------------------------------------

    return render_template(
        "dueno.html",
        nombre=session.get("nombre"),
        mascotas=mascotas,
        telemetria=estado_telemetria_actual
    )


# ---------------------------------------------------------
# OBTENER TELEMETRÍA
# ---------------------------------------------------------

@app.route("/api/telemetria", methods=["GET"])
def obtener_telemetria():

    return jsonify({
        "ok": True,
        "telemetria": estado_telemetria_actual
    })


# ---------------------------------------------------------
# RECIBIR TELEMETRÍA DEL ESP32
# ---------------------------------------------------------

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

        # ---------------------------------------------
        # RITMO CARDIACO
        # ---------------------------------------------

        if "ritmo_cardiaco" in datos:
            estado_telemetria_actual["ritmo_cardiaco"] = float(
                datos["ritmo_cardiaco"]
            )

        elif "bpm" in datos:
            estado_telemetria_actual["ritmo_cardiaco"] = float(
                datos["bpm"]
            )

        # ---------------------------------------------
        # TEMPERATURA
        # ---------------------------------------------

        if "temperatura" in datos:
            estado_telemetria_actual["temperatura"] = float(
                datos["temperatura"]
            )

        elif "temperature" in datos:
            estado_telemetria_actual["temperatura"] = float(
                datos["temperature"]
            )

        # ---------------------------------------------
        # MPU6050
        # ---------------------------------------------

        if "acx" in datos:
            estado_telemetria_actual["acx"] = float(datos["acx"])

        if "acy" in datos:
            estado_telemetria_actual["acy"] = float(datos["acy"])

        if "acz" in datos:
            estado_telemetria_actual["acz"] = float(datos["acz"])

        # ---------------------------------------------
        # ACTIVIDAD
        # ---------------------------------------------

        estado_telemetria_actual["actividad"] = determinar_actividad(
            estado_telemetria_actual["acx"],
            estado_telemetria_actual["acy"],
            estado_telemetria_actual["acz"]
        )

        # ---------------------------------------------
        # PECHERA
        # ---------------------------------------------

        if "pechera_puesta" in datos:

            valor = datos["pechera_puesta"]

            if isinstance(valor, bool):
                estado_telemetria_actual["pechera_puesta"] = valor

            else:
                estado_telemetria_actual["pechera_puesta"] = (
                    str(valor).lower()
                    in ["true", "1", "si", "sí", "puesta"]
                )

        elif "pechera" in datos:

            valor = datos["pechera"]

            estado_telemetria_actual["pechera_puesta"] = (
                str(valor).lower()
                in ["true", "1", "si", "sí", "puesta"]
            )

        # ---------------------------------------------
        # GPS
        # ---------------------------------------------

        if "latitud" in datos:
            estado_telemetria_actual["gps"]["latitud"] = float(
                datos["latitud"]
            )

        elif "latitude" in datos:
            estado_telemetria_actual["gps"]["latitud"] = float(
                datos["latitude"]
            )

        if "longitud" in datos:
            estado_telemetria_actual["gps"]["longitud"] = float(
                datos["longitud"]
            )

        elif "longitude" in datos:
            estado_telemetria_actual["gps"]["longitud"] = float(
                datos["longitude"]
            )

        # ---------------------------------------------
        # FECHA Y HORA
        # ---------------------------------------------

        estado_telemetria_actual["ultima_actualizacion"] = (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        return jsonify({
            "ok": True,
            "mensaje": "Telemetría actualizada correctamente",
            "telemetria": estado_telemetria_actual
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# API SIMPLE PARA EL ESP32
# ---------------------------------------------------------

@app.route("/api/esp32", methods=["POST"])
def recibir_esp32():

    return actualizar_telemetria()


# ---------------------------------------------------------
# ESTADO DEL SISTEMA
# ---------------------------------------------------------

@app.route("/api/estado", methods=["GET"])
def estado():

    return jsonify({
        "servidor": "VETTAG",
        "estado": "online",
        "rol": session.get("rol"),
        "telemetria": estado_telemetria_actual
    })


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ---------------------------------------------------------
# MANEJO DE ERRORES
# ---------------------------------------------------------

@app.errorhandler(404)
def pagina_no_encontrada(error):

    return jsonify({
        "error": "Página no encontrada",
        "ruta": request.path
    }), 404


@app.errorhandler(500)
def error_servidor(error):

    return jsonify({
        "error": "Error interno del servidor",
        "detalle": str(error)
    }), 500


# ---------------------------------------------------------
# INICIALIZACIÓN
# ---------------------------------------------------------

inicializar_db()


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )


