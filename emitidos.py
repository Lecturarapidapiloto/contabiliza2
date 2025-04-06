import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode

from funciones_utiles import (
    resumen_cols, filtrar_duplicados_por_uuid, procesar_zip,
    mostrar_sumatorias, mostrar_tabla_seccion,
    exportar_csv_single, exportar_excel_single
)

def section_emitidos(company_rfc):
    st.header("CFDIs Emitidos")

    # Exportar Emitidos
    with st.expander("Exportar Emitidos"):
        formato_emitidos = st.radio("Seleccionar formato", ["CSV", "Excel", "PDF"], key="formato_export_emitidos")
        alcance_emitidos = st.radio("Exportar", ["Tabla Actual", "Toda la Sección"], key="alcance_export_emitidos")
        if st.button("Exportar Emitidos"):
            if "df_emitidos" in st.session_state and not st.session_state.df_emitidos.empty:
                if alcance_emitidos == "Tabla Actual":
                    df_exportar_emitidos = st.session_state.get("filtered_df_e", st.session_state.df_emitidos)
                else:
                    df_exportar_emitidos = st.session_state.df_emitidos.copy()

                if formato_emitidos == "CSV":
                    datos_csv = exportar_csv_single(df_exportar_emitidos)
                    st.download_button(
                        label="Descargar CSV",
                        data=datos_csv,
                        file_name="emitidos_exportados.csv",
                        mime="text/csv"
                    )
                elif formato_emitidos == "Excel":
                    datos_excel = exportar_excel_single(df_exportar_emitidos, "Emitidos")
                    st.download_button(
                        label="Descargar Excel",
                        data=datos_excel,
                        file_name="emitidos_exportados.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                elif formato_emitidos == "PDF":
                    st.warning("Exportación a PDF no implementada en este ejemplo.")
            else:
                st.warning("No hay datos disponibles para exportar en Emitidos.")

    # Carga ZIP
    uploaded_file_emitidos = st.file_uploader("Cargar archivo ZIP con XMLs Emitidos", type=["zip"], key="emitidos_file")
    if uploaded_file_emitidos is not None:
        rows = procesar_zip(uploaded_file_emitidos)
        if rows:
            new_df = pd.DataFrame(rows)
            new_df["Seleccionar"] = True
            new_df = filtrar_duplicados_por_uuid(new_df, st.session_state.df_emitidos, "UUID")
            if not new_df.empty:
                st.session_state.df_emitidos = pd.concat([st.session_state.df_emitidos, new_df], ignore_index=True)
                st.success(f"Se han cargado {len(new_df)} CFDIs Emitidos.")
            else:
                st.info("Todos los CFDIs en el ZIP ya existen (UUIDs duplicados).")
        else:
            st.info("No se encontraron archivos XML en el ZIP de Emitidos.")

    # Mostrar la tabla
    if not st.session_state.df_emitidos.empty:
        columnas_sumar = resumen_cols
        st.subheader("Selecciona el Periodo que Deseas Visualizar")

        df_emit = st.session_state.df_emitidos.copy()
        df_emit["Periodo"] = df_emit["Fecha"].apply(lambda x: x[:7] if isinstance(x, str) else "")
        periodos = sorted(df_emit["Periodo"].dropna().unique().tolist())

        if periodos:
            periodo_seleccionado_e = st.selectbox(
                "Periodo",
                options=periodos,
                index=len(periodos)-1,
                key="seleccion_periodo_emitidos"
            )
            df_emit_filtrado = df_emit[df_emit["Periodo"] == periodo_seleccionado_e]
        else:
            st.warning("No hay periodos disponibles para seleccionar.")
            df_emit_filtrado = pd.DataFrame()

        if not df_emit_filtrado.empty:
            gb_e = GridOptionsBuilder.from_dataframe(df_emit_filtrado)
            gb_e.configure_column("Seleccionar", editable=True, cellEditor='agCheckboxCellEditor', pinned=True)
            gb_e.configure_default_column(editable=True, resizable=True)
            gridOptions_e = gb_e.build()

            grid_response_e = AgGrid(
                df_emit_filtrado,
                gridOptions=gridOptions_e,
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                update_mode=GridUpdateMode.VALUE_CHANGED,
                height=600,
                width=2500
            )
            edited_df_e = pd.DataFrame(grid_response_e["data"])

            # REEMPLAZAMOS el bucle que actualizaba fila por fila,
            # y ahora asignamos directamente el DF completo:
            st.session_state.df_emitidos = edited_df_e.copy()

            # Guardamos DF filtrado para exportación de la "Tabla Actual"
            st.session_state.filtered_df_e = df_emit_filtrado.copy()

            # Tabs: Seleccionados / No Seleccionados
            tabs_emitidos = st.tabs(["CFDIs Seleccionados", "CFDIs No Seleccionados"])
            with tabs_emitidos[0]:
                seleccionados_df = df_emit_filtrado[df_emit_filtrado["Seleccionar"] == True]
                mostrar_tabla_seccion(seleccionados_df, "CFDIs Seleccionados")
                st.markdown("**Sumatorias para CFDIs Seleccionados:**")
                st.table(pd.DataFrame([mostrar_sumatorias(seleccionados_df, columnas_sumar)]))

            with tabs_emitidos[1]:
                no_seleccionados_df = df_emit_filtrado[df_emit_filtrado["Seleccionar"] == False]
                mostrar_tabla_seccion(no_seleccionados_df, "CFDIs No Seleccionados")
                st.markdown("**Sumatorias para CFDIs No Seleccionados:**")
                st.table(pd.DataFrame([mostrar_sumatorias(no_seleccionados_df, columnas_sumar)]))
        else:
            st.warning("No hay datos disponibles para el periodo seleccionado.")
