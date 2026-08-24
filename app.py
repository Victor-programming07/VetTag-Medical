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
@app.route('/api/ultimos-datos', methods=['GET'])
def obtener_ultimos_datos():
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor()
        
        # Consultamos el registro más reciente según la ID
        cursor.execute('''
            SELECT temperatura, ritmo_cardiaco, accel_x, accel_y, accel_z,
                   efecto_hall, latitud, longitud, velocidad_kmh, fecha_registro
            FROM telemetria 
            ORDER BY id DESC LIMIT 1
        ''')
        
        fila = cursor.fetchone()
        conn.close()

        if fila:
            return jsonify({
                "status": "success",
                "temperatura": fila['temperatura'],
                "ritmo_cardiaco": fila['ritmo_cardiaco'],
                "accel_x": fila['accel_x'],
                "accel_y": fila['accel_y'],
                "accel_z": fila['accel_z'],
                "efecto_hall": fila['efecto_hall'],
                "latitud": fila['latitud'],
                "longitud": fila['longitud'],
                "velocidad_kmh": fila['velocidad_kmh'],
                "fecha_registro": fila['fecha_registro']
            }), 200
        else:
            return jsonify({"status": "empty", "mensaje": "Aún no hay lecturas registradas"}), 200

    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
