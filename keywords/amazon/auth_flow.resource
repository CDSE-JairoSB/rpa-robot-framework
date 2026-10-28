*** Settings ***
Documentation       Inicialización segura de sesión operativa para la wishlist Amazon.

Resource            ../../resources/common/settings.resource
Resource            ../common/system/browser_keywords.resource
Resource            ../common/system/runtime_config.resource


*** Keywords ***
Cargar Configuracion Y Parametros
    [Documentation]    Carga YAML de entorno, overrides locales y localizadores Amazon.
    ${cfg}=    Load Environment Config    ${ENV}
    Set Global Variable    ${CONFIG}    ${cfg}
    Resolver Parametros Locales Amazon
    ${loc}=    Load Locators    resources/amazon/locators.yaml
    Set Global Variable    ${LOCATORS}    ${loc}
    Log    Entorno Amazon configurado: ${ENV}    level=INFO

Iniciar Sesion En Portal
    [Documentation]    Inicia Chrome desde la copia temporal del perfil autorizado configurado.
    ${timeout}=    Set Variable    ${CONFIG}[amazon][timeout_seconds]
    Inicializar Navegador Con Copia Temporal De Perfil
    ...    ${AMAZON_WISHLIST_URL}
    ...    ${AMAZON_CHROME_USER_DATA_DIR}
    ...    ${AMAZON_CHROME_PROFILE_NAME}
    ...    ${timeout}
