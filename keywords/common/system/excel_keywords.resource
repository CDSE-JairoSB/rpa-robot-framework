*** Settings ***
Documentation       Keywords de bajo nivel para manipulación de archivos y datos tabulares (System Layer).
Resource            ../../../resources/common/settings.resource

*** Keywords ***
Cargar Cola De Trabajo Desde CSV O Excel
    [Documentation]    Lee el archivo de transacciones pendientes y lo retorna como una tabla iterable.
    [Arguments]    ${ruta_archivo}
    File Should Exist    ${ruta_archivo}
    ${extension}=        Get File Extension    ${ruta_archivo}
    IF    '${extension}' == '.csv'
        ${tabla}=    Read Table From Csv    ${ruta_archivo}    header=${True}
    ELSE
        Open Workbook       ${ruta_archivo}
        ${tabla}=           Read Worksheet As Table    header=${True}
        Close Workbook
    END
    ${total_filas}=      Get Length    ${tabla}
    Log    Cargados ${total_filas} registros de trabajo desde '${ruta_archivo}'.    level=INFO
    RETURN    ${tabla}

Archivar Archivo Procesado
    [Documentation]    Mueve el archivo de entrada a la carpeta de salida con timestamp de ejecución.
    [Arguments]    ${archivo_origen}    ${carpeta_destino}
    ${nombre_archivo}=     Get File Name    ${archivo_origen}
    ${timestamp}=          Get Current Date    result_format=%Y%m%d_%H%M%S
    ${nuevo_nombre}=       Set Variable    ${carpeta_destino}${/}procesado_${timestamp}_${nombre_archivo}
    Move File              ${archivo_origen}    ${nuevo_nombre}
    Log    Archivo archivado a: ${nuevo_nombre}    level=INFO

Obtener Extension Archivo
    [Arguments]    ${ruta}
    ${_, ext}=    Split Extension    ${ruta}
    RETURN    ${ext}
