*** Settings ***
Documentation     Rastrea precios de la Wishlist Amazon en modo solo lectura y persiste en PriceRepository.

Resource          ../../resources/common/settings.resource
Resource          ../../keywords/common/system/browser_keywords.resource
Resource          ../../keywords/common/system/runtime_config.resource
Resource          ../../keywords/amazon/wishlist_price_processing.resource

Suite Setup       Preparar Sesion Amazon Wishlist
Suite Teardown    Finalizar Suite Wishlist


*** Variables ***
${PAGE_HEADING}           id=profile-list-name
${ITEM_PRICE}             xpath=//span[contains(@class, 'a-price') and contains(@id, 'itemPrice_')]
${BROWSER_TIMEOUT}        20
${SCROLL_PAUSE}           2 seconds
${MAX_SCROLL_ATTEMPTS}    20
${STATUS_FILE_PATH}       results/status.json
${LOGIN_FORM_LOCATOR}     css:#ap_email, input[type='email'], input[name='email'], #auth-mfa-otpcode
${CAPTCHA_LOCATOR}        css:#captchacharacters, form[action*='validateCaptcha']


*** Tasks ***
Actualizar Precios De Wishlist Amazon
    [Documentation]    Carga la Wishlist en modo solo lectura, registra precios en SQLite
    ...    y detecta bajas de precio.
    Ejecutar Actualizacion De Precios


*** Keywords ***
Ejecutar Actualizacion De Precios
    [Documentation]    Coordina la extracción y persistencia, capturando errores para señalizar el estado.
    TRY
        Confirmar Acceso A Wishlist
        Cargar Todos Los Items De Wishlist
        ${items} =    Obtener Items Y Precios De Wishlist
        ${total_items} =    Get Length    ${items}
        IF    ${total_items} == 0
            Fail    [ERROR_SELECTOR] No se encontraron artículos visibles en la Wishlist.
        END
        ${summary} =    Actualizar Wishlist Amazon    ${items}
        ${status} =    Get From Dictionary    ${summary}    status
        Log To Console    Ejecución completada: ${status} (Total: ${total_items})
    EXCEPT    AS    ${error}
        Manejar Falla De Ejecucion    ${error}
    END

Manejar Falla De Ejecucion
    [Documentation]    Determina el código de error correspondiente y registra el estado en la suite.
    [Arguments]    ${error}
    Set Execution Summary    error=${error}
    ${status} =    Resolve Execution Status    0    error=${error}
    Log To Console    Error capturado: ${status} - ${error}
    Fail    ${error}

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
    [Documentation]    Verifica que la sesión no requiera 2FA, captcha o presente un selector inválido.
    ${needs_login} =    Run Keyword And Return Status
    ...    Page Should Contain Element    ${LOGIN_FORM_LOCATOR}
    IF    ${needs_login}
        Fail    [STATUS_NEEDS_2FA] Amazon requiere inicio de sesión o verificación 2FA.
    END
    ${is_captcha} =    Run Keyword And Return Status
    ...    Page Should Contain Element    ${CAPTCHA_LOCATOR}
    IF    ${is_captcha}
        Fail    [RATE_LIMITED] Amazon presentó un CAPTCHA o verificación de robot.
    END
    ${heading_visible} =    Run Keyword And Return Status
    ...    Wait Until Element Is Visible    ${PAGE_HEADING}    timeout=${BROWSER_TIMEOUT} seconds
    IF    not ${heading_visible}
        Fail    [ERROR_SELECTOR] No se pudo encontrar el encabezado de la Wishlist.
    END
    ${heading} =    Get Text    ${PAGE_HEADING}
    Log    Wishlist confirmada: ${heading}    level=INFO

Cargar Todos Los Items De Wishlist
    [Documentation]    Desplaza al final hasta que el número de precios permanezca estable en dos iteraciones.
    VAR    ${previous_count} =    ${-1}
    VAR    ${stable_iterations} =    ${0}
    FOR    ${_}    IN RANGE    ${MAX_SCROLL_ATTEMPTS}
        ${new_count}    ${stable_iterations} =    Scroll Y Evaluar Estabilidad
        ...    ${previous_count}    ${stable_iterations}
        VAR    ${previous_count} =    ${new_count}
        IF    ${stable_iterations} >= 2    BREAK
    END
    IF    ${previous_count} <= 0
        Fail    [ERROR_SELECTOR] No se cargaron artículos de la Wishlist tras el desplazamiento.
    END
    Log    Carga por scroll completada. Precios visibles: ${previous_count}    level=INFO

Scroll Y Evaluar Estabilidad
    [Documentation]    Realiza un scroll hacia abajo y calcula si el contador de precios se mantuvo estable.
    [Arguments]    ${previous_count}    ${stable_iterations}
    ${current_count} =    Get Element Count    ${ITEM_PRICE}
    Execute JavaScript    window.scrollTo(0, document.body.scrollHeight);
    Sleep    ${SCROLL_PAUSE}
    ${new_count} =    Get Element Count    ${ITEM_PRICE}
    ${is_same} =    Evaluate    ${new_count} == ${previous_count} and ${new_count} == ${current_count}
    ${updated_stable} =    Evaluate    ${stable_iterations} + 1 if ${is_same} else 0
    RETURN    ${new_count}    ${updated_stable}

Obtener Items Y Precios De Wishlist
    [Documentation]    Extrae identificador, título, url y precio directamente del DOM sin tocar notas.
    ${js_extract} =    Catenate    SEPARATOR=\n
    ...    const items = [];
    ...    const cards = document.querySelectorAll("li.g-item-sortable, div.g-item-sortable, [data-itemid]");
    ...    cards.forEach(card => {
    ...    const id = card.getAttribute("data-itemid") || (card.id ? card.id.replace("item_", "") : "");
    ...    const titleEl = card.querySelector("h2 a, h3 a, a[id*='itemName'], a.a-link-normal");
    ...    const priceEl = card.querySelector(".a-price .a-offscreen, .itemPrice, [data-testid='price']");
    ...    const linkEl = card.querySelector("a[href*='/dp/'], a[href*='/gp/product/'], h2 a, h3 a");
    ...    const title = (titleEl?.textContent || "").trim();
    ...    const price = (priceEl?.textContent || "").trim();
    ...    const url = linkEl?.href || "";
    ...    if (id || url || title) { items.push({ id, title, price, url }); }
    ...    });
    ...    return items;
    ${items} =    Execute JavaScript    ${js_extract}
    RETURN    ${items}

Finalizar Suite Wishlist
    [Documentation]    Escribe el estado final a results/status.json y cierra la sesión del navegador.
    Guardar Estado Final De Ejecucion
    Cerrar Sesion Del Navegador

Guardar Estado Final De Ejecucion
    [Documentation]    Persiste results/status.json de forma segura para orquestaciones y monitoreo.
    ${saved} =    Save Status To Json    output_path=${STATUS_FILE_PATH}
    ${status} =    Get From Dictionary    ${saved}    status
    Log    Estado final guardado en '${STATUS_FILE_PATH}': ${status}    level=INFO
