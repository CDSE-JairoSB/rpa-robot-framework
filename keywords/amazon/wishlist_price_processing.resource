*** Settings ***
Documentation       Lógica de negocio para consulta, comparación y persistencia de precios Amazon.
Resource            ../../resources/common/settings.resource
Resource            ../common/system/browser_keywords.resource

*** Keywords ***
Actualizar Wishlist Amazon
    [Documentation]    Consulta los artículos visibles, compara los precios y conserva un histórico CSV.
    ${history_path}=    Set Variable    ${CONFIG}[paths][price_history_file]
    ${history}=         Load Price History    ${history_path}
    ${items}=    Extraer Articulos Visibles De Wishlist
    ...    ${LOCATORS}[wishlist][item_cards]
    ...    ${LOCATORS}[wishlist][item_title]
    ...    ${LOCATORS}[wishlist][item_link]
    ...    ${LOCATORS}[wishlist][item_price]
    ...    ${LOCATORS}[wishlist][item_availability]

    ${found}=    Get Length    ${items}
    IF    ${found} == 0
        Fail    [SYSTEM_EXCEPTION] No se encontraron artículos con los selectores configurados.
    END
    Log    Se encontraron ${found} artículos visibles en la wishlist.    level=INFO

    ${records}=    Create List
    FOR    ${item}    IN    @{items}
        ${record}=    Procesar Articulo De Wishlist    ${item}    ${history}
        Append To List    ${records}    ${record}
    END

    ${saved}=    Append Price Records    ${history_path}    ${records}
    ${report}=   Write Execution Report    ${DATA_OUTPUT_DIR}    ${records}
    Log    Se persistieron ${saved} registros en '${history_path}'.    level=INFO
    Log    Reporte de ejecución generado: ${report}    level=INFO

Procesar Articulo De Wishlist
    [Documentation]    Construye y compara un registro; captura fallas por artículo sin detener el lote.
    [Arguments]    ${item}    ${history}
    ${total}=    Evaluate    ${TOTAL_ITEMS} + 1
    Set Global Variable    ${TOTAL_ITEMS}    ${total}

    ${name}=    Get From Dictionary    ${item}    product_name    default=${EMPTY}
    ${url}=     Get From Dictionary    ${item}    product_url    default=${EMPTY}
    ${raw_price}=    Get From Dictionary    ${item}    raw_price    default=${EMPTY}
    ${availability}=    Get From Dictionary    ${item}    availability    default=${EMPTY}

    TRY
        ${current}=    Build Price Record    ${EMPTY}    ${name}    ${url}    ${raw_price}    ${availability}
        ${identifier}=    Get From Dictionary    ${current}    product_id
        ${previous}=    Get Latest Price Record    ${history}    ${identifier}
        ${record}=      Compare Price Record    ${current}    ${previous}
        Actualizar Metricas Del Articulo    ${record}
        RETURN    ${record}
    EXCEPT    AS    ${error}
        ${record}=    Create Error Price Record    ${EMPTY}    ${name}    ${url}    ${error}
        ${sys}=       Evaluate    ${SYSTEM_EXCEPTIONS} + 1
        Set Global Variable    ${SYSTEM_EXCEPTIONS}    ${sys}
        Log    [EXCEPCION DE SISTEMA] Artículo '${name}': ${error}    level=ERROR
        RETURN    ${record}
    END

Actualizar Metricas Del Articulo
    [Documentation]    Actualiza contadores según el resultado normalizado del precio.
    [Arguments]    ${record}
    ${status}=         Get From Dictionary    ${record}    status
    ${change_type}=    Get From Dictionary    ${record}    price_change_type

    IF    '${status}' == 'OK'
        ${success}=    Evaluate    ${SUCCESSFUL_ITEMS} + 1
        Set Global Variable    ${SUCCESSFUL_ITEMS}    ${success}
    ELSE IF    '${status}' == 'PRICE_NOT_AVAILABLE'
        ${unavailable}=    Evaluate    ${UNAVAILABLE_ITEMS} + 1
        Set Global Variable    ${UNAVAILABLE_ITEMS}    ${unavailable}
    ELSE
        ${business}=    Evaluate    ${BUSINESS_EXCEPTIONS} + 1
        Set Global Variable    ${BUSINESS_EXCEPTIONS}    ${business}
    END

    IF    '${change_type}' == 'DECREASED'
        ${decreases}=    Evaluate    ${PRICE_DECREASES} + 1
        Set Global Variable    ${PRICE_DECREASES}    ${decreases}
    ELSE IF    '${change_type}' == 'INCREASED'
        ${increases}=    Evaluate    ${PRICE_INCREASES} + 1
        Set Global Variable    ${PRICE_INCREASES}    ${increases}
    END
