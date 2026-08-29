
# ---------------------------------------------------------
# DASHBOARD DEL DUEÑO
# ---------------------------------------------------------

@app.route("/dueno")
def dueno():

    # Verificar que exista una sesión
    if "usuario" not in session:
        return redirect(url_for("login"))

    # Verificar que el usuario tenga rol de dueño
    if session.get("rol") != "dueno":
        flash("No tienes permiso para acceder a esta sección.")
        return redirect(url_for("login"))

    conexion = conectar_db()

    try:
        # Buscar las mascotas asociadas al propietario
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

    # IMPORTANTE:
    # La aplicación del dueño utiliza dueno.html.
    # No se debe cargar medico.html.

    return render_template(
        "dueno.html",
        nombre=session.get("nombre"),
        mascotas=mascotas,
        telemetria=estado_telemetria_actual
    )

