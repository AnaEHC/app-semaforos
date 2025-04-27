# --- IMPORTS ---
import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2 import service_account
from fpdf import FPDF

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="App Semáforos Web + Closers", page_icon="🚦", layout="wide")

# --- CONEXIÓN GOOGLE DRIVE ---
SCOPES = ['https://www.googleapis.com/auth/drive']

# Leemos las credenciales desde los secretos de Streamlit
credentials_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(credentials_info, scopes=SCOPES)

# Creamos el servicio de conexión a Drive
service = build('drive', 'v3', credentials=credentials)

# IDs de carpeta y base de datos
ID_CARPETA_PADRE = '1Sh2Pt_ZsKNrRz6GM6NbON0ICapYovCyS'
ID_BASE_ASIGNACIONES = '1XhxVi0YRCfZmeqEgKaJJo6SSbBq7UVgm'

# --- FUNCIONES AUXILIARES ---

def buscar_id_carpeta(nombre_carpeta):
    query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{nombre_carpeta}' and '{ID_CARPETA_PADRE}' in parents"
    resultados = service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultados.get('files', [])
    return archivos[0]['id'] if archivos else None

def buscar_semaforo_en_carpeta(carpeta_id):
    query = (
        f"('{carpeta_id}' in parents) and "
        f"(mimeType='application/vnd.ms-excel.sheet.macroEnabled.12' or "
        f"mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') and "
        f"name contains 'SEMAFORO'"
    )
    resultados = service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultados.get('files', [])
    
    if archivos:
        return archivos[0]['id'], archivos[0]['name']
    else:
        return None, None




def crear_carpeta_closer(nombre_closer):
    nombre_carpeta = f"COMPARTIDO & {nombre_closer}"
    carpeta_id = buscar_id_carpeta(nombre_carpeta)
    if not carpeta_id:
        file_metadata = {'name': nombre_carpeta, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [ID_CARPETA_PADRE]}
        carpeta = service.files().create(body=file_metadata, fields='id').execute()
        return carpeta.get('id')
    return carpeta_id

def mover_archivo_a_carpeta(nombre_closer, df_clientes):
    carpeta_id = crear_carpeta_closer(nombre_closer)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_clientes.to_excel(writer, index=False)
    excel_buffer.seek(0)
    media = MediaIoBaseUpload(excel_buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resumable=True)
    service.files().create(body={'name': f"Asignaciones_{nombre_closer}.xlsx", 'parents': [carpeta_id]}, media_body=media, fields='id').execute()

def descargar_archivo(file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_excel(fh)

def descargar_base_asignaciones():
    try:
        request = service.files().get_media(fileId=ID_BASE_ASIGNACIONES)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return pd.read_excel(fh)
    except Exception:
        return pd.DataFrame()

def guardar_base_asignaciones(df):
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    excel_buffer.seek(0)
    media = MediaIoBaseUpload(excel_buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resumable=True)
    service.files().update(fileId=ID_BASE_ASIGNACIONES, media_body=media).execute()

def obtener_clientes_rojos():
    clientes_rojos_total = []

    for nombre_semaforo, nombre_carpeta in st.session_state['semaforos_carpetas'].items():
        carpeta_id = buscar_id_carpeta(nombre_carpeta)
        if carpeta_id:
            file_id, file_name = buscar_semaforo_en_carpeta(carpeta_id)
            if file_id:
                df_semaforo = descargar_archivo(file_id)
                if "SEMAFORO" in df_semaforo.columns:
                    semaforo_columna = df_semaforo["SEMAFORO"].astype(str).fillna("").str.upper()
                    df_rojos = df_semaforo[semaforo_columna == "ROJO"]
                    if not df_rojos.empty:
                        df_rojos["CALL"] = nombre_semaforo
                        clientes_rojos_total.append(df_rojos)

    if clientes_rojos_total:
        df_final = pd.concat(clientes_rojos_total, ignore_index=True)
        df_final["CLOSER ASIGNADO"] = ""  # ✅ Añadimos columna vacía
        return df_final
    else:
        return pd.DataFrame()
def generar_pdf(df, nombre_archivo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=8)

    # Ancho de cada columna (puedes ajustarlo)
    col_width = pdf.w / (len(df.columns) + 1)

    # Encabezados
    for col_name in df.columns:
        pdf.cell(col_width, 10, str(col_name), border=1)
    pdf.ln(10)

    # Filas
    for _, row in df.iterrows():
        for item in row:
            pdf.cell(col_width, 10, str(item), border=1)
        pdf.ln(10)

    pdf.output(nombre_archivo)



# --- CARGA INICIAL DE DATOS ---
if 'datos_cargados' not in st.session_state:
    st.session_state['semaforos_carpetas'] = {
        "SEMAFORO ELCHE 2.0": "COMPARTIDO ELCHE 2.0",
        "SEMAFORO ELCHE 3.0": "COMPARTIDO ELCHE 3.0",
        "SEMAFORO ELCHE 4.0": "COMPARTIDO ELCHE 4.0",
        "SEMAFORO VIGO 1.0": "COMPARTIDO VIGO 1.0",
        "SEMAFORO VIGO 2.0": "COMPARTIDO VIGO 2.0",
        "SEMAFORO VIGO 3.0": "COMPARTIDO VIGO 3.0",
        "SEMAFORO LEON 1.0": "COMPARTIDO LEON 1.0"
    }
    st.session_state['clientes_rojos'] = obtener_clientes_rojos()  # 🚀 CORREGIDO AQUÍ
    st.session_state['seguimiento'] = descargar_base_asignaciones()  # 🚀 CORREGIDO AQUÍ
    st.session_state['datos_cargados'] = True


# --- MENÚ LATERAL ---
st.sidebar.title("🚦 Menú Principal")
opcion = st.sidebar.radio("Ir a:", ("🏠 Inicio", "📂 Semáforos Comerciales", "🎯 Asignar Closers", "📋 Seguimiento de Asignaciones", "📖 Manual de Usuario"))

# --- CONTENIDO SEGÚN PESTAÑA ---

if opcion == "🏠 Inicio":
    st.title("🚦 Bienvenido a la App de Semáforos Web")
    st.success("¡Del contacto, al cierre! 🚀")

# --- SECCIÓN SEMÁFOROS COMERCIALES ---
elif opcion == "📂 Semáforos Comerciales":
    st.title("📂 Semáforos Comerciales")
    
    # ⚡ Cambiado para usar bien el session_state
    semaforos_carpetas = st.session_state['semaforos_carpetas']
    
    semaforo_elegido = st.selectbox(
        "Selecciona un Semáforo:",
        list(semaforos_carpetas.keys())
    )
    
    carpeta_nombre = semaforos_carpetas[semaforo_elegido]
    carpeta_id = buscar_id_carpeta(carpeta_nombre)

    if carpeta_id:
        with st.spinner('⏳ Descargando semáforo...'):
            file_id, file_name = buscar_semaforo_en_carpeta(carpeta_id)
            if file_id:
                df_semaforo = descargar_archivo(file_id)
                st.dataframe(df_semaforo, use_container_width=True)
            else:
                st.warning(f"⚠️ No se encontró archivo SEMÁFORO en {carpeta_nombre}.")
    else:
        st.warning(f"⚠️ No se encontró carpeta {carpeta_nombre}.")

# --- SECCIÓN ASIGNAR CLOSERS ---
# --- SECCIÓN ASIGNAR CLOSERS ---
elif opcion == "🎯 Asignar Closers":
    st.title("🎯 Asignar Closers")

    # 🔄 Botón para actualizar clientes rojos
    if st.button("🔄 Actualizar clientes rojos"):
        with st.spinner('⏳ Actualizando clientes rojos...'):
            st.session_state['clientes_rojos'] = obtener_clientes_rojos()
            st.success("✅ Clientes rojos actualizados correctamente.")
            st.rerun()

    if 'clientes_rojos' not in st.session_state:
        st.session_state['clientes_rojos'] = obtener_clientes_rojos()

    clientes_rojos = st.session_state['clientes_rojos']

    if clientes_rojos.empty:
        st.info("ℹ️ No hay clientes ROJOS pendientes.")
    else:
        edited_df = st.data_editor(
            clientes_rojos,
            use_container_width=True,
            num_rows="fixed",
        )

        if st.button("✅ Asignar Clientes"):
            with st.spinner('⏳ Asignando clientes...'):
                nuevas_asignaciones = []
                closers_creados = {}  # 🔥 Creamos un diccionario para los nuevos closers

                for _, row in edited_df.iterrows():
                    closer = str(row["CLOSER ASIGNADO"]).strip()
                    if closer:
                        nueva = row.to_dict()
                        nueva["CLOSER"] = closer
                        nueva["ESTADO"] = ""
                        nuevas_asignaciones.append(nueva)

                        # 🔥 Agrupamos por Closer
                        if closer not in closers_creados:
                            closers_creados[closer] = []
                        closers_creados[closer].append(nueva)

                if nuevas_asignaciones:
                    # 🔥 Guardar nuevas asignaciones en la base
                    df_nuevas = pd.DataFrame(nuevas_asignaciones)
                    df_existente = descargar_base_asignaciones()
                    df_final = pd.concat([df_existente, df_nuevas], ignore_index=True)
                    guardar_base_asignaciones(df_final)

                    # 🔥 Crear carpetas de cada Closer y subir su archivo
                    for closer, clientes in closers_creados.items():
                        mover_archivo_a_carpeta(closer, pd.DataFrame(clientes))

                    # 🔥 Actualizar clientes rojos (solo los no asignados)
                    clientes_restantes = edited_df[edited_df["CLOSER ASIGNADO"].astype(str).str.strip() == ""]
                    st.session_state['clientes_rojos'] = clientes_restantes

                    st.success("✅ Clientes asignados y archivos de Closers creados correctamente.")
                    st.rerun()
                else:
                    st.warning("⚠️ No has asignado ningún Closer.")



# --- SECCIÓN SEGUIMIENTO DE ASIGNACIONES ---
elif opcion == "📋 Seguimiento de Asignaciones":
    st.title("📋 Seguimiento de Asignaciones")

    seguimiento = descargar_base_asignaciones()

    if seguimiento.empty:
        st.info("ℹ️ No hay asignaciones registradas todavía.")
    else:
        # 🔥 Convertimos columnas importantes a texto
        if "ESTADO" in seguimiento.columns:
            seguimiento["ESTADO"] = seguimiento["ESTADO"].astype(str)
        if "CLOSER" in seguimiento.columns:
            seguimiento["CLOSER"] = seguimiento["CLOSER"].astype(str)

        # 📍 Checkbox para mostrar solo asignaciones activas
        mostrar_pendientes = st.checkbox("👀 Mostrar solo asignaciones activas", value=True)

        # 🔥 Si marcaron mostrar solo activas, filtramos
        if mostrar_pendientes:
            seguimiento = seguimiento[seguimiento["ESTADO"].str.upper() != "FINALIZADO"]

        # 🔥 Contamos el número de asignaciones activas
        num_activas = len(seguimiento)

        # 🔥 Mostramos contador bonito
        st.info(f"👥 Asignaciones activas: **{num_activas}**")

        # 🔥 Editor de datos
        edited_df = st.data_editor(
            seguimiento,
            column_order=[
                "selected", "CALL", "COMERCIAL", "CLIENTE", "DÍA",
                "F2025", "F2026", "HL", "VIGILANCIA",
                "IMPLANT", "DENUNCIAS", "SEMAFORO",
                "NOTAS", "CLOSER", "ESTADO"
            ],
            use_container_width=True,
            num_rows="fixed",  # No dejar crear filas nuevas
            column_config={
                "ESTADO": st.column_config.SelectboxColumn(
                    "ESTADO",
                    help="Selecciona o escribe otro estado",
                    options=["", "FINALIZADO", "PASA CENTRAL"],
                    required=False,
                ),
                "CLOSER": st.column_config.TextColumn(
                    "CLOSER",
                    help="Escribe el nombre del closer",
                    required=False,
                )
            }
        )

        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("💾 Guardar cambios"):
                with st.spinner('⏳ Guardando asignaciones...'):
                    df_guardar = edited_df.copy()

                    # Aseguramos que todas las columnas necesarias existen
                    columnas_necesarias = [
                        "CALL", "COMERCIAL", "CLIENTE", "DÍA", "F2025", "F2026",
                        "HL", "VIGILANCIA", "IMPLANT", "DENUNCIAS", "SEMAFORO",
                        "NOTAS", "CLOSER", "ESTADO"
                    ]
                    for col in columnas_necesarias:
                        if col not in df_guardar.columns:
                            df_guardar[col] = ""

                    df_guardar["selected"] = False  # Reset columna seleccionados

                    st.session_state['seguimiento'] = df_guardar
                    guardar_base_asignaciones(df_guardar)

                    st.success("✅ Asignaciones guardadas correctamente.")
                    st.rerun()

        with col2:
            if st.button("⬇️¿Quireres un Informe PDF?"):
                with st.spinner('⏳ Generando PDF...'):
                    nombre_pdf = "seguimiento_asignaciones.pdf"
                    df_para_pdf = edited_df.drop(columns=["selected"])
                    generar_pdf(df_para_pdf, nombre_pdf)
                    with open(nombre_pdf, "rb") as file:
                        st.download_button("Descargarlo aquí", file, file_name=nombre_pdf)


elif opcion == "📖 Manual de Usuario":
    st.title("📖 Manual de Usuario 🚀")
    st.write("Bienvenido/a a la guía rápida de uso de la App de Semáforos Web + Closers.")

    st.divider()

    st.header("🏠 Inicio")
    st.markdown("""
    - Aquí puedes ver el resumen general de la aplicación.
    - Es la pantalla principal desde donde partes para usar las otras secciones.
    """)

    st.divider()

    st.header("📂 Semáforos Comerciales")
    st.markdown("""
    - Consulta el estado de los clientes en cada Semáforo.
    - **Rojo 🔴:** Cliente en riesgo / no trabajado.
    - **Amarillo 🟡:** Cliente en seguimiento.
    - **Verde 🟢:** Cliente trabajado y estable.
    - **Azul 🔵:** Cliente cerrado o no interesado.
    """)

    st.divider()

    st.header("🎯 Asignar Closers")
    st.markdown("""
    - Asigna manualmente un **Closer** a cada cliente ROJO pendiente.
    - Pasos:
      1. Escribe el nombre del **Closer** en la columna "CLOSER ASIGNADO".
      2. Pulsa el botón ✅ **Asignar Clientes**.
      3. Los clientes asignados desaparecerán de esta lista y pasarán al seguimiento.

    - Cada Closer recibirá automáticamente su archivo de asignaciones 📄.
    """)

    st.divider()

    st.header("📋 Seguimiento de Asignaciones")
    st.markdown("""
    - Aquí puedes hacer seguimiento de los clientes asignados:
      - Selecciona de la columna **ESTADO** en el desplegable la opción correcta.
      - Filtrar con el checkbox 👀 **"Mostrar solo asignaciones activas"**.
      - Guardar los cambios pulsando **💾 Guardar cambios**.
      - Descargar el listado en PDF pulsando **⬇️ Descargar PDF**.

    - **Nota:** Un cliente marcado como **FINALIZADO** dejará de mostrarse si tienes activo el filtro.
    """)

    st.divider()

    st.header("🛠️ Consejos y Buenas Prácticas")
    st.markdown("""
    - Trabaja en modo **pantalla completa** para mejor experiencia.
    - Antes de asignar un Closer, asegúrate de escribir bien el nombre.
    - Usa siempre los botones de la app, **no borres nada manualmente** desde Drive.
    - Guarda cambios cada vez que hagas modificaciones grandes.
    - Al terminar tus asignaciones, descarga el PDF como respaldo.

    > 📢 **Importante:** La app no borra datos de Drive automáticamente. Siempre puedes recuperar información en el histórico si la necesitas.
    """)

    st.divider()

    st.success("¡Ahora estás listo/a para trabajar a toda máquina! 🚀")

