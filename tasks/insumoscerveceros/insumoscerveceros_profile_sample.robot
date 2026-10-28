*** Settings ***
Documentation       Sample de perfil Chrome: navegación, validación de encabezado y cierre seguro.

Resource            ../../resources/common/settings.resource
Resource            ../../keywords/common/system/browser_keywords.resource

Suite Setup         Abrir Sitio Con Perfil 4
Suite Teardown      Cerrar Sesion Del Navegador


*** Variables ***
${SAMPLE_URL}               https://insumoscerveceros.mx/collections/fermentacion
${PAGE_HEADING}             xpath=(//h1[normalize-space()='Fermentación'])[1]
${CHROME_PROFILE_PATH}      ${AMAZON_CHROME_USER_DATA_DIR}
${CHROME_PROFILE_NAME}      Default


*** Tasks ***
Validar Navegacion Con Perfil 4
    [Documentation]    Abre Chrome con el perfil inyectado, navega al sitio y valida el encabezado Fermentación.
    Wait Until Element Is Visible    ${PAGE_HEADING}    timeout=20 seconds
    ${heading}=    Get Text    ${PAGE_HEADING}
    Should Be Equal    ${heading}    Fermentación
    Log To Console    Perfil ${CHROME_PROFILE_NAME} validado. Encabezado leído: ${heading}
    Log    Validación con perfil completada. Encabezado: ${heading}    level=INFO


*** Keywords ***
Abrir Sitio Con Perfil 4
    [Documentation]    Crea una copia temporal del perfil Chrome inyectado y abre el sitio.
    Should Not Be Empty
    ...    ${CHROME_PROFILE_PATH}
    ...    msg=Defina AMAZON_CHROME_USER_DATA_DIR en la ejecución; no se versiona.
    Inicializar Navegador Con Copia Temporal De Perfil
    ...    ${SAMPLE_URL}
    ...    ${CHROME_PROFILE_PATH}
    ...    profile_name=${CHROME_PROFILE_NAME}
    ...    timeout=20
