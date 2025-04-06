import streamlit as st
import pandas as pd
import io
import re
st.set_page_config(layout="wide")

from funciones_utiles import filtrar_duplicados_por_uuid  # si lo necesitas
from recibidos import section_recibidos
from emitidos import section_emitidos

# Variables en st.session_state
if 'df_recibidos' not in st.session_state:
    st.session_state.df_recibidos = pd.DataFrame()
if 'df_emitidos' not in st.session_state:
    st.session_state.df_emitidos = pd.DataFrame()
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = pd.DataFrame()
if 'filtered_df_e' not in st.session_state:
    st.session_state.filtered_df_e = pd.DataFrame()

# Barra lateral: RFC
company_rfc = st.sidebar.text_input("Ingrese el RFC de su empresa", value="")
if not company_rfc:
    st.warning("Por favor, ingrese el RFC de su empresa para continuar.")
    st.stop()

# Sección de Avance
def section_avance():
    st.header("📁 Gestión de Avance")
    
    avance_tabs = st.tabs(["💾 Guardar Avance", "📥 Cargar Avance"])
    
    with avance_tabs[0]:
        st.subheader("💾 Guardar Avance")
        if st.button("Guardar Avance"):
            guardar_avance()
    
    with avance_tabs[1]:
        st.subheader("📥 Cargar Avance")
        uploaded_file = st.file_uploader("📂 Cargar archivo Excel con avances", type=["xlsx"], key="cargar_avance_tab")
        if uploaded_file is not None:
            try:
                df_recibidos, df_emitidos = cargar_progreso(uploaded_file)
                if not df_recibidos.empty:
                    df_recibidos = filtrar_duplicados_por_uuid(df_recibidos, st.session_state.df_recibidos, "UUID")
                    st.session_state.df_recibidos = pd.concat([st.session_state.df_recibidos, df_recibidos], ignore_index=True)
                if not df_emitidos.empty:
                    df_emitidos = filtrar_duplicados_por_uuid(df_emitidos, st.session_state.df_emitidos, "UUID")
                    st.session_state.df_emitidos = pd.concat([st.session_state.df_emitidos, df_emitidos], ignore_index=True)
                st.success("✅ Avance cargado exitosamente.")
            except Exception as e:
                st.error(f"❌ Error al cargar el archivo: {e}")

def cargar_progreso(file):
    try:
        df_recibidos = pd.read_excel(file, sheet_name="Recibidos")
        df_emitidos = pd.read_excel(file, sheet_name="Emitidos")
        return df_recibidos, df_emitidos
    except Exception as e:
        st.error(f"Error al cargar el archivo: {e}")
        return pd.DataFrame(), pd.DataFrame()

def guardar_avance():
    st.warning("No implementado en este ejemplo. (Podrías hacerlo con exportar a Excel o CSV)")

# Función auxiliar: convertir número de columna (1-indexado) a letra de Excel
def colnum_to_excel(n):
    string = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        string = chr(65 + remainder) + string
    return string

# Sección de Exportar CFDIs en el sidebar
if 'df_recibidos' in st.session_state and not st.session_state.df_recibidos.empty:
    df_exp = st.session_state.df_recibidos.copy()
    df_exp["Periodo"] = df_exp["Fecha"].apply(lambda x: x[:7] if isinstance(x, str) else "")
    periodos_disponibles = sorted(df_exp["Periodo"].dropna().unique().tolist())
else:
    periodos_disponibles = []

export_option = st.sidebar.expander("Exportar CFDIs")
with export_option:
    export_tipo = st.radio("Exportar por", ["Deducibles", "Periodos"], key="export_tipo")
    
    # Opción de exportar por Períodos
    if export_tipo == "Periodos":
        selected_periods = st.multiselect("Seleccione los períodos a exportar (deje vacío para todos)", 
                                          periodos_disponibles, 
                                          default=periodos_disponibles)
        if st.button("Exportar por Períodos"):
            if not selected_periods:
                selected_periods = periodos_disponibles

            def limpiar_y_convertir_a_numerico(serie):
                serie = serie.astype(str).str.replace(r'[^0-9\.\-]', '', regex=True)
                return pd.to_numeric(serie, errors='coerce')

            def exportar_excel_por_periodos(df, periodos):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format='dd-mm-yyyy') as writer:
                    workbook = writer.book
                    date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
                    numeric_format = workbook.add_format({'num_format': '#,##0.00'})
                    col_widths = {
                        "Régimen Fiscal Emisor": 20,
                        "Rfc Receptor": 15,
                        "Nombre Receptor": 25,
                        "CP Receptor": 10,
                        "Régimen Receptor": 20,
                        "Uso Cfdi Receptor": 25,
                        "Tipo": 10,
                        "Serie": 10,
                        "Folio": 10,
                        "Fecha": 15,
                        "Sub Total": 12,
                        "Descuento": 12,
                        "Total impuesto Trasladado": 18,
                        "Nombre Impuesto": 25,
                        "Total impuesto Retenido": 18,
                        "Total": 15,
                        "UUID": 40,
                        "Método de Pago": 15,
                        "Forma de Pago": 20,
                        "Moneda": 10,
                        "Tipo de Cambio": 15,
                        "Versión": 10,
                        "Periodo": 10,
                        "Deducible": 10
                    }
                    numeric_cols = ["Sub Total", "Descuento", 
                                    "Total impuesto Trasladado", "Total impuesto Retenido", 
                                    "Total", "Tipo de Cambio"]
                    for p in periodos:
                        df_period = df[df["Periodo"] == p].copy()
                        if "Fecha" in df_period.columns:
                            df_period["Fecha"] = pd.to_datetime(df_period["Fecha"], errors="coerce")
                        for col in numeric_cols:
                            if col in df_period.columns:
                                df_period[col] = limpiar_y_convertir_a_numerico(df_period[col])
                        sheet_name = p if len(p) <= 31 else p[:31]
                        df_period.to_excel(writer, sheet_name=sheet_name, index=False)
                        worksheet = writer.sheets[sheet_name]
                        if "Fecha" in df_period.columns:
                            fecha_col_index = df_period.columns.get_loc("Fecha")
                            worksheet.set_column(fecha_col_index, fecha_col_index, col_widths.get("Fecha", 15), date_format)
                        for col in numeric_cols:
                            if col in df_period.columns:
                                col_index = df_period.columns.get_loc(col)
                                worksheet.set_column(col_index, col_index, col_widths.get(col, 12), numeric_format)
                        for idx, col in enumerate(df_period.columns):
                            if col not in numeric_cols and col != "Fecha":
                                width = col_widths.get(col, 12)
                                worksheet.set_column(idx, idx, width)
                        worksheet.autofilter(0, 0, df_period.shape[0], df_period.shape[1]-1)
                        # Condicional: resaltar en rojo las filas donde "Deducible" sea FALSE
                        if "Deducible" in df_period.columns:
                            ded_index = df_period.columns.get_loc("Deducible")
                            ded_letter = colnum_to_excel(ded_index + 1)
                            last_col_letter = colnum_to_excel(df_period.shape[1])
                            nrows = df_period.shape[0] + 1
                            data_range = f"A2:{last_col_letter}{nrows}"
                            red_format = workbook.add_format({'font_color': 'red'})
                            worksheet.conditional_format(data_range,
                                {'type': 'formula',
                                 'criteria': f'=NOT(${ded_letter}2)',
                                 'format': red_format})
                output.seek(0)
                return output.getvalue()

            excel_data = exportar_excel_por_periodos(df_exp, selected_periods)
            st.download_button("Descargar Excel por Períodos", data=excel_data,
                               file_name="CFDIs_por_periodos.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    # Opción de exportar por Deducibles
    elif export_tipo == "Deducibles":
        selected_periods_d = st.multiselect("Seleccione los períodos a exportar (deje vacío para todos)", 
                                            periodos_disponibles, 
                                            default=periodos_disponibles)
        if st.button("Exportar por Deducibles"):
            if not selected_periods_d:
                selected_periods_d = periodos_disponibles

            def limpiar_y_convertir_a_numerico(serie):
                serie = serie.astype(str).str.replace(r'[^0-9\.\-]', '', regex=True)
                return pd.to_numeric(serie, errors='coerce')

            def exportar_excel_por_deducibles(df, periodos):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format='dd-mm-yyyy') as writer:
                    workbook = writer.book
                    date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
                    numeric_format = workbook.add_format({'num_format': '#,##0.00'})
                    col_widths = {
                        "Régimen Fiscal Emisor": 20,
                        "Rfc Receptor": 15,
                        "Nombre Receptor": 25,
                        "CP Receptor": 10,
                        "Régimen Receptor": 20,
                        "Uso Cfdi Receptor": 25,
                        "Tipo": 10,
                        "Serie": 10,
                        "Folio": 10,
                        "Fecha": 15,
                        "Sub Total": 12,
                        "Descuento": 12,
                        "Total impuesto Trasladado": 18,
                        "Nombre Impuesto": 25,
                        "Total impuesto Retenido": 18,
                        "Total": 15,
                        "UUID": 40,
                        "Método de Pago": 15,
                        "Forma de Pago": 20,
                        "Moneda": 10,
                        "Tipo de Cambio": 15,
                        "Versión": 10,
                        "Periodo": 10,
                        "Deducible": 10
                    }
                    numeric_cols = ["Sub Total", "Descuento", 
                                    "Total impuesto Trasladado", "Total impuesto Retenido", 
                                    "Total", "Tipo de Cambio"]
                    
                    # Función auxiliar para aplicar formato condicional a filas de no deducibles
                    def aplicar_formato_no_deducibles(worksheet, df_sub):
                        nrows = df_sub.shape[0] + 1  # Incluye cabecera
                        ncols = df_sub.shape[1]
                        last_col_letter = colnum_to_excel(ncols)
                        red_format = workbook.add_format({'font_color': 'red'})
                        worksheet.conditional_format(f"A2:{last_col_letter}{nrows}",
                                                     {'type': 'formula',
                                                      'criteria': f'=NOT(${colnum_to_excel(df_sub.columns.get_loc("Deducible")+1)}2)',
                                                      'format': red_format})
                    
                    for p in periodos:
                        df_period = df[df["Periodo"] == p].copy()
                        # Dividir en deducibles y no deducibles
                        df_deducible = df_period[df_period["Deducible"] == True].copy()
                        df_no_deducible = df_period[df_period["Deducible"] == False].copy()
                        
                        for sub_df, sub_label in [(df_deducible, "Deducibles"), (df_no_deducible, "No Deducibles")]:
                            if "Fecha" in sub_df.columns:
                                sub_df["Fecha"] = pd.to_datetime(sub_df["Fecha"], errors="coerce")
                            for col in numeric_cols:
                                if col in sub_df.columns:
                                    sub_df[col] = limpiar_y_convertir_a_numerico(sub_df[col])
                            
                            sheet_name = f"{p} - {sub_label}"
                            if len(sheet_name) > 31:
                                sheet_name = sheet_name[:31]
                            sub_df.to_excel(writer, sheet_name=sheet_name, index=False)
                            
                            worksheet = writer.sheets[sheet_name]
                            if "Fecha" in sub_df.columns:
                                fecha_col_index = sub_df.columns.get_loc("Fecha")
                                worksheet.set_column(fecha_col_index, fecha_col_index, col_widths.get("Fecha", 15), date_format)
                            for col in numeric_cols:
                                if col in sub_df.columns:
                                    col_index = sub_df.columns.get_loc(col)
                                    worksheet.set_column(col_index, col_index, col_widths.get(col, 12), numeric_format)
                            for idx, col in enumerate(sub_df.columns):
                                if col not in numeric_cols and col != "Fecha":
                                    width = col_widths.get(col, 12)
                                    worksheet.set_column(idx, idx, width)
                            worksheet.autofilter(0, 0, sub_df.shape[0], sub_df.shape[1]-1)
                            
                            # Si es la hoja de "No Deducibles", aplicar formato condicional (texto en rojo)
                            if sub_label == "No Deducibles":
                                aplicar_formato_no_deducibles(worksheet, sub_df)
                output.seek(0)
                return output.getvalue()

            excel_data = exportar_excel_por_deducibles(df_exp, selected_periods_d)
            st.download_button("Descargar Excel por Deducibles", data=excel_data,
                               file_name="CFDIs_por_deducibles.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
# Título principal
st.title("Procesador de XMLs desde ZIP - CFDI 4.0")

# Radio para navegar entre secciones
seccion = st.sidebar.radio("Tipo de CFDIS", ["Recibidos", "Emitidos"], key="seccion")

# Lógica de navegación de secciones
if seccion == "Recibidos":
    section_recibidos(company_rfc)
elif seccion == "Emitidos":
    section_emitidos(company_rfc)
