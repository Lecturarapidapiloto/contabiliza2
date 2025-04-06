import streamlit as st
import zipfile
import io
import xml.etree.ElementTree as ET
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode

# Mapea Forma de Pago
codigo_map_forma_pago = {
    "01": "Efectivo","02": "Cheque Nominativo","03": "Transferencia Electrónica de Fondos SPEI",
    "04": "Tarjeta de Crédito","05": "Monedero Electrónico","06": "Dinero Electrónico",
    "8": "Vales de Despensa","12": "Dación en Pago","13": "Pago por Subrogación",
    "14": "Pago por Consignación","15": "Condonación","17": "Compensación","23": "Novación",
    "24": "Confusión","25": "Remisión de Deuda","26": "Prescripción o Caducidad",
    "27": "A Satisfacción del Acreedor","28": "Tarjeta de Débito","29": "Tarjeta de Servicios",
    "30": "Aplicación de Anticipos","31": "Intermediario Pagos","99": "Por Definir",
}

# Mapea Uso de CFDI
codigo_map_uso_cfdi = {
    "G01": "Adquisición de mercancías","G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general","I01": "Construcciones","I02": "Mobiliario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte","I04": "Equipo de computo y accesorios","I05": "Dados, troqueles, moldes, matrices y herramental",
    "I06": "Comunicaciones telefónicas","I07": "Comunicaciones satelitales","I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios","D02": "Gastos médicos por incapacidad o discapacidad",
    "D03": "Gastos funerarios","D04": "Donativos","D05": "Intereses reales pagados por créditos hipotecarios (casa habitación)",
    "D06": "Aportaciones voluntarias al SAR","D07": "Primas por seguros de gastos médicos",
    "D08": "Gastos de transportación escolar obligatoria","D09": "Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones",
    "D10": "Pagos por servicios educativos (colegiaturas)","S01": "Sin efectos fiscales","CP01": "Pagos","CN01": "Nómina",
}

# Columnas para sumatorias
resumen_cols = [
    "Sub Total",
    "Descuento",
    "Total impuesto Trasladado",
    "Total impuesto Retenido",
    "Total",
    "Traslado IVA 0.160000 %"
]

def filtrar_duplicados_por_uuid(nuevo_df, df_existente, uuid_col="UUID"):
    if uuid_col not in df_existente.columns:
        return nuevo_df
    uuids_existentes = df_existente[uuid_col].unique()
    return nuevo_df[~nuevo_df[uuid_col].isin(uuids_existentes)]

def eliminar_duplicados_en_df(df, uuid_col="UUID"):
    if uuid_col not in df.columns:
        return df, 0
    n_antes = len(df)
    df_sin_dup = df.drop_duplicates(subset=[uuid_col], keep='first')
    n_despues = len(df_sin_dup)
    eliminados = n_antes - n_despues
    return df_sin_dup, eliminados

def mostrar_eliminar_duplicados_ui(df, nombre_tabla="Recibidos"):
    from st_aggrid import GridOptionsBuilder, AgGrid, DataReturnMode, GridUpdateMode

    st.subheader(f"Análisis de duplicados en {nombre_tabla}")
    if "UUID" not in df.columns:
        st.info(f"No existe la columna 'UUID' en la tabla '{nombre_tabla}'.")
        return None

    df_dup = df.copy()
    counts = df_dup["UUID"].value_counts()
    uuids_duplicados = counts[counts > 1].index
    df_duplicados = df_dup[df_dup["UUID"].isin(uuids_duplicados)]
    if df_duplicados.empty:
        st.info("No se encontraron CFDIs duplicados (mismo UUID).")
        return None

    st.markdown(f"Se encontraron **{len(df_duplicados)}** filas con UUID repetido.")
    st.info("Selecciona las filas que deseas **eliminar** de la tabla principal.")

    gb = GridOptionsBuilder.from_dataframe(df_duplicados)
    gb.configure_selection("multiple", use_checkbox=True)
    gridOptions = gb.build()

    grid_response = AgGrid(
        df_duplicados,
        gridOptions=gridOptions,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=400,
        width=2500,
    )

    filas_seleccionadas = grid_response["selected_rows"]
    if st.button(f"Eliminar duplicados seleccionados en {nombre_tabla}"):
        if not filas_seleccionadas:
            st.warning("No has seleccionado ningún CFDI para eliminar.")
            return None
        uuids_a_eliminar = [row["UUID"] for row in filas_seleccionadas]
        df_sin_seleccion = df[~df["UUID"].isin(uuids_a_eliminar)]
        st.success(f"Se han eliminado {len(filas_seleccionadas)} filas duplicadas en {nombre_tabla}.")
        return df_sin_seleccion
    return None

def procesar_zip(uploaded_file):
    # Este necesita la variable 'company_rfc', la inyectaremos vía import en main o se pasa por parámetro
    zip_bytes = uploaded_file.read()
    rows = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as thezip:
        ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4','tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        for filename in thezip.namelist():
            if filename.lower().endswith(".xml"):
                with thezip.open(filename) as xml_file:
                    try:
                        tree = ET.parse(xml_file)
                        root = tree.getroot()
                    except ET.ParseError:
                        st.warning(f"Error al parsear el archivo XML: {filename}")
                        continue

                    row = {
                        "XML": filename, "Rfc Emisor": "","Nombre Emisor": "","Régimen Fiscal Emisor": "",
                        "Rfc Receptor": "","Nombre Receptor": "","CP Receptor": "","Régimen Receptor": "",
                        "Uso Cfdi Receptor": "","Tipo": "","Serie": "","Folio": "","Fecha": "",
                        "Sub Total": "","Descuento": "","Total impuesto Trasladado": "","Nombre Impuesto": "",
                        "Total impuesto Retenido": "","Total": "","UUID": "","Método de Pago": "",
                        "Forma de Pago": "","Moneda": "","Tipo de Cambio": "","Versión": "","Estado": "",
                        "Estatus": "","Validación EFOS": "","Fecha Consulta": "","Conceptos": "",
                        "Relacionados": "","Tipo Relación": "","Traslado IVA 0.160000 %": ""
                    }
                    # Extraer datos
                    comp = root
                    row["Fecha"] = comp.attrib.get("Fecha", "")
                    row["Sub Total"] = comp.attrib.get("SubTotal", "")
                    row["Descuento"] = comp.attrib.get("Descuento", "")
                    row["Total"] = comp.attrib.get("Total", "")
                    row["Método de Pago"] = comp.attrib.get("MetodoPago", "")

                    forma_pago_codigo = comp.attrib.get("FormaPago", "")
                    forma_pago_desc = codigo_map_forma_pago.get(forma_pago_codigo, "")
                    if forma_pago_desc:
                        row["Forma de Pago"] = f"{forma_pago_codigo}-{forma_pago_desc}"
                    else:
                        row["Forma de Pago"] = forma_pago_codigo

                    row["Moneda"] = comp.attrib.get("Moneda", "")
                    row["Tipo de Cambio"] = comp.attrib.get("TipoCambio", "")
                    row["Versión"] = comp.attrib.get("Version", "")
                    row["Serie"] = comp.attrib.get("Serie", "")
                    row["Folio"] = comp.attrib.get("Folio", "")
                    row["Tipo"] = comp.attrib.get("TipoDeComprobante", "")

                    emisor = comp.find("cfdi:Emisor", namespaces=ns)
                    if emisor is not None:
                        row["Rfc Emisor"] = emisor.attrib.get("Rfc", "")
                        row["Nombre Emisor"] = emisor.attrib.get("Nombre", "")
                        row["Régimen Fiscal Emisor"] = emisor.attrib.get("RegimenFiscal", "")

                    receptor = comp.find("cfdi:Receptor", namespaces=ns)
                    if receptor is not None:
                        row["Rfc Receptor"] = receptor.attrib.get("Rfc", "")
                        row["Nombre Receptor"] = receptor.attrib.get("Nombre", "")
                        row["CP Receptor"] = receptor.attrib.get("DomicilioFiscalReceptor", "")
                        row["Régimen Receptor"] = receptor.attrib.get("RegimenFiscalReceptor", "")
                        uso_cfdi_codigo = receptor.attrib.get("UsoCFDI", "")
                        uso_cfdi_desc = codigo_map_uso_cfdi.get(uso_cfdi_codigo, "")
                        if uso_cfdi_desc:
                            row["Uso Cfdi Receptor"] = f"{uso_cfdi_codigo}-{uso_cfdi_desc}"
                        else:
                            row["Uso Cfdi Receptor"] = uso_cfdi_codigo

                    timbre = comp.find(".//tfd:TimbreFiscalDigital", namespaces=ns)
                    if timbre is not None:
                        row["UUID"] = timbre.attrib.get("UUID", "")

                    # Impuestos
                    impuestos_elem = comp.find("cfdi:Impuestos", namespaces=ns)
                    total_trasladado = (impuestos_elem.attrib.get("TotalImpuestosTrasladados")
                                        if impuestos_elem is not None else None)
                    impuestos_nombres = set()
                    traslado_iva_016 = ""

                    if total_trasladado is None:
                        total_trasladado = 0.0
                        for traslado in comp.findall(".//cfdi:Traslado", namespaces=ns):
                            try:
                                total_trasladado += float(traslado.attrib.get("Importe", "0"))
                            except:
                                pass
                            imp = traslado.attrib.get("Impuesto", "")
                            if imp:
                                impuestos_nombres.add(imp)
                            if traslado.attrib.get("TasaOCuota") == "0.160000" and traslado.attrib.get("Impuesto") == "002":
                                traslado_iva_016 = traslado.attrib.get("Importe", "")
                    else:
                        for traslado in comp.findall(".//cfdi:Traslado", namespaces=ns):
                            imp = traslado.attrib.get("Impuesto", "")
                            if imp:
                                impuestos_nombres.add(imp)
                            if traslado.attrib.get("TasaOCuota") == "0.160000" and traslado.attrib.get("Impuesto") == "002":
                                traslado_iva_016 = traslado.attrib.get("Importe", "")

                    total_retenido = 0.0
                    for retencion in comp.findall(".//cfdi:Retencion", namespaces=ns):
                        try:
                            total_retenido += float(retencion.attrib.get("Importe", "0"))
                        except:
                            pass

                    row["Total impuesto Trasladado"] = total_trasladado
                    row["Nombre Impuesto"] = ", ".join(impuestos_nombres)
                    row["Total impuesto Retenido"] = total_retenido
                    row["Traslado IVA 0.160000 %"] = traslado_iva_016

                    # Conceptos
                    conceptos = comp.findall("cfdi:Conceptos/cfdi:Concepto", namespaces=ns)
                    lista_conceptos = [f"{c.attrib.get('Descripcion','')}: {c.attrib.get('Importe','')}"
                                       for c in conceptos]
                    row["Conceptos"] = "; ".join(lista_conceptos)

                    rows.append(row)
    return rows


def mostrar_sumatorias(df, columnas_sumar):
    sumas = {}
    for col in columnas_sumar:
        sumas[col] = pd.to_numeric(df[col], errors='coerce').sum()
    return sumas

def mostrar_tabla_seccion(df, titulo, ancho=2500):
    st.subheader(titulo)
    if df.empty:
        st.write(f"No hay datos para {titulo.lower()}.")
    else:
        st.dataframe(df, width=ancho)

def exportar_csv_single(df):
    return df.to_csv(index=False).encode('utf-8')

def exportar_csv_multiple(dfs, nombres):
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for df, name in zip(dfs, nombres):
                csv = df.to_csv(index=False)
                zf.writestr(f"{name}.csv", csv)
        buffer.seek(0)
        return buffer.read()

def exportar_excel_single(df, sheet_name="Datos"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()

def exportar_datos(df_recibidos, df_emitidos, formato="Excel"):
    """
    Exporta los datos de Recibidos y Emitidos a Excel o CSV (ya sin filtros extra).
    """
    output = io.BytesIO()
    if formato == "Excel":
        df_deducibles = df_recibidos[df_recibidos["Deducible"] == True]
        df_no_deducibles = df_recibidos[df_recibidos["Deducible"] == False]
        df_emitidos_seleccionados = df_emitidos[df_emitidos["Seleccionar"] == True]
        df_emitidos_no_seleccionados = df_emitidos[df_emitidos["Seleccionar"] == False]

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_recibidos.to_excel(writer, sheet_name="Recibidos", index=False)
            df_deducibles.to_excel(writer, sheet_name="Deducibles", index=False)
            df_no_deducibles.to_excel(writer, sheet_name="No Deducibles", index=False)
            df_emitidos.to_excel(writer, sheet_name="Emitidos", index=False)
            df_emitidos_seleccionados.to_excel(writer, sheet_name="Emitidos Seleccionados", index=False)
            df_emitidos_no_seleccionados.to_excel(writer, sheet_name="Emitidos No Seleccionados", index=False)

        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_name = "CFDIs_Fiscales.xlsx"

    elif formato == "CSV":
        df_recibidos_export = df_recibidos.copy()
        df_emitidos_export = df_emitidos.copy()
        df_recibidos_export.insert(0, "Tipo", "Recibidos")
        df_emitidos_export.insert(0, "Tipo", "Emitidos")
        df_combined = pd.concat([df_recibidos_export, df_emitidos_export])
        output.write(df_combined.to_csv(index=False).encode("utf-8"))
        mime = "text/csv"
        file_name = "CFDIs_Fiscales.csv"

    output.seek(0)
    return output, file_name, mime
