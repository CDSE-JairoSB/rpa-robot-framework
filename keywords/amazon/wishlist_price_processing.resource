*** Settings ***
Documentation       Lógica de negocio para consulta, extracción y persistencia de precios Amazon.
Resource            ../../resources/common/settings.resource
Resource            ../common/system/browser_keywords.resource


*** Keywords ***
Actualizar Wishlist Amazon
    [Documentation]    Extrae artículos visibles, registra sus precios en PriceRepository
    ...    y retorna un resumen estructurado.
    [Arguments]    ${items}=${None}
    @{items_to_process} =    Resolver Items De Wishlist    ${items}
    VAR    ${total} =    ${0}
    VAR    @{drops_found} =    @{EMPTY}
    FOR    ${item}    IN    @{items_to_process}
        ${drop_record} =    Procesar Articulo En Repositorio    ${item}
        ${total} =    Evaluate    ${total} + 1
        IF    $drop_record is not None and $drop_record.get('is_drop')
            Append To List    ${drops_found}    ${drop_record}
        END
    END
    ${summary} =    Build Execution Summary    ${total}    drops_found=${drops_found}
    Log    Resumen de wishlist: ${summary}    level=INFO
    RETURN    ${summary}

Resolver Items De Wishlist
    [Documentation]    Obtiene los artículos de los argumentos o los extrae directamente del DOM visible.
    [Arguments]    ${items}=${None}
    IF    $items is not None    RETURN    ${items}
    ${extracted} =    Extraer Articulos Visibles De Wishlist
    ...    ${LOCATORS}[wishlist][item_cards]
    ...    ${LOCATORS}[wishlist][item_title]
    ...    ${LOCATORS}[wishlist][item_link]
    ...    ${LOCATORS}[wishlist][item_price]
    ...    ${LOCATORS}[wishlist][item_availability]
    RETURN    ${extracted}

Procesar Articulo En Repositorio
    [Documentation]    Normaliza el precio del artículo y lo registra en SQLite vía PriceRepository.
    [Arguments]    ${item}
    ${extracted_info} =    Extraer Campos De Articulo    ${item}
    ${price_raw} =         Get From Dictionary    ${extracted_info}    raw_price
    ${normalized} =        Normalize Amazon Price    ${price_raw}
    ${price_str} =         Get From Dictionary    ${normalized}        price
    IF    not $price_str    RETURN    ${None}
    ${repo_item} =         Construir Registro Para Repositorio    ${extracted_info}    ${normalized}
    ${result} =            Record Price    ${repo_item}
    Actualizar Metricas Del Articulo    ${result}
    RETURN    ${result}

Extraer Campos De Articulo
    [Documentation]    Extrae nombre, url, precio e identificador soportando diversas convenciones de claves.
    [Arguments]    ${item}
    ${name} =        Evaluate    $item.get('product_name') or $item.get('title') or ''
    ${url} =         Evaluate    $item.get('product_url') or $item.get('url') or ''
    ${raw_price} =   Evaluate    str($item.get('raw_price') or $item.get('price') or '')
    ${id} =          Evaluate    $item.get('asin') or $item.get('id') or ''
    ${asin} =        Extract Asin From Url    ${url}
    ${final_id} =    Evaluate    $asin or $id or 'UNKNOWN'
    VAR    &{info} =
    ...    asin=${final_id}
    ...    name=${name}
    ...    url=${url}
    ...    raw_price=${raw_price}
    RETURN    ${info}

Construir Registro Para Repositorio
    [Documentation]    Estructura el diccionario esperado por PriceRepository.record_price.
    [Arguments]    ${info}    ${normalized}
    ${asin} =        Get From Dictionary    ${info}          asin
    ${name} =        Get From Dictionary    ${info}          name
    ${url} =         Get From Dictionary    ${info}          url
    ${price_str} =   Get From Dictionary    ${normalized}    price
    ${curr_raw} =    Get From Dictionary    ${normalized}    currency
    ${currency} =    Evaluate    $curr_raw or 'MXN'
    VAR    &{repo_item} =
    ...    asin=${asin}
    ...    title=${name}
    ...    url=${url}
    ...    current_price=${price_str}
    ...    currency=${currency}
    RETURN    ${repo_item}

Actualizar Metricas Del Articulo
    [Documentation]    Registra trazas operativas según el resultado de persistencia de PriceRepository.
    [Arguments]    ${record}
    ${asin} =       Get From Dictionary    ${record}    asin
    ${current} =    Get From Dictionary    ${record}    current_price
    ${is_drop} =    Get From Dictionary    ${record}    is_drop
    IF    ${is_drop}
        ${prev} =     Get From Dictionary    ${record}    previous_price
        ${pct} =      Get From Dictionary    ${record}    drop_percentage
        Log    [BAJADA DE PRECIO] ASIN ${asin}: $${prev} -> $${current} (-${pct}%)    level=WARN
    ELSE
        Log    [PRECIO OBSERVADO] ASIN ${asin}: $${current}    level=INFO
    END
