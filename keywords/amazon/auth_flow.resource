*** Settings ***
Documentation       Inicialización segura de sesión operativa para la wishlist Amazon.
Resource            ../../resources/common/settings.resource
Resource            ../common/system/browser_keywords.resource

*** Keywords ***
Cargar Configuracion Y Parametros
    [Documentation]    Carga el YAML del entorno activo y el diccionario de localizadores Amazon.
    ${cfg}=    Load Environment Config    ${ENV}
    ${loc}=    Load Locators    resources/amazon/locators.yaml
    Set Global Variable    ${CONFIG}      ${cfg}
    Set Global Variable    ${LOCATORS}    ${loc}
    Log    Entorno Amazon configurado: ${ENV}    level=INFO

Obtener URL De Wishlist Configurada
    [Documentation]    Obtiene la URL inyectada en ejecución o la configurada de forma no sensible.
    ${url}=    Set Variable If
    ...    '${AMAZON_WISHLIST_URL}' != ''
    ...    ${AMAZON_WISHLIST_URL}
    ...    ${CONFIG}[amazon][wishlist_url]
    Should Not Be Empty
    ...    ${url}
    ...    msg=Defina AMAZON_WISHLIST_URL sin guardarla en archivos versionados.
    RETURN    ${url}

Iniciar Sesion En Portal
    [Documentation]    Inicia Chrome desde la copia temporal del perfil autorizado configurado.
    ${url}=          Obtener URL De Wishlist Configurada
    ${profile_name}=  Set Variable    ${CONFIG}[amazon][chrome_profile_name]
    ${timeout}=       Set Variable    ${CONFIG}[amazon][timeout_seconds]
    Inicializar Navegador Con Copia Temporal De Perfil
    ...    ${url}
    ...    ${AMAZON_CHROME_USER_DATA_DIR}
    ...    ${profile_name}
    ...    ${timeout}
