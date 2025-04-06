import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode

from funciones_utiles import (
    resumen_cols, filtrar_duplicados_por_uuid, procesar_zip,
    mostrar_sumatorias, mostrar_tabla_seccion,
    exportar_csv_single, exportar_excel_single, exportar_datos
)

def section_recibidos(company_rfc):
    st.header("CFDIs Recibidos")

    # Cargar Archivos ZIP de Recibidos
    uploaded_file_recibidos = st.file_uploader(
        "Cargar archivo ZIP con XMLs Recibidos",
        type=["zip"],
        key="recibidos_file"
    )
    if uploaded_file_recibidos is not None:
        rows = procesar_zip(uploaded_file_recibidos)
        if rows:
            new_df = pd.DataFrame(rows)
            new_df["Deducible"] = True
            new_df = filtrar_duplicados_por_uuid(new_df, st.session_state.df_recibidos, "UUID")
            if not new_df.empty:
                st.session_state.df_recibidos = pd.concat([st.session_state.df_recibidos, new_df], ignore_index=True)
                st.success(f"Se han cargado {len(new_df)} CFDIs Recibidos.")
            else:
                st.info("Todos los CFDIs en el ZIP ya existen (UUIDs duplicados).")
        else:
            st.info("No se encontraron archivos XML en el ZIP de Recibidos.")

    # Mostrar la tabla si hay datos
    if not st.session_state.df_recibidos.empty:
        columnas_sumar = resumen_cols
        st.subheader("Selecciona el Periodo que Deseas Visualizar")

        # Calculamos el período a partir de la fecha
        df_rec = st.session_state.df_recibidos.copy()
        df_rec["Periodo"] = df_rec["Fecha"].apply(lambda x: x[:7] if isinstance(x, str) else "")
        periodos = sorted(df_rec["Periodo"].dropna().unique().tolist())

        if periodos:
            # Utilizamos una key estática para el selectbox
            periodo_seleccionado = st.selectbox(
                "Periodo",
                options=periodos,
                index=len(periodos)-1,
                key="seleccion_periodo_recibidos"
            )
            df_rec_filtrado = df_rec[df_rec["Periodo"] == periodo_seleccionado]
        else:
            st.warning("No hay periodos disponibles para seleccionar.")
            df_rec_filtrado = pd.DataFrame()

        if not df_rec_filtrado.empty:
            # Mostrar totales en la tabla principal
            total_main = len(df_rec_filtrado)
            total_deducibles = len(df_rec_filtrado[df_rec_filtrado["Deducible"] == True])
            total_no_deducibles = len(df_rec_filtrado[df_rec_filtrado["Deducible"] == False])
            st.markdown(
                f"**Totales en la tabla principal:** {total_main} XMLs  \n"
                f"**Deducibles:** {total_deducibles} XMLs  \n"
                f"**No Deducibles:** {total_no_deducibles} XMLs"
            )

            # Contenedor para la grilla; la key incluye el período seleccionado para forzar re-render
            grid_container = st.container()
            with grid_container:
                gb = GridOptionsBuilder.from_dataframe(df_rec_filtrado)
                gb.configure_column("Deducible", editable=True, cellEditor='agCheckboxCellEditor', pinned=True)
                gb.configure_default_column(editable=True, resizable=True)
                gridOptions = gb.build()

                grid_response = AgGrid(
                    df_rec_filtrado,
                    gridOptions=gridOptions,
                    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                    update_mode=GridUpdateMode.VALUE_CHANGED,
                    height=600,
                    width=2500,
                    key=f"grid_recibidos_{periodo_seleccionado}"
                )
            edited_df = pd.DataFrame(grid_response['data'])

            # Botón para aplicar cambios
            if st.button("Aplicar cambios", key="aplicar_cambios_recibidos"):
                update_dict = edited_df.set_index("XML")["Deducible"].to_dict()
                st.session_state.df_recibidos["Deducible"] = st.session_state.df_recibidos["XML"].map(
                    update_dict
                ).fillna(st.session_state.df_recibidos["Deducible"])
                st.success("Cambios aplicados. Si la grilla no se actualiza, recarga la página manualmente.")

            # Recalcular la tabla filtrada usando los datos actualizados
            df_rec_filtrado = st.session_state.df_recibidos.copy()
            df_rec_filtrado["Periodo"] = df_rec_filtrado["Fecha"].apply(lambda x: x[:7] if isinstance(x, str) else "")
            df_rec_filtrado = df_rec_filtrado[df_rec_filtrado["Periodo"] == periodo_seleccionado]
            st.session_state.filtered_df = df_rec_filtrado.copy()

            # Mostrar totales (nuevamente, para confirmar)
            total_main = len(df_rec_filtrado)
            total_deducibles = len(df_rec_filtrado[df_rec_filtrado["Deducible"] == True])
            total_no_deducibles = len(df_rec_filtrado[df_rec_filtrado["Deducible"] == False])
            st.markdown(
                f"**Actualizados:** {total_main} XMLs  |  "
                f"Deducibles: {total_deducibles}  |  "
                f"No Deducibles: {total_no_deducibles}"
            )

            # Mostrar pestañas según el estado "Deducible"
            tabs_recibidos = st.tabs(["Deducibles", "No Deducibles"])
            with tabs_recibidos[0]:
                deducible_df = df_rec_filtrado[df_rec_filtrado["Deducible"] == True]
                mostrar_tabla_seccion(deducible_df, "XMLs Deducibles")
                st.markdown("**Sumatorias para XMLs Deducibles:**")
                st.table(pd.DataFrame([mostrar_sumatorias(deducible_df, columnas_sumar)]))

            with tabs_recibidos[1]:
                no_deducible_df = df_rec_filtrado[df_rec_filtrado["Deducible"] == False]
                mostrar_tabla_seccion(no_deducible_df, "XMLs No Deducibles")
                st.markdown("**Sumatorias para XMLs No Deducibles:**")
                st.table(pd.DataFrame([mostrar_sumatorias(no_deducible_df, columnas_sumar)]))
        else:
            st.warning("No hay datos para el periodo seleccionado.")
