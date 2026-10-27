*** Settings ***
Documentation       Actualiza la nota de cada artículo de la Wishlist Amazon con su precio visible.
Resource            ../../resources/common/settings.resource
Resource            ../../keywords/common/system/browser_keywords.resource
Resource            ../../keywords/common/system/runtime_config.resource

Suite Setup         Preparar Sesion Amazon Wishlist
Suite Teardown      Cerrar Sesion Del Navegador

*** Variables ***
${PAGE_HEADING}         id=profile-list-name
${ITEM_PRICE}           xpath=//span[contains(@class, 'a-price') and contains(@id, 'itemPrice_')]
${ADD_NOTE}             xpath=//a[contains(normalize-space(.), 'Agrega una nota')]
${NOTE_BOX}             id=WLNOTES_Comment
${SAVE_NOTE}            xpath=//*[@id='WLNOTES_save']//input[@type='submit']
${EXPECTED_HEADING}      Grosery
${BROWSER_TIMEOUT}       20
${SCROLL_PAUSE}          2 seconds
${MAX_SCROLL_ATTEMPTS}   20

*** Tasks ***
Actualizar Notas De Precios De Wishlist
    [Documentation]    Carga todos los artículos de la Wishlist y guarda el precio visible como nota de cada artículo.
    Confirmar Acceso A Wishlist
    Cargar Todos Los Items De Wishlist
    ${items}=    Obtener Items Y Precios De Wishlist
    ${total_items}=    Get Length    ${items}
    Should Be True    ${total_items} > 0    msg=No se encontraron artículos con precio en la Wishlist.
    Log To Console    Total de items cargados: ${total_items}
    Log    Total de items cargados: ${total_items}    level=INFO
    ${updated_items}=    Set Variable    0
    FOR    ${item}    IN    @{items}
        TRY
            ${was_updated}=    Actualizar Nota Solo Si El Precio Es Menor    ${item}
            IF    ${was_updated}
                ${updated_items}=    Evaluate    ${updated_items} + 1
            END
        EXCEPT    AS    ${error}
            Log To Console    Error aislado en artículo: ${error}
            Log    [SYSTEM_EXCEPTION] Artículo omitido: ${error}    level=ERROR
        END
    END
    Log To Console    Proceso finalizado. Notas actualizadas: ${updated_items}
    Log    Proceso finalizado. Notas actualizadas: ${updated_items}    level=INFO

*** Keywords ***
Preparar Sesion Amazon Wishlist
    [Documentation]    Resuelve URL/perfil locales y abre Chrome con una copia temporal del perfil.
    Resolver Parametros Locales Amazon
    Abrir Wishlist Con Perfil Autorizado

Abrir Wishlist Con Perfil Autorizado
    [Documentation]    Crea una copia temporal del perfil Chrome resuelto y abre la Wishlist.
    Inicializar Navegador Con Copia Temporal De Perfil
    ...    ${AMAZON_WISHLIST_URL}
    ...    ${AMAZON_CHROME_USER_DATA_DIR}
    ...    profile_name=${AMAZON_CHROME_PROFILE_NAME}
    ...    timeout=${BROWSER_TIMEOUT}

Confirmar Acceso A Wishlist
    Wait Until Element Is Visible    ${PAGE_HEADING}    timeout=${BROWSER_TIMEOUT} seconds
    ${heading}=    Get Text    ${PAGE_HEADING}
    #Should Be Equal    ${heading}    ${EXPECTED_HEADING}
    Log To Console    Wishlist confirmada: ${heading}
    Log    Wishlist confirmada: ${heading}    level=INFO

Cargar Todos Los Items De Wishlist
    [Documentation]    Desplaza al final hasta que el número de precios permanezca estable en dos iteraciones consecutivas.
    Execute JavaScript    window.__wishlistItems = {};
    ${previous_count}=    Set Variable    -1
    ${stable_iterations}=    Set Variable    0
    FOR    ${attempt}    IN RANGE    ${MAX_SCROLL_ATTEMPTS}
        Execute JavaScript
        ...    document.querySelectorAll("span.a-price[id*='itemPrice_']").forEach(price=>{const id=price.id.replace("itemPrice_","");const card=document.getElementById("item_"+id);const note=card?.querySelector("a[href*='/hz/wishlist/cqp/']");const value=(price.querySelector(".a-offscreen")?.textContent||price.textContent||"").trim().split(/\s+/)[0];if(id&&value&&note?.href){window.__wishlistItems[id]={id,price:value,note_url:note.href};}});
        ${current_count}=    Get Element Count    ${ITEM_PRICE}
        Execute JavaScript    window.scrollTo(0, document.body.scrollHeight);
        Sleep    ${SCROLL_PAUSE}
        ${new_count}=    Get Element Count    ${ITEM_PRICE}
        IF    ${new_count} == ${previous_count} and ${new_count} == ${current_count}
            ${stable_iterations}=    Evaluate    ${stable_iterations} + 1
        ELSE
            ${stable_iterations}=    Set Variable    0
        END
        ${previous_count}=    Set Variable    ${new_count}
        IF    ${stable_iterations} >= 2
            Exit For Loop
        END
    END
    Should Be True    ${previous_count} > 0    msg=No se cargaron artículos de la Wishlist.
    Log    Carga por scroll completada. Precios visibles: ${previous_count}    level=INFO

Obtener Items Y Precios De Wishlist
    [Documentation]    Devuelve cada identificador de artículo y su precio visible, evitando duplicados de precio renderizado.
    ${items}=    Execute JavaScript    return Object.values(window.__wishlistItems || {});
    RETURN    ${items}

Actualizar Nota Solo Si El Precio Es Menor
    [Documentation]    Guarda el precio actual si la nota está vacía o cuando es menor que el precio numérico registrado.
    [Arguments]    ${item}
    ${item_id}=          Get From Dictionary    ${item}    id
    ${current_price}=    Get From Dictionary    ${item}    price
    ${note_url}=         Get From Dictionary    ${item}    note_url
    Go To    ${note_url}
    Wait Until Element Is Visible    ${NOTE_BOX}    timeout=${BROWSER_TIMEOUT} seconds
    ${registered_price}=    Get Value    ${NOTE_BOX}
    Log To Console    Precio registrado leído para ${item_id}: ${registered_price}
    ${is_empty_note}=    Run Keyword And Return Status    Should Be Empty    ${registered_price}
    IF    ${is_empty_note}
        Clear Element Text    ${NOTE_BOX}
        Input Text    ${NOTE_BOX}    ${current_price}
        Click Element    ${SAVE_NOTE}
        Wait Until Element Is Not Visible    ${NOTE_BOX}    timeout=${BROWSER_TIMEOUT} seconds
        Wait Until Element Is Visible    ${PAGE_HEADING}    timeout=${BROWSER_TIMEOUT} seconds
        Log To Console    Nota vacía inicializada: ${item_id} = ${current_price}
        Log    Nota vacía inicializada para ${item_id} con precio actual ${current_price}.    level=INFO
        RETURN    ${True}
    END
    ${has_registered_price}=    Run Keyword And Return Status
    ...    Should Match Regexp
    ...    ${registered_price}
    ...    ^[ ]*[$]?[ ]*[0-9]+([,.][0-9]{1,2})?[ ]*$
    IF    not ${has_registered_price}
        Log To Console    Sin precio registrado válido; no se actualiza: ${item_id}
        Log    Sin precio registrado válido para ${item_id}; no se realizó cambio.    level=INFO
        RETURN    ${False}
    END
    ${current_value}=       Convertir Precio A Numero    ${current_price}
    ${registered_value}=    Convertir Precio A Numero    ${registered_price}
    IF    ${current_value} < ${registered_value}
        Clear Element Text    ${NOTE_BOX}
        Input Text    ${NOTE_BOX}    ${current_price}
        Click Element    ${SAVE_NOTE}
        Wait Until Element Is Not Visible    ${NOTE_BOX}    timeout=${BROWSER_TIMEOUT} seconds
        Wait Until Element Is Visible    ${PAGE_HEADING}    timeout=${BROWSER_TIMEOUT} seconds
        Log To Console    Nota actualizada: ${item_id} = ${current_price} (anterior: ${registered_price})
        Log    Precio menor detectado para ${item_id}: ${registered_price} -> ${current_price}    level=INFO
        RETURN    ${True}
    END
    Log To Console    Sin cambio: ${item_id}; actual ${current_price} >= registrado ${registered_price}
    Log    Sin cambio para ${item_id}; precio actual ${current_price} no es menor que ${registered_price}.    level=INFO
    RETURN    ${False}

Convertir Precio A Numero
    [Documentation]    Convierte un importe Amazon MXN/USD a número decimal.
    [Arguments]    ${price}
    ${normalized}=    Normalize Amazon Price    ${price}
    ${number_text}=    Get From Dictionary    ${normalized}    price
    Should Not Be Empty    ${number_text}    msg=No se pudo normalizar el precio: ${price}
    ${number}=    Convert To Number    ${number_text}
    RETURN    ${number}
