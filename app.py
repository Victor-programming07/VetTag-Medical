import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'telemetria_veterinaria_pajan_2026_key')

DB_NAME = "veterinaria.db"

def obtener_conexion_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_bd():
    conn = obtener_conexion_db()
    cursor = conn.cursor()
    
    # Tabla de usuarios (Tu estructura original intacta)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            fecha_creacion TEXT NOT NULL
        )
    ''')
    
    # 📌 Nueva tabla segura para almacenar los datos de telemetría de las mascotas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperatura REAL,
            ritmo_cardiaco INTEGER,
            accel_x REAL,
            accel_y REAL,
            accel_z REAL,
            efecto_hall INTEGER,
            latitud REAL,
            longitud REAL,
            velocidad_kmh REAL,
            fecha_registro TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# Inicializar base de datos al arrancar
inicializar_bd()

@app.route('/')
def inicio():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = obtener_conexion_db()
    cursor = conn.cursor()
    
    # Comprobar si existe un usuario principal
    cursor.execute("SELECT * FROM usuarios LIMIT 1")
    usuario_existente = cursor.fetchone()

    # MODO 1: Registro Inicial (Si la BD está vacía)
    if not usuario_existente:
        if request.method == 'POST':
            usuario = request.form.get('usuario', '').strip()
            password = request.form.get('password', '').strip()

            if not usuario or not password:
                flash("Por favor, complete todos los campos.", "error")
                conn.close()
                return render_template('login.html', modo='registro')

            password_hash = generate_password_hash(password)
            fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                "INSERT INTO usuarios (usuario, password, fecha_creacion) VALUES (?, ?, ?)",
                (usuario, password_hash, fecha_hoy)
            )
            conn.commit()
            conn.close()

            flash("Credenciales guardadas con éxito. Ya puedes iniciar sesión.", "success")
            return redirect(url_for('login'))

        conn.close()
        return render_template('login.html', modo='registro')

    # MODO 2: Expiración de Contraseña (Más de 30 días)
    fecha_creacion = datetime.strptime(usuario_existente['fecha_creacion'], "%Y-%m-%d %H:%M:%S")
    dias_transcurridos = (datetime.now() - fecha_creacion).days

    if dias_transcurridos >= 30:
        if request.method == 'POST':
            nueva_password = request.form.get('password', '').strip()

            if not nueva_password:
                flash("Ingresa una nueva contraseña válida.", "error")
                conn.close()
                return render_template('login.html', modo='expirado', usuario_expirado=usuario_existente['usuario'])

            nueva_hash = generate_password_hash(nueva_password)
            fecha_actualizada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                "UPDATE usuarios SET password = ?, fecha_creacion = ? WHERE id = ?",
                (nueva_hash, fecha_actualizada, usuario_existente['id'])
            )
            conn.commit()
            conn.close()

            flash("Contraseña actualizada correctamente.", "success")
            return redirect(url_for('login'))

        conn.close()
        return render_template('login.html', modo='expirado', usuario_expirado=usuario_existente['usuario'])

    # MODO 3: Login Normal
    if request.method == 'POST':
        usuario_ingresado = request.form.get('usuario', '').strip()
        password_ingresada = request.form.get('password', '').strip()

        cursor.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario_ingresado,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password_ingresada):
            session['usuario_id'] = user['id']
            session['usuario_nombre'] = user['usuario']
            flash(f"¡Bienvenido/a {user['usuario']}!", "success")
            
            return render_template('dueno.html', usuario=user['usuario'])
        else:
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template('login.html', modo='login')

    conn.close()
    return render_template('login.html', modo='login')


# -----------------------------------------------------------------
# 📌 NUEVA RUTA API: Recibe los datos del ESP32 o de tus pruebas PowerShell
# -----------------------------------------------------------------
@app.route('/api/datos', methods=['POST'])
def recibir_datos():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "Payload JSON vacío"}), 400

        # Extracción de parámetros
        temp = data.get('temperatura')
        bpm = data.get('ritmo_cardiaco')
        acc_x = data.get('accel_x')
        acc_y = data.get('accel_y')
        acc_z = data.get('accel_z')
        hall = data.get('efecto_hall')
        lat = data.get('latitud')
        lon = data.get('longitud')
        vel = data.get('velocidad_kmh')

        conn = sqlite3.connect('veterinaria.db')
        cursor = conn.cursor()

        # 1. Asegurar que la tabla exista con todas las columnas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                temperatura REAL,
                ritmo_cardiaco INTEGER,
                accel_x REAL,
                accel_y REAL,
                accel_z REAL,
                efecto_hall INTEGER,
                latitud REAL,
                longitud REAL,
                velocidad_kmh REAL
            )
        ''')

        # 2. Inserción de datos
        cursor.execute('''
            INSERT INTO telemetria (temperatura, ritmo_cardiaco, accel_x, accel_y, accel_z, efecto_hall, latitud, longitud, velocidad_kmh)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (temp, bpm, acc_x, acc_y, acc_z, hall, lat, lon, vel))

        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Datos guardados correctamente"}), 201

    except Exception as e:
        print(f"❌ Error en servidor: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
