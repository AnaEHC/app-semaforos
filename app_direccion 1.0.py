import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2 import service_account
from fpdf import FPDF

# CONFIGURACIÓN DE CONEXIÓN
SERVICE_ACCOUNT_FILE = 'C:/Users/user/Desktop/APP DIRECCION/CREDENCIALES/semaforo-direccion-c20318ce5a60.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build('drive', 'v3', credentials=credentials)

# ID carpeta principal
ID_CARPETA_PADRE = '1Sh2Pt_ZsKNrRz6GM6NbON0ICapYovCyS'
ID_BASE_ASIGNACIONES = '1XhxVi0YRCfZmeqEgKaJJo6SSbBq7UVgm'

# Mapeo semáforo -> carpeta
semaforos_carpetas = {
    "SEMAFORO ELCHE 2.0": "COMPARTIDO ELCHE 2.0",
    "SEMAFORO ELCHE 3.0": "COMPARTIDO ELCHE 3.0",
    "SEMAFORO ELCHE 4.0": "COMPARTIDO ELCHE 4.0",
    "SEMAFORO VIGO 1.0": "COMPARTIDO VIGO 1.0",
    "SEMAFORO VIGO 2.0": "COMPARTIDO VIGO 2.0",
    "SEMAFORO VIGO 3.0": "COMPARTIDO VIGO 3.0",
    "SEMAFORO LEON 1.0": "COMPARTIDO LEON 1.0"
}

# FUNCIONES AUXILIARES

def buscar_id_carpeta(nombre_carpeta):
    query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{nombre_carpeta}' and '{ID_CARPETA_PADRE}' in parents"
    resultados = service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultados.get('files', [])
    if archivos:
        return archivos[0]['id']
    return None

def buscar_semaforo_en_carpeta(id_carpeta):
    query = f"mimeType != 'application/vnd.google-apps.folder' and name contains 'SEMAFORO' and name contains '.xlsm' and '{id_carpeta}' in parents"
    resultados = service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultados.get('files', [])
    if archivos:
        return archivos[0]['id'], archivos[0]['name']
    return None, None

def descargar_archivo(file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        df = pd.read_excel(fh)
        return df
    except Exception as e:
        return pd.DataFrame()

def descargar_base_asignaciones():
    request = service.files().get_media(fileId=ID_BASE_ASIGNACIONES)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    df = pd.read_excel(fh)
    return df

def guardar_base_asignaciones(df):
    temp_path = "temp_base_asignaciones.xlsx"
    with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    media = MediaFileUpload(temp_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    service.files().update(fileId=ID_BASE_ASIGNACIONES, media_body=media).execute()
    try:
        os.remove(temp_path)
    except Exception:
        pass

def limpiar_texto(texto):
    """Quita emojis, convierte checks a SI/NO, y deja celdas vacías si no hay valor."""
    if str(texto).strip() == '✅':
        return 'SI'
    elif str(texto).strip() == '❌':
        return 'NO'
    elif pd.isna(texto) or str(texto).lower() == 'nan':
        return ''
    else:
        return ''.join(c for c in str(texto) if ord(c) < 256)

def generar_pdf(df, nombre_archivo):
    pdf = FPDF(orientation='L', unit='mm', format='A4')  # 🚨 Landscape (horizontal)
    pdf.add_page()
    pdf.set_font("Arial", size=8)
    
    page_width = pdf.w - 2 * pdf.l_margin
    col_width = page_width / (len(df.columns) + 0.5)  # Más espacio por columna
    row_height = pdf.font_size * 2

    # Escribir encabezados
    for col in df.columns:
        pdf.cell(col_width, row_height, limpiar_texto(col), border=1)
    pdf.ln(row_height)

    # Escribir datos
    for index, row in df.iterrows():
        for item in row:
            pdf.cell(col_width, row_height, limpiar_texto(item), border=1)
        pdf.ln(row_height)

    pdf.output(nombre_archivo)



def listar_archivos_en_carpeta(carpeta_id):
    """Lista todos los archivos en una carpeta de Google Drive."""
    query = f"'{carpeta_id}' in parents and trashed = false"
    resultados = service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultados.get('files', [])
    return archivos

# INICIO APP
st.set_page_config(page_title="App Semáforos Web + Closers", page_icon="🚦", layout="wide")
st.sidebar.title("🚦 Menú Principal")
opcion = st.sidebar.radio("Ir a:", ("🏠 Inicio", "📂 Semáforos Comerciales", "🎯 Asignar Closers", "📋 Seguimiento de Asignaciones"))

if opcion == "🏠 Inicio":
    st.title("🚦 Bienvenido a la App de Semáforos Web")
    st.success("¡Del contacto al cierre! 🚀")

elif opcion == "📂 Semáforos Comerciales":
    st.title("📂 Semáforos Comerciales")
    semaforo_elegido = st.selectbox("Selecciona un Semáforo:", list(semaforos_carpetas.keys()))

    if st.button("📥 Cargar Semáforo"):
        carpeta_nombre = semaforos_carpetas[semaforo_elegido]
        carpeta_id = buscar_id_carpeta(carpeta_nombre)
        if carpeta_id:
            file_id, file_name = buscar_semaforo_en_carpeta(carpeta_id)
            if file_id:
                df_semaforo = descargar_archivo(file_id)
                st.session_state['df_semaforo'] = df_semaforo
                st.success(f"✅ Semáforo {file_name} cargado correctamente.")
            else:
                st.warning(f"⚠️ No se encontró archivo SEMÁFORO en {carpeta_nombre}.")
        else:
            st.warning(f"⚠️ No se encontró carpeta {carpeta_nombre}.")

    if 'df_semaforo' in st.session_state:
        st.dataframe(st.session_state['df_semaforo'], use_container_width=True)

elif opcion == "🎯 Asignar Closers":
    st.title("🎯 Asignar Closers")

    columnas_mostrar = ["CALL", "COMERCIAL", "CLIENTE", "DÍA", "F2025", "F2026", "HL", "VIGILANCIA", "IMPLANT", "DENUNCIAS", "SEMAFORO", "NOTAS"]

    semaforos_carpetas = {
        "SEMAFORO ELCHE 2.0": "COMPARTIDO ELCHE 2.0",
        "SEMAFORO ELCHE 3.0": "COMPARTIDO ELCHE 3.0",
        "SEMAFORO ELCHE 4.0": "COMPARTIDO ELCHE 4.0",
        "SEMAFORO VIGO 1.0": "COMPARTIDO VIGO 1.0",
        "SEMAFORO VIGO 2.0": "COMPARTIDO VIGO 2.0",
        "SEMAFORO VIGO 3.0": "COMPARTIDO VIGO 3.0",
        "SEMAFORO LEON 1.0": "COMPARTIDO LEON 1.0"
    }

    clientes_totales = []

    for nombre_semaforo, nombre_carpeta in semaforos_carpetas.items():
        carpeta_id = buscar_id_carpeta(nombre_carpeta)
        if carpeta_id:
            archivos = listar_archivos_en_carpeta(carpeta_id)
            archivo_semaforo = next((a for a in archivos if a['name'].startswith("SEMAFORO") and a['name'].endswith(".xlsm")), None)
            if archivo_semaforo:
                df = descargar_archivo(archivo_semaforo['id'])
                if not df.empty:
                    columnas_presentes = [col for col in columnas_mostrar if col in df.columns]
                    df = df[columnas_presentes]
                    if 'DÍA' in df.columns:
                        df['DÍA'] = pd.to_datetime(df['DÍA'], errors='coerce').dt.strftime('%d/%m/%Y')
                    df = df[df["SEMAFORO"] == "ROJO"]
                    clientes_totales.append(df)
            else:
                st.warning(f"⚠️ No se encontró el archivo Semáforo en {nombre_carpeta}.")
        else:
            st.warning(f"⚠️ No se encontró la carpeta {nombre_carpeta}.")

    if clientes_totales:
        df_clientes = pd.concat(clientes_totales, ignore_index=True)

        st.subheader(f"Clientes ROJOS pendientes: {len(df_clientes)}")
        
        df_clientes['CLOSER ASIGNADO'] = ""

        edited_df = st.data_editor(
            df_clientes,
            column_config={
                "CALL": st.column_config.TextColumn(disabled=True),
                "COMERCIAL": st.column_config.TextColumn(disabled=True),
                "CLIENTE": st.column_config.TextColumn(disabled=True),
                "DÍA": st.column_config.TextColumn(disabled=True),
                "F2025": st.column_config.TextColumn(disabled=True),
                "F2026": st.column_config.TextColumn(disabled=True),
                "HL": st.column_config.TextColumn(disabled=True),
                "VIGILANCIA": st.column_config.TextColumn(disabled=True),
                "IMPLANT": st.column_config.TextColumn(disabled=True),
                "DENUNCIAS": st.column_config.TextColumn(disabled=True),
                "SEMAFORO": st.column_config.TextColumn(disabled=True),
                "NOTAS": st.column_config.TextColumn(disabled=True),
                "CLOSER ASIGNADO": st.column_config.TextColumn(help="Escribe aquí el nombre del Closer"),
            },
            use_container_width=True,
            num_rows="dynamic",
        )

        if st.button("✅ ASIGNAR CLIENTES"):
            asignaciones = descargar_base_asignaciones()
            nuevas_asignaciones = []

            for _, row in edited_df.iterrows():
                if row["CLOSER ASIGNADO"].strip():
                    nueva_asignacion = row.to_dict()
                    nueva_asignacion["ESTADO"] = ""
                    nuevas_asignaciones.append(nueva_asignacion)

            if nuevas_asignaciones:
                df_nuevas = pd.DataFrame(nuevas_asignaciones)
                if asignaciones.empty:
                    df_resultado = df_nuevas
                else:
                    df_resultado = pd.concat([asignaciones, df_nuevas], ignore_index=True)

                guardar_base_asignaciones(df_resultado)
                st.success("✅ Clientes asignados correctamente.")

                if 'df_clientes' in st.session_state:
                    del st.session_state['df_clientes']

                st.rerun()
            else:
                st.warning("⚠️ No has asignado ningún Closer.")

    else:
        st.info("ℹ️ No hay clientes ROJOS pendientes.")


elif opcion == "📋 Seguimiento de Asignaciones":
    st.title("📋 Seguimiento de Asignaciones")

    columnas_mostrar = [
        "CALL", "COMERCIAL", "CLIENTE", "DÍA",
        "F2025", "F2026", "HL", "VIGILANCIA",
        "IMPLANT", "DENUNCIAS", "SEMAFORO",
        "NOTAS", "ASIGNADO", "ESTADO"
    ]

    if 'seguimiento' not in st.session_state:
        df_asignaciones = descargar_base_asignaciones()
        if not df_asignaciones.empty:
            columnas_presentes = [col for col in columnas_mostrar if col in df_asignaciones.columns]
            df_asignaciones = df_asignaciones[columnas_presentes]
            if 'DÍA' in df_asignaciones.columns:
                df_asignaciones['DÍA'] = pd.to_datetime(df_asignaciones['DÍA'], errors='coerce').dt.strftime('%d/%m/%Y')
            if 'ESTADO' in df_asignaciones.columns:
                df_asignaciones['ESTADO'] = df_asignaciones['ESTADO'].astype(str)
            df_asignaciones['selected'] = False
            st.session_state['seguimiento'] = df_asignaciones
        else:
            st.session_state['seguimiento'] = pd.DataFrame(columns=columnas_mostrar + ['selected'])

    st.subheader("Gestiona el seguimiento de clientes asignados:")


    col_seleccionar, col_vacio = st.columns([1, 9])
    with col_seleccionar:
        if st.button("✅ Seleccionar Todos"):
            st.session_state['seguimiento']['selected'] = True

    edited_df = st.data_editor(
        st.session_state['seguimiento'],
        column_order=["selected"] + columnas_mostrar,
        column_config={
            "selected": st.column_config.CheckboxColumn(label=""),
            "CALL": st.column_config.TextColumn(disabled=True),
            "COMERCIAL": st.column_config.TextColumn(disabled=True),
            "CLIENTE": st.column_config.TextColumn(disabled=True),
            "DÍA": st.column_config.TextColumn(disabled=True),
            "F2025": st.column_config.TextColumn(disabled=True),
            "F2026": st.column_config.TextColumn(disabled=True),
            "HL": st.column_config.TextColumn(disabled=True),
            "VIGILANCIA": st.column_config.TextColumn(disabled=True),
            "IMPLANT": st.column_config.TextColumn(disabled=True),
            "DENUNCIAS": st.column_config.TextColumn(disabled=True),
            "SEMAFORO": st.column_config.TextColumn(disabled=True),
            "NOTAS": st.column_config.TextColumn(disabled=True),
            "CLOSER ASIGNADO": st.column_config.TextColumn(disabled=True),
            "ESTADO": st.column_config.TextColumn(help="Escribe el Estado final del cliente"),
        },
        use_container_width=True,
        num_rows="dynamic",
    )

    col1, col2 = st.columns([1,1])

    with col1:
        if st.button("🗑️ BORRAR ASIGNADOS"):
            df_filtrado = edited_df[edited_df["selected"] != True]
            df_filtrado = df_filtrado.drop(columns=["selected"])
            guardar_base_asignaciones(df_filtrado)
            st.success("✅ Asignados borrados correctamente.")
            st.session_state['seguimiento'] = df_filtrado
            st.rerun()

    with col2:
        if st.button("⬇️ DESCARGAR PDF"):
            nombre_pdf = "seguimiento_asignaciones.pdf"
            df_para_pdf = edited_df.drop(columns=["selected"])
            generar_pdf(df_para_pdf, nombre_pdf)
            with open(nombre_pdf, "rb") as file:
                st.download_button("Tu decarga aquí", file, file_name=nombre_pdf)
