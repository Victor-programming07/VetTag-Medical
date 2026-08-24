import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'telemetria_veterinaria_pajan_2026_key')

# Almacenamiento en RAM de la última lectura del ESP32
ultima_telemetria = {
    "temperatura": 0,
    "ritmo_cardiaco": 0,
    "accel_x": 0.0,
    "accel_y": 0.0,
    "accel_z": 0.0,
    "efecto_hall": 0,
    "latitud": 0.0,
    "longitud": 0.0,
    "velocidad_kmh": 0.0,
    "fecha_registro": "--:--:--"
}

@app.route('/')
def inicio():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_ingresado = request.form.get('usuario', '').strip()
        password_ingresada = request.form.get('password', '').strip()

        if usuario_ingresado and password_ingresada:
            session['usuario_nombre'] = usuario_ingresado
            flash(f"¡Bienvenido/a {usuario_ingresado}!", "success")
            return render_template('dueno.html', usuario=usuario_ingresado)
        else:
            flash("Por favor ingrese usuario y contraseña.", "error")
            return render_template('login.html', modo='login')

    return render_template('login.html', modo='login')

# -----------------------------------------------------------------
# ENDPOINT POST: Recibe telemetría desde el ESP32
# -----------------------------------------------------------------
@app.route('/api/datos', methods=['POST'])
def recibir_datos():
    global ultima_telemetria
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON vacío"}), 400

        ultima_telemetria = {
            "temperatura": data.get('temperatura', 0),
            "ritmo_cardiaco": data.get('ritmo_cardiaco', 0),
            "accel_x": data.get('accel_x', 0.0),
            "accel_y": data.get('accel_y', 0.0),
            "accel_z": data.get('accel_z', 0.0),
            "efecto_hall": data.get('efecto_hall', 0),
            "latitud": data.get('latitud', 0.0),
            "longitud": data.get('longitud', 0.0),
            "velocidad_kmh": data.get('velocidad_kmh', 0.0),
            "fecha_registro": datetime.now().strftime("%H:%M:%S")
        }

        return jsonify({"status": "success", "message": "Guardado en memoria"}), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# -----------------------------------------------------------------
# ENDPOINT GET: Sirve los datos al HTML de la App del Dueño
# -----------------------------------------------------------------
@app.route('/api/telemetria', methods=['GET'])
def obtener_telemetria():
    global ultima_telemetria
    try:
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
        estado_act = "Reposo" if mag < 1.2 else "Caminando"

        return jsonify({
            "temperatura": temp,
            "ritmo_cardiaco": bpm,
            "pechera_puesta": bool(hall == 1),
            "actividad": {"estado": estado_act},
            "diagnostico": {
                "salud_mascota": "Saludable" if temp <= 39.2 else "Alerta",
                "badge_class": "bg-success" if temp <= 39.2 else "bg-warning",
                "mensaje": "Estado dentro del rango óptimo."
            },
            "gps": {"valido": bool(lat != 0), "latitud": lat, "longitud": lon},
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
