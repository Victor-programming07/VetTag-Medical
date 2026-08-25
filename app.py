import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'telemetria_veterinaria_pajan_2026_key')

# Almacenamiento volátil en memoria RAM
ultima_telemetria = None
ultima_fecha_recepcion = None

# Tiempo límite sin recibir datos antes de reiniciar la RAM (en segundos)
TIMEOUT_DESCONEXION = 8

@app.route('/')
def inicio():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_ingresado = request.form.get('usuario', '').strip()
        password_ingresada = request.form.get('password', '').strip()
        rol = request.form.get('rol', 'dueno').strip()

        if usuario_ingresado and password_ingresada:
            session['usuario_nombre'] = usuario_ingresado
            session['rol'] = rol
            flash(f"¡Bienvenido/a {usuario_ingresado}!", "success")
            
            if rol == 'medico':
                return redirect(url_for('vista_medico'))
            return redirect(url_for('vista_dueno'))
        else:
            flash("Por favor ingrese usuario y contraseña.", "error")
            return render_template('login.html', modo='login')

    return render_template('login.html', modo='login')

@app.route('/dueno')
def vista_dueno():
    if 'usuario_nombre' not in session:
        return redirect(url_for('login'))
    return render_template('dueno.html', usuario=session['usuario_nombre'])

@app.route('/medico')
def vista_medico():
    if 'usuario_nombre' not in session:
        return redirect(url_for('login'))
    return render_template('medico.html', usuario=session['usuario_nombre'])


# -----------------------------------------------------------------
# 1. RECEPCIÓN DE DATOS DESDE ESP32 (POST)
# -----------------------------------------------------------------
@app.route('/api/datos', methods=['POST'])
def recibir_datos():
    global ultima_telemetria, ultima_fecha_recepcion
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON vacío"}), 400

        # Guardar en RAM los datos y actualizar marca de tiempo de recepción
        ultima_fecha_recepcion = datetime.now()
        ultima_telemetria = {
            "temperatura": data.get('temperatura', 0.0),
            "ritmo_cardiaco": data.get('ritmo_cardiaco', 0),
            "accel_x": data.get('accel_x', 0.0),
            "accel_y": data.get('accel_y', 0.0),
            "accel_z": data.get('accel_z', 0.0),
            "efecto_hall": data.get('efecto_hall', 0),
            "latitud": data.get('latitud', 0.0),
            "longitud": data.get('longitud', 0.0),
            "velocidad_kmh": data.get('velocidad_kmh', 0.0),
            "fecha_registro": ultima_fecha_recepcion.strftime("%H:%M:%S")
        }

        return jsonify({"status": "success", "message": "Datos recibidos correctamente"}), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------------------------------------------
# 2. CONSULTA DEL FRONTEND (GET) - AUTO-REINICIO DE VALORES A ZERO
# -----------------------------------------------------------------
@app.route('/api/telemetria', methods=['GET'])
def obtener_telemetria():
    global ultima_telemetria, ultima_fecha_recepcion
    try:
        # Evaluar si ha transcurrido más tiempo del permitido sin recibir nada del ESP32
        if ultima_fecha_recepcion is not None:
            segundos_sin_datos = (datetime.now() - ultima_fecha_recepcion).total_seconds()
            if segundos_sin_datos > TIMEOUT_DESCONEXION:
                # REINICIO AUTOMÁTICO DE MEMORIA
                ultima_telemetria = None
                ultima_fecha_recepcion = None

        # Si la RAM está vacía / reiniciada, responder a cero/vacío
        if ultima_telemetria is None:
            return jsonify({
                "conectado": False,
                "temperatura": 0,
                "ritmo_cardiaco": 0,
                "pechera_puesta": False,
                "actividad": {"estado": "Sin Conexión"},
                "diagnostico": {
                    "salud_mascota": "Desconectado",
                    "badge_class": "bg-secondary",
                    "mensaje": "Dispositivo fuera de línea. Esperando sensores..."
                },
                "gps": {"valido": False, "latitud": 0.0, "longitud": 0.0},
                "ultima_actualizacion": "--:--:--"
            })

        # Si el dispositivo está enviando activamente:
        temp = ultima_telemetria["temperatura"]
        bpm = ultima_telemetria["ritmo_cardiaco"]
        ax = ultima_telemetria["accel_x"]
        ay = ultima_telemetria["accel_y"]
        az = ultima_telemetria["accel_z"]
        hall = ultima_telemetria["efecto_hall"]
        lat = ultima_telemetria["latitud"]
        lon = ultima_telemetria["longitud"]
        fecha = ultima_telemetria["fecha_registro"]

        mag = (ax**2 + ay**2 + az**2)**0.5
        estado_act = "En Reposo" if mag < 1.2 else "En Movimiento"

        if temp > 39.2 or bpm > 140:
            salud = "Alerta Médica"
            badge = "bg-danger"
            mensaje = "Parámetros fuera de rango normal."
        else:
            salud = "Estable"
            badge = "bg-success"
            mensaje = "Constantes vitales dentro del rango óptimo."

        return jsonify({
            "conectado": True,
            "temperatura": temp,
            "ritmo_cardiaco": bpm,
            "pechera_puesta": bool(hall == 1),
            "actividad": {"estado": estado_act},
            "diagnostico": {
                "salud_mascota": salud,
                "badge_class": badge,
                "mensaje": mensaje
            },
            "gps": {"valido": bool(lat != 0 and lon != 0), "latitud": lat, "longitud": lon},
            "ultima_actualizacion": fecha
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
